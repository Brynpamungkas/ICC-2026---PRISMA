"""Build, test, and verify the existing CPU stack from a normal local terminal.

No installations, model downloads, Git mutations, label changes, tau calibration,
or final research evaluation. Only services started by this run are stopped.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from uuid import uuid4

import requests

from backend.app.config import ROOT, load_config


def check_ports(config: dict) -> None:
    """Check permission/occupancy before altering the generated frontend build."""
    for key in ('frontend','api','llama_cpp'):
        host, port = config[key]['host'],config[key]['port']
        if host not in ('127.0.0.1','localhost','::1'):
            raise ValueError('Verifikasi hanya diizinkan pada host loopback lokal.')
        family = socket.AF_INET6 if ':' in host else socket.AF_INET
        with socket.socket(family,socket.SOCK_STREAM) as probe:
            probe.bind((host,port))


def command(argv: list[str], *, env: dict, log: Path, timeout_s: float) -> dict:
    """Retain exact command output and enforce a bounded lifetime for our process group."""
    start = time.monotonic()
    with log.open('x',encoding='utf-8') as stream:
        process = subprocess.Popen(argv,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            code = process.wait(timeout=timeout_s)
            return {'argv':argv,'exit_code':code,'status':'PASS' if code == 0 else 'FAIL',
                    'log':str(log),'duration_s':time.monotonic()-start}
        except (subprocess.TimeoutExpired,KeyboardInterrupt):
            os.killpg(process.pid,signal.SIGKILL)
            process.wait()
            return {'argv':argv,'exit_code':process.returncode,'status':'TIMEOUT_OR_INTERRUPTED',
                    'log':str(log),'duration_s':time.monotonic()-start}


def _health_url(config: dict) -> str:
    host=config['api']['host']
    return f"http://{'['+host+']' if ':' in host else host}:{config['api']['port']}/api/kesehatan"


def run(config: dict, output: Path, *, config_path: str | Path = 'config/local.cpu.yaml') -> int:
    if config['model']['backend'] != 'llama_cpp' or config['llama_cpp']['gpu_layers'] != 0:
        raise ValueError('Prosedur ini hanya untuk profil llama.cpp CPU yang disepakati.')
    output.mkdir(parents=True,exist_ok=False,mode=0o700)
    report={'run_id':output.name,'status':'STARTED','passed':False,'baseline_gate_passed':False,
            'started_at':datetime.now(timezone.utc).isoformat(),'commands':[],
            'runtime':{'backend':config['model']['backend'],'model':config['model']['name'],
                       'sampling':config['sampling'],'prompt_version':config['prompt']['version']},
            'limitations':['Browser visual/keyboard/accessibility acceptance remains separate',
                           'Golden FROZEN skips are not accepted as passed',
                           'No final evaluation or gate accepted automatically']}
    service=None
    service_log=None

    def save():
        (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

    save()
    try:
        try:
            check_ports(config)
        except OSError as exc:
            report['status']='BLOCKED_LOCAL_PORTS'
            report['failure']={'category':type(exc).__name__,'message':str(exc)}
            print('Port/izin socket belum tersedia. Hentikan launcher lama milik Anda atau jalankan dari terminal biasa.',flush=True)
            return 1
        env=dict(os.environ)
        # An explicit CPU configuration must never be replaced by an ambient
        # baseline profile, including when this helper itself runs under pytest.
        env['PRISMA_CONFIG']=str(ROOT/config_path)
        env['PRISMA_PYTHON']=sys.executable
        node=ROOT/'.local'/f"node-v{config['local_setup']['node_version']}-linux-{os.uname().machine.replace('x86_64','x64').replace('aarch64','arm64')}"/'bin'
        if node.is_dir():
            env['PATH']=str(node)+os.pathsep+env.get('PATH','')
        timeout=config['transport']['timeout_s']
        steps=[('frontend-tests',['npm','--prefix','frontend','test']),
               ('frontend-types',['npm','--prefix','frontend','run','typecheck']),
               ('frontend-build',['npm','--prefix','frontend','run','build']),
               ('backend-tests',['make','test','PY='+sys.executable]),
               ('backend-lint',['make','lint','PY='+sys.executable])]
        for name,argv in steps:
            print('Memeriksa '+name+' ...',flush=True)
            step_env=dict(env)
            if name == 'backend-tests':
                # The existing mock suite asserts baseline N=64. This does not
                # launch vLLM or replace the live CPU N=8 configuration below.
                step_env['PRISMA_CONFIG']=str(ROOT/'config/config.yaml')
            result=command(argv,env=step_env,log=output/(name+'.log'),timeout_s=timeout)
            result['config_profile']=step_env['PRISMA_CONFIG']
            report['commands'].append(result)
            save()
            if result['status'] != 'PASS':
                report['status']='FAILED_'+name.upper().replace('-','_')
                return 1
        print('Menjalankan layanan CPU milik pemeriksaan ini ...',flush=True)
        service_log=(output/'services.log').open('x',encoding='utf-8')
        service=subprocess.Popen(['bash','scripts/run_local.sh','cpu'],cwd=ROOT,env=env,
                                 stdout=service_log,stderr=subprocess.STDOUT,start_new_session=True)
        report['service_pid']=service.pid
        deadline=time.monotonic()+timeout
        with requests.Session() as http:
            http.trust_env=False
            while True:
                if service.poll() is not None:
                    report['status']='FAILED_SERVICE_STARTUP'
                    return 1
                try:
                    response=http.get(_health_url(config),timeout=config['api']['health_timeout_s'],allow_redirects=False)
                    payload=response.json()
                    if response.status_code == 200 and all(payload[k]['status']=='AVAILABLE' for k in ('model','database')):
                        report['health']=payload
                        break
                except (requests.RequestException,ValueError,KeyError,TypeError):
                    pass
                if time.monotonic() >= deadline:
                    report['status']='FAILED_READINESS_TIMEOUT'
                    return 1
                print('Menunggu kesehatan model/database ...',flush=True)
                time.sleep(min(config['api']['health_timeout_s'],max(0,deadline-time.monotonic())))
        for name,module in [('engine','scripts.smoke_pipeline'),('http','scripts.smoke_http')]:
            print('Memeriksa '+name+' dengan model nyata ...',flush=True)
            result=command([sys.executable,'-B','-m',module,'--out',str(output/name)],
                           env=env,log=output/(name+'.log'),timeout_s=timeout)
            report['commands'].append(result)
            save()
        report['passed']=all(r['status']=='PASS' for r in report['commands'])
        report['status']='LOCAL_CHECKS_PASSED' if report['passed'] else 'FAILED_LIVE_CHECKS'
        return 0 if report['passed'] else 1
    except Exception as exc:
        report['status']='FAILED_OPERATION'
        report['failure']={'category':type(exc).__name__,'message':str(exc)}
        return 1
    finally:
        if service is not None:
            try:
                if service.poll() is None:
                    service.terminate()  # Only our launcher; its trap stops its own children.
                service.wait(timeout=config['api']['health_timeout_s'])
                report['cleanup']='LAUNCHER_EXITED'
            except subprocess.TimeoutExpired:
                os.killpg(service.pid,signal.SIGKILL)
                service.wait()
                report['cleanup']='FORCED_OWN_PROCESS_GROUP'
            if service_log is not None:
                service_log.close()
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        save()
        print('Status: '+report['status']+'; bukti: '+str(output),flush=True)


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    selected=os.environ.get('PRISMA_CONFIG','config/local.cpu.yaml')
    name='verify-cpu-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex
    return run(load_config(selected),args.out or ROOT/'eval/runs'/name,config_path=selected)


if __name__ == '__main__':
    raise SystemExit(main())
