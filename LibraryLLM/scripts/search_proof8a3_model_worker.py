"""One ephemeral local evaluation worker, no server or application integration."""
import os,sys,json,time
from pathlib import Path


def main():
    # Trusted stdlib platform bootstrap runs BEFORE reading any query/config.
    # Windows platform may invoke the fixed read-only cmd /c ver probe.
    import platform
    platform.uname();platform.platform();platform.processor()
    os.environ['USER']='offline-extractor' # getpass must not fall back to Unix-only pwd on Windows
    cfg=json.loads(sys.stdin.readline());root=Path(__file__).resolve().parents[1]
    model_path=Path(cfg['model_path']).resolve()
    cache=Path(cfg['runtime_cache']).resolve()
    if cache.parent!=root/'scratch' or not cache.name.startswith('search_proof8_runtime_'):raise ValueError('Invalid runtime cache namespace')
    import tempfile
    tempfile.tempdir=str(cache)
    os.environ['TEMP']=os.environ['TMP']=str(cache)
    os.environ['TORCH_HOME']=str(cache/'torch')
    os.environ['HF_DEACTIVATE_ASYNC_LOAD']='1' # installed Transformers5 supports bounded sequential loading
    # Install before any runtime import. This is a bounded Python harness audit,
    # not an OS security sandbox against malicious installed native code.
    allowed=[Path(sys.base_prefix).resolve(),Path(sys.prefix).resolve(),root/'.venv',cache,model_path.parent.parent,root/'scratch/search_proof_recovery_v7r1',root/'scratch/search_proof8_local',root/'scratch/search_v2c_c5er/candidate_search_v4',root/'scripts']
    allowed_files={root/'scratch/__init__.py',root/'scratch/search_v2c_c5er/__init__.py',root/'scripts/__init__.py'}
    def audit(event,args):
        if event=='sqlite3.connect' and not (Path(str(args[0])).resolve()==cache or cache in Path(str(args[0])).resolve().parents):raise RuntimeError('Database connection outside isolated runtime cache denied')
        if event in ['os.remove','os.rename','os.mkdir','os.rmdir','os.truncate']:
            paths=args[:2] if event=='os.rename' else args[:1]
            if all(isinstance(x,(str,bytes,os.PathLike)) and (Path(os.fsdecode(x)).resolve()==cache or cache in Path(os.fsdecode(x)).resolve().parents) for x in paths):return
        if event in ['socket.connect','socket.bind','socket.getaddrinfo','subprocess.Popen','os.system','os.remove','os.rename','os.mkdir','os.rmdir','os.truncate']:raise RuntimeError('Offline worker forbids runtime operation: '+event+' '+str(args)[:300])
        if event=='import' and str(args[0]).split('.')[0] in ['search','backend','assistant','rag','pymongo']:raise RuntimeError('Application/database import denied: '+str(args[0]))
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            if os.fsdecode(args[0]).casefold()=='nul':return # Windows null device, no filesystem state
            p=Path(os.fsdecode(args[0])).resolve();mode,flags=args[1:3]
            writing=isinstance(mode,str) and any(x in mode for x in 'wax+') or isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)
            if writing and not (p==cache or cache in p.parents):raise RuntimeError('Worker file writes denied: '+str(p))
            if p not in allowed_files and not any(p==a or a in p.parents for a in allowed):raise RuntimeError('Worker read outside runtime/model/code allowlist: '+str(p))
    sys.addaudithook(audit)
    sys.path.insert(0,str(root))
    started=time.perf_counter()
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer,AutoConfig,GenerationConfig,StoppingCriteria,StoppingCriteriaList
    from accelerate import init_empty_weights,load_checkpoint_and_dispatch
    if not torch.cuda.is_available():raise RuntimeError('Audited CUDA runtime unavailable; no implicit CPU fallback')
    torch.set_num_threads(2);torch.manual_seed(0)
    device_total=torch.cuda.get_device_properties(0).total_memory
    torch.cuda.set_per_process_memory_fraction(cfg['gpu_memory_cap_bytes']/device_total)
    torch.cuda.reset_peak_memory_stats()
    tokenizer=AutoTokenizer.from_pretrained(str(model_path),local_files_only=True,trust_remote_code=False)
    from scratch.search_proof8_local.control import compact_ontology
    from scratch.search_proof_recovery_v7r1.extraction import validate_proposal
    prompt=cfg['prompt']+'\nAuthoritative ontology:'+json.dumps(compact_ontology(),separators=(',',':'))
    sizes=[]
    for row in cfg['queries']:
        messages=[{'role':'system','content':prompt},{'role':'user','content':json.dumps({'query':row['query']},ensure_ascii=False)}]
        encoded=tokenizer.apply_chat_template(messages,add_generation_prompt=True,tokenize=True,return_dict=True,return_tensors='pt')
        token_count=encoded['input_ids'].shape[-1]
        sizes.append({'id':row['id'],'input_tokens':token_count,'within_budget':token_count<=cfg['max_input_tokens']})
    print(json.dumps({'event':'input_budget_audit','records':sizes,'max_input_tokens':cfg['max_input_tokens'],'max_new_tokens':cfg['max_new_tokens']}),flush=True)
    if not all(x['within_budget'] for x in sizes):raise ValueError('Frozen prompt/input token budget exceeded')
    hf_config=AutoConfig.from_pretrained(str(model_path),local_files_only=True,trust_remote_code=False)
    with init_empty_weights(include_buffers=False):
        model=AutoModelForCausalLM.from_config(hf_config,dtype=torch.bfloat16,attn_implementation='eager')
    model.tie_weights()
    model=load_checkpoint_and_dispatch(model,str(model_path/'model.safetensors.index.json'),device_map={'':0},dtype=torch.bfloat16,offload_state_dict=False,offload_buffers=False,strict=True)
    model.tie_weights()
    if any(p.is_meta for p in model.parameters()):raise RuntimeError('Incomplete cached checkpoint load')
    model.generation_config=GenerationConfig.from_pretrained(str(model_path),local_files_only=True)

    model.eval();torch.cuda.synchronize()
    print(json.dumps({'event':'loaded','cold_process_startup_ms':(time.perf_counter()-started)*1000,'cuda_peak_allocated_bytes':torch.cuda.max_memory_allocated(),'cuda_peak_reserved_bytes':torch.cuda.max_memory_reserved(),'cuda_device_total_bytes':device_total,'gpu_memory_cap_bytes':cfg['gpu_memory_cap_bytes'],'weight_dtype':str(next(model.parameters()).dtype)}),flush=True)
    class Deadline(StoppingCriteria):
        def __init__(self,end):self.end=end
        def __call__(self,*a,**k):return time.perf_counter()>=self.end
    from concurrent.futures import ThreadPoolExecutor
    import threading,hashlib
    lock=threading.Lock()
    def infer(row,phase,submitted=None):
        submitted=time.perf_counter() if submitted is None else submitted
        query=row['query'];record={'event':'prediction','id':row['id'],'phase':phase}
        with lock:
            st=time.perf_counter();record['queue_wait_ms']=(st-submitted)*1000
            print(json.dumps({'event':'prediction_started','id':row['id'],'phase':phase}),flush=True)
            try:
                if len(query)>500:raise ValueError('Input exceeds500 characters')
                messages=[{'role':'system','content':prompt},{'role':'user','content':json.dumps({'query':query},ensure_ascii=False)}]
                inputs=tokenizer.apply_chat_template(messages,add_generation_prompt=True,tokenize=True,return_dict=True,return_tensors='pt')
                n=inputs['input_ids'].shape[-1]
                if n>cfg['max_input_tokens']:raise ValueError('Input token budget exceeded')
                record['tokenization_ms']=(time.perf_counter()-st)*1000
                generation_started=time.perf_counter()
                deadline=Deadline(generation_started+cfg['query_timeout_seconds'])
                with torch.inference_mode():
                    output=model.generate(**inputs.to('cuda'),do_sample=False,max_new_tokens=cfg['max_new_tokens'],stopping_criteria=StoppingCriteriaList([deadline]),pad_token_id=tokenizer.eos_token_id)
                torch.cuda.synchronize();record['generation_ms']=(time.perf_counter()-generation_started)*1000
                generated=output[0,n:];raw=tokenizer.decode(generated,skip_special_tokens=True)
                record.update(raw_output=raw,input_tokens=n,output_tokens=len(generated),status='CAPTURED',output_sha256=hashlib.sha256(raw.encode()).hexdigest())
                try:validate_proposal(query,raw);record['schema_source_valid']=True
                except Exception as e:record.update(schema_source_valid=False,validation_error=str(e))
                if time.perf_counter()>=deadline.end:record['status']='TIMEOUT_SAFE_REJECTION'
                elif len(generated)>=cfg['max_new_tokens'] and not record.get('schema_source_valid'):record['status']='OUTPUT_LIMIT_SAFE_REJECTION'
            except Exception as e:record.update(status='ERROR_SAFE_REJECTION',error_type=type(e).__name__,error=str(e))
            record.update(elapsed_ms=(time.perf_counter()-st)*1000,total_request_ms=(time.perf_counter()-submitted)*1000,cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(),cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved())
            print(json.dumps(record,ensure_ascii=False),flush=True)
            return record
    serial_start=time.perf_counter()
    for row in cfg['queries']:infer(row,'serial')
    print(json.dumps({'event':'serial_complete','count':len(cfg['queries']),'wall_ms':(time.perf_counter()-serial_start)*1000}),flush=True)
    # Two callers share ONE model and serialize generation; one waits in queue.
    submitted=time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(infer,row,'two_callers_one_model',submitted) for row in cfg['queries'][:2]]
        for job in jobs:job.result()
    print(json.dumps({'event':'concurrency_complete','callers':2,'model_instances':1,'active_generations':1,'queue_capacity':1,'wall_ms':(time.perf_counter()-submitted)*1000}),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as e:
        
        chain=[];current=e
        while current is not None and len(chain)<8:
            chain.append({'type':type(current).__name__,'error':str(current)})
            current=current.__cause__ or current.__context__
        print(json.dumps({'event':'worker_failure','type':type(e).__name__,'error':str(e),'exception_chain':chain}),flush=True)
        raise SystemExit(2)
