"""Freeze the resumed, standalone V8 local comparison before any predictions."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,subprocess,psutil,importlib.util,importlib.metadata as metadata

R=Path('reports')
def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def save(name,obj):
    with (R/('search_proof8a2_'+name+'.json')).open('x',encoding='utf-8') as stream:json.dump(obj,stream,indent=2,ensure_ascii=False)


def main():
    pre=json.loads((R/'search_proof8_preflight.json').read_text(encoding='utf-8'))
    source=json.loads((R/'search_proof7r1_source_freeze.json').read_text(encoding='utf-8'))
    assert all(sha(p)==h for p,h in source['files'].items())
    mem=psutil.virtual_memory()
    raw=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.free,memory.used,utilization.gpu,driver_version','--format=csv,noheader,nounits'],text=True).strip()
    name,total,free,used,util,driver=[s.strip() for s in raw.split(',')]
    total=int(float(total)*1024**2);free=int(float(free)*1024**2)
    reserve=2*1024**3;margin=512*1024**2
    budget=min(int(5.75*1024**3),(mem.available-reserve-margin)//(256*1024**2)*(256*1024**2))
    assert budget>=3*1024**3,'Current headroom no longer supports the measured startup requirement'
    gpu_reserve=1024**3;gpu_margin=128*1024**2;gpu_cap=min(int(.82*total),free-gpu_reserve-gpu_margin)
    assert gpu_cap>6*1024**3,'VRAM headroom no longer supports cached BF16 attempt'
    queries=[json.loads(s) for s in (R/'search_proof7_pilot_review_packet.jsonl').read_text(encoding='utf-8').splitlines()]
    old=json.loads((R/'search_proof7_comparison7_configuration.json').read_text(encoding='utf-8'))
    cache=Path('scratch/search_proof8_runtime_attempt2');cache.mkdir()
    cfg={'model_path':pre['model_path'],'revision':pre['model_revision'],'queries':queries,'prompt':old['prompt'],
        'runtime_cache':str(cache.resolve()),'max_input_tokens':4096,'max_new_tokens':768,'query_timeout_seconds':45,'query_timeout_grace_seconds':10,
        'hard_timeout_seconds':960,'startup_timeout_seconds':120,'worker_tree_memory_cap_bytes':budget,'platform_RAM_reserve_bytes':reserve,'startup_margin_bytes':margin,
        'gpu_memory_cap_bytes':gpu_cap,'GPU_reserve_bytes':gpu_reserve,'GPU_startup_margin_bytes':gpu_margin}
    processes=[]
    for p in psutil.process_iter(['pid','name','memory_info','cmdline']):
        try:
            args=p.info['cmdline'] or [];pname=p.info['name'].casefold()
            if 'python' in pname or any('luminar' in x.casefold() or 'libraryllm' in x.casefold() or 'uvicorn' in x.casefold() for x in args):
                processes.append({'pid':p.pid,'name':p.info['name'],'RSS_bytes':p.info['memory_info'].rss,'role_hint':next((Path(x).name for x in args if x.endswith('.py')),'not_identified')})
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    inventory={'at_utc':datetime.now(timezone.utc).isoformat(),'RAM':mem._asdict(),'GPU':{'name':name,'total_bytes':total,'free_bytes':free,'used_bytes':int(float(used)*1024**2),'utilization_percent':float(util),'driver':driver},
        'runtime_versions':{n:metadata.version(n) for n in ['torch','transformers','accelerate','safetensors','tokenizers','bitsandbytes']},
        'quantization_inventory':{n:bool(importlib.util.find_spec(n)) for n in ['bitsandbytes','auto_gptq','awq','llama_cpp','onnxruntime']},
        'checkpoint_format':'Unquantized BF16 safetensors,2shards;config torch_dtype=bfloat16; no artifact conversion or download',
        'application_process_memory':processes,'required_services_terminated':0,'resource_budget_justification':'Use current availableRAM minus2GiB reserve and0.5GiB startup/allocator margin; round down256MiB and cap5.75GiB after observed4GiB failure at4,392,308,736bytes. Disable Transformers asynchronous loading with the installed HF_DEACTIVATE_ASYNC_LOAD switch; same BF16 weights and prompt. Prior observed2.23GB startup makes3GiB minimum sensible but does not prove successful load. GPUcap separately min82%total,free minus1GiB reserve and128MiB margin. Guards remain active.',
        'scope':'Standalone local experiment; complete separate baseV8 prompt deferred per user clarification'}
    save('resource_inventory',inventory);save('configuration',cfg)
    files={**source['files']}
    extra=list(Path('scratch/search_proof8_local').glob('*.py'))+[Path('scripts/search_proof8a2_model_worker.py'),Path(__file__),R/'search_proof8a2_configuration.json',R/'search_proof8a2_resource_inventory.json',R/'search_proof7r1_pilot_frozen_development_view.jsonl',R/'search_proof7r1_pilot_contract_adjudication.json',R/'search_proof7_pilot_authored.jsonl',R/'search_proof7_pilot_independent_review.jsonl',R/'search_proof7_model_audit_verified.json']
    for path in extra:files[str(path)]=sha(path)
    # Scorers/predictors are appended by the caller before starting capture.
    for name in ['search_proof8a2_capture.py','search_proof8a2_score.py']:
        path=Path('scripts')/name;assert path.is_file();files[str(path)]=sha(path)
    save('comparison_freeze',{'candidate_id':'search-smarteng-disabled-proof-8-local','control_parser_version':'search-smarteng-disabled-proof-7r1','files':files,'population':'18independently_authored_reviewed_then_exposed_DEVELOPMENT_queries','typed_oracles':16,'execution_oracles':18,'fresh_acceptance':False,'semantic_control_changed':False,'model_revision':pre['model_revision'],'model_downloads':0,'training':False,'attempt':2})
    print(json.dumps({'available_RAM_bytes':mem.available,'worker_tree_cap_bytes':budget,'available_VRAM_bytes':free,'GPU_cap_bytes':gpu_cap,'frozen_files':len(files),'queries':len(queries)}))


if __name__=='__main__':main()
