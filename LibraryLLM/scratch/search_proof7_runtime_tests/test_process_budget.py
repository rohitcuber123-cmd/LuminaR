from pathlib import Path
from types import SimpleNamespace
from scripts import search_proof7_process_budget as sandbox

DUMMY=Path(__file__).resolve().parents[2]/'scripts/search_proof7_dummy_worker.py'


def test_disabled_runner_does_not_spawn():
    assert sandbox.run_local({},enabled=False)['status']=='DISABLED'


def test_queue_is_bounded_without_waiting():
    assert sandbox._one.acquire(blocking=False)
    try:assert sandbox.run_local({},enabled=True)['status']=='QUEUE_FULL_SAFE_REJECTION'
    finally:sandbox._one.release()


def test_resource_preflight_is_safe(monkeypatch):
    monkeypatch.setattr(sandbox.psutil,'virtual_memory',lambda:SimpleNamespace(available=0))
    assert sandbox.run_local({},enabled=True)['status']=='RESOURCE_PREFLIGHT_BLOCKED'


def test_process_completion_and_output_capture():
    r=sandbox.run_local({},enabled=True,worker_script=DUMMY,min_system_available_bytes=0)
    assert r['status']=='COMPLETED' and r['records'][0]['event']=='test_double'


def test_hard_timeout_kills_child():
    r=sandbox.run_local({'sleep':2},enabled=True,worker_script=DUMMY,total_timeout_seconds=.15,min_system_available_bytes=0)
    assert r['status']=='HARD_TIMEOUT' and r['exit_code']!=0


def test_hard_memory_budget_kills_child():
    r=sandbox.run_local({'sleep':2},enabled=True,worker_script=DUMMY,max_rss_bytes=1,min_system_available_bytes=0)
    assert r['status']=='RAM_BUDGET_EXCEEDED' and r['exit_code']!=0


def test_timeout_cleans_descendant_tree():
    import psutil
    script=DUMMY.with_name('search_proof7_dummy_worker_tree.py')
    result=sandbox.run_local({},enabled=True,worker_script=script,total_timeout_seconds=.6,min_system_available_bytes=0)
    assert result['status']=='HARD_TIMEOUT'
    assert len(result['observed_process_ids'])>=2
    assert not any(psutil.pid_exists(pid) for pid in result['observed_process_ids'])
