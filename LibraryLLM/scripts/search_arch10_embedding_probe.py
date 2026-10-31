"""Guard only this probe child. Never terminates unrelated processes."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scratch.search_architecture_v10.sandbox import run_local

if __name__=='__main__':
    result=run_local({},enabled=True,total_timeout_seconds=60,max_rss_bytes=2_147_483_648,
        min_system_available_bytes=1_073_741_824,worker_script=Path(__file__).with_name('search_arch10_embedding_probe_worker.py'))
    tag=sys.argv[1] if len(sys.argv)>1 else ''
    assert not tag or tag.isalnum()
    with Path('reports/search_arch10_embedding_probe'+tag+'.json').open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:result.get(k) for k in ['status','wall_ms','peak_worker_tree_rss_bytes','stderr']}))
