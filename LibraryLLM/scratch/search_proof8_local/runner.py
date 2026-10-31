"""Disabled, one-model process-tree runner with CPU/GPU resource guards.

The extractor gets no tool authority. The parent runs a read-only nvidia-smi
monitor. Python audit hooks are not an OS sandbox for hostile native code.
"""
from pathlib import Path
import os,sys,json,subprocess,time,threading,queue
import psutil

_one=threading.BoundedSemaphore(1)


def gpu_row(line):
    total,free,used,util=[float(x.strip()) for x in line.split(',')]
    return {'total_bytes':int(total*1024**2),'free_bytes':int(free*1024**2),'used_bytes':int(used*1024**2),'utilization_percent':util}


def run_local(config,*,enabled=False,event_sink=None,worker_script=None,test_mode=False):
    if not enabled:return {'status':'DISABLED','records':[],'model_calls':0}
    if not _one.acquire(blocking=False):return {'status':'QUEUE_FULL_SAFE_REJECTION','records':[],'model_calls':0}
    root=Path(__file__).resolve().parents[2]
    script=Path(worker_script or root/'scripts/search_proof8_model_worker.py')
    if test_mode and not script.name.startswith('search_proof7_dummy_worker'):
        _one.release();raise ValueError('Test mode is limited to the frozen process test doubles')
    budget=config['worker_tree_memory_cap_bytes'];reserve=config['platform_RAM_reserve_bytes'];margin=config['startup_margin_bytes']
    records=[];stderr=[];telemetry=[];observed={};cpu_max={};reason=None;loaded_at=None;active_since=None
    child=None;gpu=None;start=time.perf_counter();peak_rss=0;lowest_ram=psutil.virtual_memory().available
    latest_gpu={};gpu_lock=threading.Lock();gpu_records=[];gpu_errors=[]
    def tree(p):
        try:return [p]+p.children(recursive=True)
        except psutil.NoSuchProcess:return []
    def stop(p):
        members=tree(p)
        for member in reversed(members):
            try:member.kill()
            except (psutil.NoSuchProcess,psutil.AccessDenied):pass
        psutil.wait_procs(members,timeout=5)
    def drain_gpu():
        for line in gpu.stdout:
            try:
                row=gpu_row(line);row['elapsed_ms']=(time.perf_counter()-start)*1000
                with gpu_lock:latest_gpu.update(row);gpu_records.append(row)
            except (ValueError,TypeError):gpu_errors.append(line[:1000])
    def emit(event):
        nonlocal loaded_at,active_since
        event['parent_received_elapsed_ms']=(time.perf_counter()-start)*1000
        records.append(event)
        if event.get('event')=='loaded':loaded_at=time.perf_counter()
        if event.get('event')=='prediction_started':active_since=time.perf_counter()
        if event.get('event')=='prediction':active_since=None
        if event_sink:event_sink(event)
    try:
        if psutil.virtual_memory().available < budget+reserve+margin:
            return {'status':'RESOURCE_PREFLIGHT_BLOCKED','records':[],'model_calls':0,'available_RAM_bytes':psutil.virtual_memory().available,'required_RAM_headroom_bytes':budget+reserve+margin}
        if not test_mode:
            gpu=subprocess.Popen(['nvidia-smi','--query-gpu=memory.total,memory.free,memory.used,utilization.gpu','--format=csv,noheader,nounits','-lms','500'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
            gpu_thread=threading.Thread(target=drain_gpu,daemon=True);gpu_thread.start()
            gpu_wait=time.perf_counter()
            while not latest_gpu and time.perf_counter()-gpu_wait<5:time.sleep(.05)
            if not latest_gpu:return {'status':'GPU_MONITOR_UNAVAILABLE','records':[],'model_calls':0}
            if latest_gpu['free_bytes']<config['gpu_memory_cap_bytes']+config['GPU_reserve_bytes']+config['GPU_startup_margin_bytes']:
                return {'status':'GPU_RESOURCE_PREFLIGHT_BLOCKED','records':[],'model_calls':0,'current_GPU':dict(latest_gpu)}
        whitelist={'SYSTEMROOT','WINDIR','PATH','TEMP','TMP','COMSPEC','USERPROFILE','LOCALAPPDATA'}
        env={k:v for k,v in os.environ.items() if k.upper() in whitelist}
        env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1',TOKENIZERS_PARALLELISM='false',CUDA_VISIBLE_DEVICES='0',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2')
        child=subprocess.Popen([sys.executable,'-I','-B',str(script)],cwd=root,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        child.stdin.write(json.dumps(config,ensure_ascii=False)+'\n');child.stdin.close()
        messages=queue.Queue()
        def drain(stream,label):
            for line in stream:messages.put((label,line.rstrip()))
        readers=[threading.Thread(target=drain,args=(child.stdout,'stdout'),daemon=True),threading.Thread(target=drain,args=(child.stderr,'stderr'),daemon=True)]
        for thread in readers:thread.start()
        process=psutil.Process(child.pid);previous_cpu=0;previous_time=time.perf_counter()
        while child.poll() is None:
            now=time.perf_counter()
            members=tree(process);rss=0
            for p in members:
                try:
                    observed[p.pid]=p;rss+=p.memory_info().rss
                    cpu=p.cpu_times();cpu_max[p.pid]=max(cpu_max.get(p.pid,0),cpu.user+cpu.system)
                except psutil.NoSuchProcess:pass
            cpu_total=sum(cpu_max.values());elapsed=max(now-previous_time,.0001)
            core_percent=max(0,100*(cpu_total-previous_cpu)/elapsed)
            previous_cpu=cpu_total;previous_time=now
            available=psutil.virtual_memory().available;lowest_ram=min(lowest_ram,available);peak_rss=max(peak_rss,rss)
            if len(telemetry)==0 or now-start-telemetry[-1]['elapsed_ms']/1000>=.5:
                telemetry.append({'elapsed_ms':(now-start)*1000,'worker_tree_RSS_bytes':rss,'platform_available_RAM_bytes':available,'CPU_core_percent':core_percent,'CPU_host_percent':core_percent/(psutil.cpu_count() or 1)})
            if rss>budget:reason='RAM_BUDGET_EXCEEDED'
            elif available<reserve:reason='PLATFORM_RAM_RESERVE_REACHED'
            elif not test_mode and latest_gpu.get('free_bytes',0)<config['GPU_reserve_bytes']:reason='GPU_RESERVE_REACHED'
            elif not test_mode and gpu.poll() is not None:reason='GPU_MONITOR_LOST'
            elif now-start>config['hard_timeout_seconds']:reason='HARD_TIMEOUT'
            elif loaded_at is None and now-start>config['startup_timeout_seconds']:reason='STARTUP_TIMEOUT'
            elif active_since and now-active_since>config['query_timeout_seconds']+config['query_timeout_grace_seconds']:reason='QUERY_HARD_TIMEOUT'
            if reason:stop(process);break
            while not messages.empty():
                label,line=messages.get()
                if label=='stdout':
                    try:
                        if len(line.encode('utf-8'))>65536:raise ValueError('Oversized worker event')
                        emit(json.loads(line))
                    except ValueError:stderr.append('Invalid worker event: '+line[:1000])
                elif line:stderr.append(line[:2000])
            time.sleep(.1)
        child.wait(timeout=10)
        for thread in readers:thread.join(timeout=2)
        while not messages.empty():
            label,line=messages.get()
            if label=='stdout':
                try:emit(json.loads(line))
                except ValueError:stderr.append(line[:1000])
            elif line:stderr.append(line[:2000])
        return {'status':reason or ('COMPLETED' if child.returncode==0 else 'WORKER_FAILED_SAFE_REJECTION'),'records':records,'stderr':stderr[-50:],
            'wall_ms':(time.perf_counter()-start)*1000,'peak_worker_tree_RSS_bytes':peak_rss,'minimum_available_RAM_bytes':lowest_ram,
            'worker_CPU_seconds':sum(cpu_max.values()),'process_tree_samples':telemetry,'GPU_samples':gpu_records,'GPU_monitor_errors':gpu_errors,
            'observed_process_ids':sorted(observed),'exit_code':child.returncode,'model_calls':sum(x.get('event')=='prediction' for x in records),
            'worker_instances':1,'resource_policy':{k:config[k] for k in ['worker_tree_memory_cap_bytes','platform_RAM_reserve_bytes','startup_margin_bytes','gpu_memory_cap_bytes','GPU_reserve_bytes','GPU_startup_margin_bytes','hard_timeout_seconds']},
            'test_mode':test_mode,'guards':'100ms process-tree/availableRAM polling;500ms globalGPU polling; CUDA allocator cap; whole-tree cleanup. Polling guards allow transient overshoot and are not OS quotas.'}
    finally:
        if child and child.poll() is None:
            try:stop(psutil.Process(child.pid))
            except psutil.NoSuchProcess:pass
        for p in observed.values():
            try:
                if p.is_running():stop(p)
            except psutil.NoSuchProcess:pass
        if gpu:
            gpu.terminate()
            try:gpu.wait(timeout=5)
            except subprocess.TimeoutExpired:gpu.kill();gpu.wait(timeout=5)
        _one.release()
