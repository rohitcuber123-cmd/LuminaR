"""Capture non-secret source and service metadata without writing to live services."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, platform, subprocess, urllib.request

ROOT=Path(__file__).resolve().parents[1]
paths=['rag/llm.py','rag/qa.py','rag/api.py','assistant/api.py','assistant/qwen.py',
       'assistant/orchestrator.py','assistant/semantic.py','assistant/state.py','assistant/tools.py',
       'assistant/library_scope.py','search/api.py','search/luminar_search.py','search/index_manager.py',
       'backend/services/library_catalogue_experience.py','frontend/src/lib/assistant.ts']

def get(port,path):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}',timeout=10) as response:
            return {'status':response.status,'body':json.load(response)}
    except Exception as error:return {'error':f'{type(error).__name__}: {error}'}

def main():
    freeze=json.loads((ROOT/'reports/institution_v2q_ai_final_source_freeze.json').read_text(encoding='utf8'))
    source={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in paths}
    drift=[name for name,sha in freeze.items() if not (ROOT/name).exists() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha]
    gpu=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.free,utilization.gpu','--format=csv,noheader'],capture_output=True,text=True)
    data={'captured_at':datetime.now(timezone.utc).isoformat(),
        'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'tracked_status':subprocess.check_output(['git','status','--short','--untracked-files=no'],cwd=ROOT,text=True).splitlines(),
        'source_sha256':source,'drift_from_2q_source_freeze':drift,
        'services':{'core':get(8002,'/health'),'search':get(8003,'/health'),'rag':get(8005,'/health')},
        'platform':platform.platform(),'python':platform.python_version(),'gpu_snapshot':gpu.stdout.strip() if gpu.returncode==0 else 'unavailable',
        'configured_models':{'qwen':'Qwen/Qwen2.5-3B-Instruct',
            'qwen_cache_snapshot_observed':'aa8e72537993ba99e69dfaafa59ed015b17504d1 (cache observed; loaded revision not independently verified)',
            'qwen_config_max_position_embeddings':32768,'qwen_cuda_quantization':'4-bit NF4, double quantization, float16 compute when CUDA branch is used',
            'generation':'do_sample=False; temperature and top_p arguments are unused when sampling is disabled; default 256 tokens, assistant gateway 180 structured / 160 prose',
            'embedding':'all-MiniLM-L6-v2, 384 dimensions','reranker':'cross-encoder/ms-marco-MiniLM-L-6-v2',
            'global_search':'HNSW efSearch=128; rerank depth=50; max returned=50; rerank batch=16'},
        'historical_2q_tests':{'backend':'3050 passed, 0 failed, 20 skipped','frontend':'1028 passed, 0 failed, 0 skipped'},
        'note':'Historical counts are not a fresh Part 2Q.1 regression result. No credentials or private document content captured.'}
    (ROOT/'reports/institution_v2q1_baseline.json').write_text(json.dumps(data,indent=2),encoding='utf8')
    print(json.dumps({'source_drift':drift,'search':data['services']['search'].get('body',{}).get('index_status'),
        'rag':data['services']['rag'].get('body',{}).get('status')}))

if __name__=='__main__':main()
