"""SYNTHETIC orchestration tests; never launch services or install software."""
import json
import socket

import pytest

from backend.app.config import load_config


def test_socket_rejection_does_not_rebuild_or_start_services(tmp_path, monkeypatch):
    from scripts import verify_local
    def denied(config):
        raise PermissionError('SYNTHETIC: local socket forbidden')
    monkeypatch.setattr(verify_local,'check_ports',denied)
    monkeypatch.setattr(verify_local,'command',lambda *a,**kw: pytest.fail('must not run commands'))
    cfg=load_config('config/local.cpu.yaml')
    assert verify_local.run(cfg,tmp_path/'run') == 1
    report=json.loads((tmp_path/'run/summary.json').read_text())
    assert report['status'] == 'BLOCKED_LOCAL_PORTS' and report['commands'] == []


def test_existing_run_is_not_overwritten(tmp_path):
    from scripts import verify_local
    with pytest.raises(FileExistsError):
        verify_local.run(load_config('config/local.cpu.yaml'),tmp_path)


def test_preflight_checks_configured_ports_without_listening(monkeypatch):
    from scripts import verify_local
    bound=[]
    class Probe:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def bind(self,address): bound.append(address)
    monkeypatch.setattr(socket,'socket',lambda *a,**kw:Probe())
    cfg=load_config('config/local.cpu.yaml')
    verify_local.check_ports(cfg)
    assert bound == [(cfg[k]['host'],cfg[k]['port']) for k in ('frontend','api','llama_cpp')]


def test_baseline_gpu_is_not_implicitly_launched(tmp_path):
    from scripts import verify_local
    with pytest.raises(ValueError,match='CPU'):
        verify_local.run(load_config('config/config.yaml'),tmp_path/'run')


@pytest.mark.parametrize('ambient',['config/config.yaml','config/local.cpu.yaml'])
def test_mock_backend_suite_uses_baseline_without_changing_live_cpu_profile(tmp_path, monkeypatch, ambient):
    from scripts import verify_local
    from backend.app.config import ROOT
    seen=[]
    monkeypatch.setenv('PRISMA_CONFIG',ambient)
    monkeypatch.setattr(verify_local,'check_ports',lambda cfg:None)
    def capture(argv, *, env, log, timeout_s):
        seen.append((argv,env['PRISMA_CONFIG']))
        return {'argv':argv,'status':'FAIL' if argv[:2] == ['make','test'] else 'PASS','exit_code':1,
                'log':str(log),'duration_s':0}
    monkeypatch.setattr(verify_local,'command',capture)
    cfg=load_config('config/local.cpu.yaml')
    assert verify_local.run(cfg,tmp_path/'run') == 1
    backend=[profile for argv,profile in seen if argv[:2] == ['make','test']]
    assert backend == [str(ROOT/'config/config.yaml')]
    assert all(profile == str(ROOT/'config/local.cpu.yaml') for argv,profile in seen if argv[0] == 'npm')
    assert cfg['sampling']['n_samples'] == 8
