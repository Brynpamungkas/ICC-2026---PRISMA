"""SYNTHETIC verifier fixtures only; no HTTP/model/study results are produced."""
from copy import deepcopy
import json
from uuid import uuid4

import pytest

from backend.app.config import load_config


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status_code = status
        self.payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self.payload


class SyntheticService:
    def __init__(self, *, hold=False, health=200, mismatch=False, mutate=False):
        self.hold, self.health, self.mismatch, self.mutate = hold, health, mismatch, mutate
        self.original = None
        self.choice = None
        self.posts = 0

    def request(self, method, url, **kw):
        path = url.split('/api')[-1]
        if '/api' not in url:
            return FakeResponse('SYNTHETIC PRISMA HTML')
        if path == '/kesehatan':
            return FakeResponse({k: {'status': 'AVAILABLE' if self.health == 200 else 'UNAVAILABLE',
                'checked_at': '2099-01-01T00:00:00+00:00'} for k in ('model','database')}, self.health)
        if path == '/katalog':
            from backend.app.catalog import get_catalog
            return FakeResponse({'indikator': [dict(kode=m.code,nama_kanonik=m.name,definisi_resmi=m.definition,
                satuan=m.unit,sumber=m.source,cakupan_wilayah=sorted(m.regions),periode_tersedia=sorted(m.periods))
                for m in get_catalog().indicators.values()]})
        if path == '/tanya':
            self.posts += 1
            b = kw['json']
            def ev(code, rows, structure='TEXT'):
                return {'candidate': {'code':code,'canonical_name':'SYNTHETIC','unit':'% ' if code=='KMS_PERSEN' else 'ribu jiwa'},
                    'result': {'candidate_code':code,'columns':['wilayah','nilai'] if structure=='TEXT' else ['nilai'],
                    'rows':rows,'structure':structure,'unit':'% ' if code=='KMS_PERSEN' else 'ribu jiwa','error':None}}
            if self.posts == 1:
                d = {'decision':'TANYA','answer':None,'evidence':[ev('KMS_PERSEN',[['SYN_A',10]]),
                    ev('KMS_JUMLAH',[['SYN_B',20]])], 'reason_code':None,'suggestion':None,'period_used':'2025-09'}
                if self.hold:
                    d = {'decision':'TAHAN','reason_code':'T0','suggestion':'SYNTHETIC unavailable','period_used':'2025-09'}
                self.original = deepcopy(d)
                self.session = b['id_sesi']
                self.log_id = str(uuid4())
            elif self.posts == 2:
                d = {'decision':'JAWAB','answer':ev('KMS_JUMLAH',[[30]],'NUMBER'),'period_used':'2025-09'}
            else:
                d = {'decision':'TAHAN','reason_code':'T1','suggestion':'SYNTHETIC outside catalog'}
            return FakeResponse({'id_sesi':b['id_sesi'],'id_log': self.log_id if self.posts==1 else str(uuid4()),'decision':d})
        if path.startswith('/log/'):
            if kw['headers']['X-Session-ID'] != self.session:
                return FakeResponse({'error':{'code':'LOG_NOT_FOUND','message':'Log tidak ditemukan.','id_log':None}},200 if self.mismatch else 404)
            from backend.app.catalog import get_catalog
            d = self.choice if self.mutate else self.original
            return FakeResponse({'id_log':self.log_id,'record':{'run_id':uuid4().hex,'session_id':self.session,
                'question':'Provinsi mana yang paling miskin?','mode':'K3','prompt_version':load_config()['prompt']['version'],
                'dictionary_hash':get_catalog().version,'decision':d}})
        if path == '/klarifikasi':
            b = kw['json']
            if b['indikator_pilihan'] != 'KMS_PERSEN':
                return FakeResponse({'error':{'code':'CHOICE_CONFLICT','message':'SYNTHETIC','id_log':None}},409)
            self.choice = {'decision':'JAWAB','answer':self.original['evidence'][0], 'period_used':'2025-09'}
            return FakeResponse({'id_sesi':b['id_sesi'],'id_log':b['id_log'],'decision':self.choice})
        raise AssertionError((method,url,kw))


def run_synthetic(tmp_path, monkeypatch, service):
    from scripts import smoke_http
    monkeypatch.setattr(smoke_http, 'references', lambda cfg: {
        'GOLD-01': {'KMS_PERSEN':[['SYN_A',10]],'KMS_JUMLAH':[['SYN_B',20]]},
        'GOLD-02': {'KMS_JUMLAH':[[30]]},'GOLD-03':{}})
    return smoke_http.run(load_config(), tmp_path/'run', requester=service)


def test_http_smoke_checks_five_endpoints_and_original_evidence(tmp_path, monkeypatch):
    assert run_synthetic(tmp_path, monkeypatch, SyntheticService())
    summary = json.loads((tmp_path/'run/summary.json').read_text())
    assert summary['passed'] and not summary['baseline_gate_passed']
    assert {r['case_id'] for r in summary['cases']} == {'GOLD-01','GOLD-02','GOLD-03'}
    assert summary['checks']['session_isolation'] and summary['checks']['original_tanya_preserved']


def test_200_tahan_t0_is_not_treated_as_success(tmp_path, monkeypatch):
    assert not run_synthetic(tmp_path, monkeypatch, SyntheticService(hold=True))
    summary = json.loads((tmp_path/'run/summary.json').read_text())
    assert not summary['cases'][0]['passed']


def test_unavailable_health_stops_before_model_requests(tmp_path, monkeypatch):
    service = SyntheticService(health=503)
    assert not run_synthetic(tmp_path,monkeypatch,service)
    assert service.posts == 0


def test_cross_session_log_leak_fails_smoke(tmp_path, monkeypatch):
    assert not run_synthetic(tmp_path,monkeypatch,SyntheticService(mismatch=True))


def test_changed_original_tanya_log_fails_smoke(tmp_path, monkeypatch):
    assert not run_synthetic(tmp_path,monkeypatch,SyntheticService(mutate=True))


def test_existing_evidence_directory_is_never_overwritten(tmp_path):
    from scripts import smoke_http
    folder=tmp_path/'existing'
    folder.mkdir()
    (folder/'sentinel').write_text('keep')
    with pytest.raises(FileExistsError):
        smoke_http.run(load_config(),folder,requester=SyntheticService())
    assert (folder/'sentinel').read_text() == 'keep'
