"""One ephemeral local evaluation worker, no server or application integration."""
import os,sys,json,time
from pathlib import Path


def main():
    cfg=json.loads(sys.stdin.readline());root=Path(__file__).resolve().parents[1]
    model_path=Path(cfg['model_path']).resolve()
    # Install before any runtime import. This is a bounded Python harness audit,
    # not an OS security sandbox against malicious installed native code.
    allowed=[Path(sys.base_prefix).resolve(),Path(sys.prefix).resolve(),root/'.venv',model_path.parent.parent,root/'scratch/search_proof_recovery_v7',root/'scratch/search_v2c_c5er/candidate_search_v4',root/'scripts']
    allowed_files={root/'scratch/__init__.py',root/'scratch/search_v2c_c5er/__init__.py',root/'scripts/__init__.py'}
    def audit(event,args):
        if event in ['socket.connect','socket.bind','socket.getaddrinfo','subprocess.Popen','os.system','os.remove','os.rename','os.mkdir','os.rmdir','os.truncate']:raise RuntimeError('Offline worker forbids network/tool/process operations')
        if event=='import' and str(args[0]).split('.')[0] in ['search','backend','assistant','rag','pymongo','sqlite3']:raise RuntimeError('Application/database import denied')
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            p=Path(os.fsdecode(args[0])).resolve();mode,flags=args[1:3]
            writing=isinstance(mode,str) and any(x in mode for x in 'wax+') or isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)
            if writing:raise RuntimeError('Worker file writes denied')
            if p not in allowed_files and not any(p==a or a in p.parents for a in allowed):raise RuntimeError('Worker read outside runtime/model/code allowlist: '+str(p))
    sys.addaudithook(audit)
    sys.path.insert(0,str(root))
    started=time.perf_counter()
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer,StoppingCriteria,StoppingCriteriaList
    if not torch.cuda.is_available():raise RuntimeError('Audited CUDA runtime unavailable; no implicit CPU fallback')
    torch.set_num_threads(2);torch.cuda.set_per_process_memory_fraction(.82)
    torch.cuda.reset_peak_memory_stats()
    tokenizer=AutoTokenizer.from_pretrained(str(model_path),local_files_only=True,trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(str(model_path),local_files_only=True,trust_remote_code=False,dtype=torch.bfloat16,device_map='cuda',attn_implementation='eager')
    model.eval();torch.cuda.synchronize()
    print(json.dumps({'event':'loaded','cold_load_ms':(time.perf_counter()-started)*1000,'cuda_peak_allocated_bytes':torch.cuda.max_memory_allocated(),'cuda_peak_reserved_bytes':torch.cuda.max_memory_reserved()}),flush=True)
    from scratch.search_proof_recovery_v7.ontology import manifest
    from scratch.search_proof_recovery_v7.extraction import validate_proposal
    prompt=cfg['prompt']+'\nAuthoritative ontology:'+json.dumps(manifest(),separators=(',',':'))
    class Deadline(StoppingCriteria):
        def __init__(self,end):self.end=end
        def __call__(self,*a,**k):return time.perf_counter()>=self.end
    for row in cfg['queries']:
        query=row['query'];st=time.perf_counter();record={'event':'prediction','id':row['id']}
        try:
            if len(query)>500:raise ValueError('Input exceeds500 characters')
            messages=[{'role':'system','content':prompt},{'role':'user','content':json.dumps({'query':query},ensure_ascii=False)}]
            inputs=tokenizer.apply_chat_template(messages,add_generation_prompt=True,tokenize=True,return_dict=True,return_tensors='pt')
            n=inputs['input_ids'].shape[-1]
            if n>cfg['max_input_tokens']:raise ValueError('Input token budget exceeded')
            deadline=Deadline(time.perf_counter()+cfg['query_timeout_seconds'])
            with torch.inference_mode():
                output=model.generate(**inputs.to('cuda'),do_sample=False,max_new_tokens=cfg['max_new_tokens'],stopping_criteria=StoppingCriteriaList([deadline]),pad_token_id=tokenizer.eos_token_id)
            torch.cuda.synchronize();generated=output[0,n:];raw=tokenizer.decode(generated,skip_special_tokens=True)
            record.update(raw_output=raw,input_tokens=n,output_tokens=len(generated),status='CAPTURED')
            try:validate_proposal(query,raw);record['schema_source_valid']=True
            except Exception as e:record.update(schema_source_valid=False,validation_error=str(e))
            if time.perf_counter()>=deadline.end:record['status']='TIMEOUT_SAFE_REJECTION'
        except Exception as e:record.update(status='ERROR_SAFE_REJECTION',error_type=type(e).__name__,error=str(e))
        record.update(elapsed_ms=(time.perf_counter()-st)*1000,cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(),cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved())
        print(json.dumps(record,ensure_ascii=False),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'event':'worker_failure','type':type(e).__name__,'error':str(e)}),flush=True)
        raise SystemExit(2)
