"""Reuse accepted K native workflows, replacing laboratory wrapping with the native seam.

No store or worker method is monkeypatched. The frozen baseline class is loaded
only for paired before measurements; all enabled runs use current native startup.
"""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2k_native_child.py').read_text(encoding='utf8')
source=source.replace('V2K','V2L').replace('v2k','v2l')


def replace(old,new):
    global source
    assert old in source,'Accepted native harness changed; review transformation'
    source=source.replace(old,new)


replace('from scratch.institution_v2l_telemetry.telemetry import Actor,Agent,COLLECTION,SLOT,digest',
    'from backend.services.library_worker_telemetry import COLLECTION,SLOT,digest\n'
    'from backend.services.library_worker_observer import configured_factory,ENABLE_ENV,URI_ENV,RestrictedWriter,NativeObserver,Configuration')
replace('from scratch.institution_v2l_telemetry.adapter import NativeAdapter','''BASELINE_NATIVE=os.environ.get('LUMINAR_V2L_BASELINE_NATIVE')=='1'
if BASELINE_NATIVE:
    import importlib.util
    spec=importlib.util.spec_from_file_location('luminar_v2l_frozen_native',ROOT/'.scratch/institution-v2l/before/search/library_intelligence.py')
    frozen=importlib.util.module_from_spec(spec);spec.loader.exec_module(frozen);TenantIntelligence=frozen.TenantIntelligence''')
replace("worker=TenantIntelligence(encode,model_version=store.MODEL+':native-v2l',fail=fail)",
    "os.environ[ENABLE_ENV]='1' if a.enabled else '0'\n"
    "    os.environ[URI_ENV]=os.environ['V2L_READER_URI'] if a.bad_writer else os.environ['V2L_TELEMETRY_URI']\n"
    "    options={'model_version':store.MODEL+':native-v2l','fail':fail}\n"
    "    if not BASELINE_NATIVE:options['observer_factory']=configured_factory(db.name)\n"
    "    worker=TenantIntelligence(encode,**options)\n"
    "    result.update(frozen_baseline_native=BASELINE_NATIVE,native_method_monkeypatching=False,extra_models=0)")
replace("    if a.enabled:\n        agent=Agent(lambda:Actor(os.environ['V2L_READER_URI'] if a.bad_writer else os.environ['V2L_TELEMETRY_URI'],db.name,worker.worker_id),worker.worker_id)\n    adapter=NativeAdapter(worker,store,agent) if agent else nullcontext()",
    '    adapter=nullcontext()')
replace('            worker.start()\n            if agent:agent.ready.wait(3)',
    "            import threading\n"
    "            result['threads_before_start']={'python':threading.active_count(),'os':proc.num_threads()}\n"
    "            result['mongo_connections_before']=mongo.admin.command('serverStatus')['connections']['current']\n"
    "            start_at=time.perf_counter();worker.start()\n"
    "            result['native_start_return_ms']=(time.perf_counter()-start_at)*1000\n"
    "            agent=getattr(worker,'observer',None)\n"
    "            if agent:agent.ready.wait(3)\n"
    "            result['observer_ready_ms']=(time.perf_counter()-start_at)*1000\n"
    "            result['threads_observing']={'python':threading.active_count(),'os':proc.num_threads()}\n"
    "            result['mongo_connections_observing']=mongo.admin.command('serverStatus')['connections']['current']")
replace('                for target in targets:',"                targets=targets*int(os.environ.get('LUMINAR_V2L_BENCH_REPETITIONS','1'))\n                for target in targets:")
replace("active_job=[None];first_fault=[False]", "observer_crash=[False];active_job=[None];first_fault=[False]")
replace("    def fail(stage):\n        if stage not in result['stages']:result['stages'].append(stage)",
    "    def fail(stage):\n"
    "        if stage not in result['stages']:result['stages'].append(stage)\n"
    "        if os.environ.get('LUMINAR_V2L_OBSERVER_CRASH')=='1' and stage=='EMBEDDING_BATCH':\n"
    "            observer_crash[0]=True;time.sleep(3)\n"
    "            result['injected_observer_failure']='Actual authenticated auxiliary actor raises at observer-loop boundary while native model build remains active.'")
