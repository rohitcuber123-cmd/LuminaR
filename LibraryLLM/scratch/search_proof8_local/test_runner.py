from pathlib import Path
from types import SimpleNamespace
import psutil,pytest
from . import runner

ROOT=Path(__file__).resolve().parents[2]
DUMMY=ROOT/'scripts/search_proof7_dummy_worker.py'


def cfg(**kw):
    return {'worker_tree_memory_cap_bytes':256*1024**2,'platform_RAM_reserve_bytes':0,'startup_margin_bytes':0,'gpu_memory_cap_bytes':0,'GPU_reserve_bytes':0,'GPU_startup_margin_bytes':0,'hard_timeout_seconds':5,'startup_timeout_seconds':5,'query_timeout_seconds':1,'query_timeout_grace_seconds':1,**kw}


def test_gpu_monitor_units():
    r=runner.gpu_row('8151, 7899, 252, 0')
    assert r['free_bytes']==7899*1024**2 and r['utilization_percent']==0
    with pytest.raises(ValueError):runner.gpu_row('N/A')


def test_disabled_does_not_start():
    assert runner.run_local({},enabled=False)['status']=='DISABLED'


def test_one_full_instance_only():
    assert runner._one.acquire(False)
    try:assert runner.run_local({},enabled=True)['status']=='QUEUE_FULL_SAFE_REJECTION'
    finally:runner._one.release()


def test_test_mode_not_available_to_model_worker():
    with pytest.raises(ValueError):runner.run_local(cfg(),enabled=True,test_mode=True,worker_script=ROOT/'scripts/search_proof8_model_worker.py')


def test_preflight_reserves_memory(monkeypatch):
    monkeypatch.setattr(runner.psutil,'virtual_memory',lambda:SimpleNamespace(available=0))
    r=runner.run_local(cfg(),enabled=True,test_mode=True,worker_script=DUMMY)
    assert r['status']=='RESOURCE_PREFLIGHT_BLOCKED'


def test_capture_telemetry_and_event_sink():
    events=[]
    r=runner.run_local(cfg(),enabled=True,test_mode=True,worker_script=DUMMY,event_sink=events.append)
    assert r['status']=='COMPLETED' and events[0]['event']=='test_double'
    assert r['process_tree_samples'] and not any(psutil.pid_exists(pid) for pid in r['observed_process_ids'])


def test_startup_timeout_cleans_tree():
    r=runner.run_local(cfg(sleep=2,startup_timeout_seconds=.15),enabled=True,test_mode=True,worker_script=DUMMY)
    assert r['status']=='STARTUP_TIMEOUT'
    assert not any(psutil.pid_exists(pid) for pid in r['observed_process_ids'])


def test_hard_memory_limit_cleans_tree():
    r=runner.run_local(cfg(sleep=2,worker_tree_memory_cap_bytes=1),enabled=True,test_mode=True,worker_script=DUMMY)
    assert r['status']=='RAM_BUDGET_EXCEEDED'
    assert not any(psutil.pid_exists(pid) for pid in r['observed_process_ids'])


def test_descendant_cleanup_on_hard_timeout():
    r=runner.run_local(cfg(hard_timeout_seconds=.6),enabled=True,test_mode=True,worker_script=ROOT/'scripts/search_proof7_dummy_worker_tree.py')
    assert r['status']=='HARD_TIMEOUT' and len(r['observed_process_ids'])>=2
    assert not any(psutil.pid_exists(pid) for pid in r['observed_process_ids'])
