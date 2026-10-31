"""Bounded local child-process runner, disabled by default; no inference on import."""
from pathlib import Path
import os,sys,subprocess,json,time,threading,queue
import psutil

_one=threading.BoundedSemaphore(1)


def run_local(config,*,enabled=False,total_timeout_seconds=480,max_rss_bytes=2147483648,min_system_available_bytes=2147483648,worker_script=None):
    if not enabled:return {'status':'DISABLED','records':[],'model_calls':0}
    if not _one.acquire(blocking=False):return {'status':'QUEUE_FULL_SAFE_REJECTION','records':[],'model_calls':0}
    root=Path(__file__).resolve().parents[2]
    script=worker_script or root/'scripts/search_proof7r1_model_worker.py'
    observed_pids=set();observed_processes={}
    def tree(process):
        result=[process]
        try:result.extend(process.children(recursive=True))
        except psutil.NoSuchProcess:pass
        return result
    def stop_tree(process):
        descendants=tree(process)
        for member in reversed(descendants):
            try:member.kill()
            except (psutil.NoSuchProcess,psutil.AccessDenied):pass
        psutil.wait_procs(descendants,timeout=5)
    child=None;started=time.perf_counter();peak=0;records=[];errors=[];reason=None
    try:
        if psutil.virtual_memory().available<min_system_available_bytes+536870912:return {'status':'RESOURCE_PREFLIGHT_BLOCKED','records':[],'model_calls':0,'available_bytes':psutil.virtual_memory().available}
        allowed_env=['SystemRoot','WINDIR','PATH','TEMP','TMP','COMSPEC','USERPROFILE','LOCALAPPDATA']
        env={k:v for k,v in os.environ.items() if k.upper() in {x.upper() for x in allowed_env}}
        env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1',TOKENIZERS_PARALLELISM='false',CUDA_VISIBLE_DEVICES='0',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2')
        child=subprocess.Popen([sys.executable,'-I','-B',str(script)],cwd=root,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        child.stdin.write(json.dumps(config,ensure_ascii=False)+'\n');child.stdin.close()
        lines=queue.Queue()
        def drain(stream,label):
            for line in stream:lines.put((label,line.rstrip()))
        readers=[threading.Thread(target=drain,args=(child.stdout,'stdout'),daemon=True),threading.Thread(target=drain,args=(child.stderr,'stderr'),daemon=True)]
        for thread in readers:thread.start()
        process=psutil.Process(child.pid)
        while child.poll() is None:
            try:
                members=tree(process);observed_pids.update(p.pid for p in members);observed_processes.update((p.pid,p) for p in members)
                rss=sum(p.memory_info().rss for p in members if p.is_running());peak=max(peak,rss)
                if rss>max_rss_bytes:reason='RAM_BUDGET_EXCEEDED'
                elif psutil.virtual_memory().available<min_system_available_bytes:reason='PLATFORM_RAM_RESERVE_REACHED'
                elif time.perf_counter()-started>total_timeout_seconds:reason='HARD_TIMEOUT'
                if reason:stop_tree(process);break
            except psutil.NoSuchProcess:break
            while not lines.empty():
                label,line=lines.get()
                if label=='stdout':
                    try:records.append(json.loads(line))
                    except ValueError:errors.append(line[:2000])
                else:errors.append(line[:2000])
            time.sleep(.1)
        child.wait(timeout=10)
        for thread in readers:thread.join(timeout=2)
        while not lines.empty():
            label,line=lines.get()
            if label=='stdout':
                try:records.append(json.loads(line))
                except ValueError:errors.append(line[:2000])
            else:errors.append(line[:2000])
        return {'status':reason or ('COMPLETED' if child.returncode==0 else 'WORKER_FAILED_SAFE_REJECTION'),'records':records,'stderr':errors[-40:],'peak_worker_tree_rss_bytes':peak,'observed_process_ids':sorted(observed_pids),'budget_scope':'entire launcher/worker descendant tree','wall_ms':(time.perf_counter()-started)*1000,'exit_code':child.returncode,'concurrency':1,'queue_capacity':0,'hard_timeout_seconds':total_timeout_seconds,'max_rss_bytes':max_rss_bytes,'minimum_platform_available_bytes':min_system_available_bytes,'model_calls':sum(x.get('event')=='prediction' for x in records),'security_limit':'Python audit hooks and process budgets, not OS-level hostile-native-code containment.'}
    finally:
        if child and child.poll() is None:stop_tree(psutil.Process(child.pid));child.wait(timeout=10)
        for member in observed_processes.values():
            try:
                if member.is_running():stop_tree(member)
            except psutil.NoSuchProcess:pass
        _one.release()