replace("    if not BASELINE_NATIVE:options['observer_factory']=configured_factory(db.name)",
    "    if not BASELINE_NATIVE:\n"
    "        options['observer_factory']=configured_factory(db.name)\n"
    "        if os.environ.get('LUMINAR_V2L_OBSERVER_CRASH')=='1':\n"
    "            class ExplodingWriter(RestrictedWriter):\n"
    "                def __getattribute__(self,name):\n"
    "                    if name=='ownership_lost' and observer_crash[0]:raise RuntimeError('controlled observer loop exception')\n"
    "                    return super().__getattribute__(name)\n"
    "            def crashing_observer(owner):return NativeObserver(lambda:ExplodingWriter(Configuration(db.name,os.environ[URI_ENV]),owner),owner)\n"
    "            options['observer_factory']=crashing_observer")
replace("'lifecycle':c.get('lifecycle')}","'lifecycle':c.get('lifecycle'),'telemetry_enabled':bool(agent),\n"
    "                         'record_scope':'THIS_INSTANCE' if agent and agent.actor and c.get('instance_id')==agent.actor.instance_id else 'RETAINED_OTHER_INSTANCE_OR_ABSENT'}")
replace("'appName':'LuminaR-2K-prototype-telemetry'","'appName':RestrictedWriter.app_name")
replace("result['telemetry_fault_injected']='Actual server role revocation while native Search embedding active; native writer untouched.'\n                time.sleep(12)",
    "result['telemetry_fault_injected']='Actual server role revocation while native Search embedding active; native writer untouched.'\n"
    "                time.sleep(12)\n"
    "                old_pulses=agent.actor.metrics['pulse_write']\n"
    "                db.command('grantRolesToUser','fixture_telemetry',roles=[{'role':'fixture_telemetry_writer','db':db.name}])\n"
    "                reconnect_until=time.monotonic()+12\n"
    "                while agent.actor.metrics['pulse_write']<=old_pulses:\n"
    "                    assert time.monotonic()<reconnect_until,'Auxiliary writer did not reconnect'\n"
    "                    time.sleep(.1)\n"
    "                result['telemetry_reconnected_same_instance']=True")
replace("clib=seed(10);cr=", "clib=seed(10);repo.collection('libraries').update_one({'library_id':clib},{'$set':{'library_type':'PUBLIC_LIBRARY','access_mode':'PUBLIC'}});cr=")
replace('        worker.close()\n        if worker.thread:worker.thread.join(timeout=5)',
    "        close_at=time.perf_counter();worker.close()\n"
    "        result['native_close_return_ms']=(time.perf_counter()-close_at)*1000\n"
    "        if worker.thread:worker.thread.join(timeout=5)\n"
    "        result['worker_end_ms']=(time.perf_counter()-close_at)*1000\n"
    "        result['observer_thread_ended']=not agent or not agent.thread or not agent.thread.is_alive()\n"
    "        result['observer_final_state']=agent.state if agent else 'DISABLED'\n"
    "        result['mongo_connections_after_close']=mongo.admin.command('serverStatus')['connections']['current']")
# Resource sampling uses only this known child, never enumerates other processes.
replace("    def sample():\n        if not active_job[0]:return", """    resource_at=[0];resource_cpu=[time.process_time()]
    result['resource_samples']=[]
    def sample():
        tick=time.monotonic()
        if tick-resource_at[0]>=1:
            cpu=time.process_time();delta=(tick-resource_at[0]) if resource_at[0] else None
            result['resource_samples'].append({'phase':'JOB' if active_job[0] else 'IDLE','rss_bytes':proc.memory_info().rss,
                'cpu_delta_ms':(cpu-resource_cpu[0])*1000 if delta else None,'interval_seconds':delta,
                'python_threads':__import__('threading').active_count(),'os_threads':proc.num_threads()})
            resource_at[0]=tick;resource_cpu[0]=cpu
        if not active_job[0]:return""")
assert 'NativeAdapter' not in source and 'store.claim=' not in source
exec(compile(source,str(ROOT/'scripts/institution_v2k_native_child.py'),'exec'),{'__file__':str(Path(__file__).resolve()),'__name__':'__main__'})
