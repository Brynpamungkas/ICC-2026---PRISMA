"""Check the running local frontend/API/model against the paper's three A-4 cases.

This sends real requests and creates real question/clarification logs. No retries,
mock backend, reference answers, or repaired SQL are supplied to the model.
This is not final research evaluation or a browser accessibility/visual test.
Run: PRISMA_CONFIG=config/local.cpu.yaml .venv/bin/python -m scripts.smoke_http
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time
from uuid import uuid4

import requests

from backend.app.catalog import get_catalog
from backend.app.config import ROOT, load_config
from backend.app.schemas.api import CatalogResponse, HealthResponse, LogResponse, QuestionResponse
from scripts.smoke_pipeline import _reference, check_case

CASES = [("GOLD-01", "Provinsi mana yang paling miskin?", "TANYA"),
         ("GOLD-02", "Berapa total penduduk miskin di Pulau Jawa?", "JAWAB"),
         ("GOLD-03", "Berapa IPM Jawa Barat?", "TAHAN")]
PAPER_PERIOD = "2025-09"  # Explicit A-4 snapshot; never change the requested period to force a pass.


def references(config: dict) -> dict:
    """Compute local read-only reference rows; never send them to the HTTP API/model."""
    cat = get_catalog()
    sql = ("SELECT p.nama AS wilayah,n.nilai AS nilai FROM nilai_indikator n JOIN provinsi p ON p.kode=n.kode_provinsi "
           "WHERE n.kode_indikator=:indikator AND n.periode=:periode ORDER BY n.nilai DESC LIMIT 1")
    rank = {c: _reference(sql, {'indikator':c, 'periode':PAPER_PERIOD}, config) for c in ('KMS_PERSEN','KMS_JUMLAH')}
    regions = sorted(cat.kamus[('pulau','jawa')]['wilayah'])
    params = {f'wilayah_{i}': code for i, code in enumerate(regions)}
    sql = ("SELECT SUM(n.nilai) AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator "
           "AND n.periode=:periode AND n.kode_provinsi IN (" + ','.join(':'+k for k in params) + ')')
    total = _reference(sql, {**params,'indikator':'KMS_JUMLAH','periode':PAPER_PERIOD}, config)
    return {'GOLD-01':rank, 'GOLD-02':{'KMS_JUMLAH':total}, 'GOLD-03':{}}


def run(config: dict, output: Path, *, requester=None) -> bool:
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    owned = requester is None
    client = requests.Session() if owned else requester
    if owned:
        client.trust_env = False
    cat = get_catalog()
    session = str(uuid4())
    origins = {}
    for key in ('api','frontend'):
        host = config[key]['host']
        if host not in ('localhost','127.0.0.1','::1'):
            raise ValueError('Smoke HTTP requires an explicitly configured loopback host')
        origins[key] = f"http://{'['+host+']' if ':' in host else host}:{config[key]['port']}"
    report = {'run_id':output.name,'purpose':'PAPER_A4_REAL_HTTP_NOT_FINAL_EVALUATION',
              'started_at':datetime.now(timezone.utc).isoformat(), 'passed':False,'baseline_gate_passed':False,
              'backend':config['model']['backend'],'model':config['model']['name'],
              'prompt_version':config['prompt']['version'],'sampling':config['sampling'],
              'catalog_hash':cat.version,'python':platform.python_version(),
              'origins':origins,'cases':[],'checks':{},'requests':[],
              'limitations':['No browser visual/accessibility acceptance', 'No final evaluation/gate accepted',
                             'Workspace hashes do not independently attest an already-running server process',
                             'CPU results remain separate from vLLM/AWQ/N64']}
    report['code_commit'] = subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,
                                          text=True,check=True).stdout.strip()
    report['code_dirty'] = bool(subprocess.run(['git','status','--porcelain'],cwd=ROOT,capture_output=True,
                                              text=True,check=True).stdout)
    report['source_sha256'] = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in (ROOT/'backend/app',ROOT/'scripts') for p in sorted(folder.rglob('*.py'))}
    report['resolved_config_sha256'] = hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
    db = ROOT/config['execution']['db_path']
    report['database_sha256'] = hashlib.sha256(db.read_bytes()).hexdigest() if db.is_file() else None
    (output/'resolved_config.json').write_text(json.dumps(config,indent=2)+'\n')

    def save():
        (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

    def request(method, path, *, origin='frontend', body=None, headers=None):
        url = origins[origin]+path
        start = time.monotonic()
        row = {'sequence':len(report['requests']),'method':method,'url':url,'body':body,'headers':headers}
        report['requests'].append(row)
        try:
            response = client.request(method,url,json=body,headers=headers,
                                      timeout=config['transport']['timeout_s'],allow_redirects=False)
            row['status_code'],row['response_text'] = response.status_code,response.text
            try:
                payload = response.json()
            except ValueError:
                payload = None
            row['response_json'] = payload
            return response.status_code,payload,response.text
        except Exception as exc:
            row['failure'] = {'category':type(exc).__name__,'message':str(exc)}
            raise
        finally:
            row['duration_s'] = time.monotonic()-start
            (output/f"http-{row['sequence']:03d}.json").write_text(json.dumps(row,indent=2,ensure_ascii=False)+'\n')
            save()

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    save()
    try:
        for origin in ('api','frontend'):
            status,payload,_ = request('GET','/api/kesehatan',origin=origin)
            health = HealthResponse.model_validate(payload)
            require(status == 200 and health.model.status == health.database.status == 'AVAILABLE',
                    f'{origin}: model/database not ready')
            report['checks'][origin+'_health'] = True
        status,_,html = request('GET','/')
        require(status == 200 and 'PRISMA' in html.upper(),'Frontend HTML unavailable')
        report['checks']['frontend_html'] = True
        catalogs = []
        for origin in ('api','frontend'):
            status,payload,_ = request('GET','/api/katalog',origin=origin)
            require(status == 200,'Catalog request failed')
            parsed = CatalogResponse.model_validate(payload)
            catalogs.append({m.kode:m.model_dump() for m in parsed.indikator})
        require(catalogs[0] == catalogs[1] and set(catalogs[0]) == set(cat.indicators),
                'Catalog differs across backend/proxy/local snapshot')
        report['checks']['catalog_proxy'] = True
        refs = references(config)
        for identifier,question,expected in CASES:
            row = {'case_id':identifier,'question':question,'expected':expected,'passed':False,'references':refs[identifier]}
            report['cases'].append(row)
            try:
                status,payload,_ = request('POST','/api/tanya',body={'pertanyaan':question,'id_sesi':session})
                require(status == 200,'Question did not return a completed domain decision')
                answer = QuestionResponse.model_validate(payload)
                require(answer.id_sesi == session,'Question session mismatch')
                d = answer.decision.model_dump()
                row['response'] = answer.model_dump()
                errors = check_case(d,expected,refs[identifier],'T1' if expected == 'TAHAN' else None)
                if expected != 'TAHAN' and d['period_used'] != PAPER_PERIOD:
                    errors.append('Resolved period differs from explicit A-4 snapshot')
                require(not errors,'; '.join(errors))
                if expected == 'TANYA':
                    owned_headers = {'X-Session-ID':session}
                    status,payload,_ = request('GET','/api/log/'+answer.id_log,headers=owned_headers)
                    require(status == 200,'Original log unavailable')
                    original = LogResponse.model_validate(payload)
                    require(original.record.session_id == session and original.record.question == question and
                            original.record.decision.model_dump() == d,'Original question/log mismatch')
                    require(original.record.prompt_version == str(config['prompt']['version']) and
                            original.record.dictionary_hash == cat.version,'Stale server prompt or catalog')
                    row['id_log'],row['run_id'] = answer.id_log,original.record.run_id
                    chosen = d['evidence'][0]
                    choice = {'id_sesi':session,'id_log':answer.id_log,'indikator_pilihan':chosen['candidate']['code']}
                    answers = []
                    for _ in range(2):
                        status,payload,_ = request('POST','/api/klarifikasi',body=choice)
                        require(status == 200,'Clarification/retry failed')
                        result = QuestionResponse.model_validate(payload)
                        require(result.id_sesi == session and result.id_log == answer.id_log and
                                result.decision.decision == 'JAWAB' and result.decision.answer.model_dump() == chosen,
                                'Clarification differs from selected original evidence')
                        answers.append(result.model_dump())
                    require(answers[0] == answers[1],'Identical clarification retry changed response')
                    report['checks']['clarification_idempotent'] = True
                    status,payload,_ = request('POST','/api/klarifikasi',body={**choice,
                        'indikator_pilihan':d['evidence'][1]['candidate']['code']})
                    require(status == 409 and payload['error']['code'] == 'CHOICE_CONFLICT','Different second choice not rejected')
                    report['checks']['choice_conflict'] = True
                    status,payload,_ = request('GET','/api/log/'+answer.id_log,headers={'X-Session-ID':str(uuid4())})
                    require(status == 404 and payload['error']['code'] == 'LOG_NOT_FOUND','Cross-session log access not rejected')
                    report['checks']['session_isolation'] = True
                    status,payload,_ = request('GET','/api/log/'+answer.id_log,headers=owned_headers)
                    require(status == 200 and LogResponse.model_validate(payload).record.decision.model_dump() == d,
                            'Clarification overwrote original TANYA evidence')
                    report['checks']['original_tanya_preserved'] = True
                row['passed'] = True
            except Exception as exc:
                row['failure'] = {'category':type(exc).__name__,'message':str(exc)}
            finally:
                save()
            print(identifier+': '+('PASS' if row['passed'] else 'FAIL'),flush=True)
        report['passed'] = len(report['cases']) == len(CASES) and all(r['passed'] for r in report['cases'])
    except Exception as exc:
        report['failure'] = {'category':type(exc).__name__,'message':str(exc)}
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        save()
        if owned:
            client.close()
    return report['passed']


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path)
    args = parser.parse_args()
    name = 'http-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex
    output = args.out or ROOT/'eval/runs'/name
    passed = run(load_config(),output)
    print(f'Bukti: {output}. Tidak meluluskan G2/G3/G4 otomatis.')
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
