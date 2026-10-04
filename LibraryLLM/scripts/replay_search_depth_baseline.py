"""Replay original Top10 engine from pre-edit snapshot against unchanged index/catalogue."""
import importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
p=ROOT/'reports/search_depth_baseline/search/luminar_search.py'
spec=importlib.util.spec_from_file_location('search_depth_original_engine',p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
engine=module.LuminaRSearchEngine();after=json.loads((ROOT/'reports/search_depth_after_results.json').read_text(encoding='utf-8'));rows=[]
try:
 for entry in after['queries']:
  response=engine.search(entry['query'],top_k=10,diagnostics=True)
  actual=[x['work_id'] for x in response['results']];new=[x['work_id'] for x in entry['runs'][-1]['response']['results'][:10]]
  rows.append({'query':entry['query'],'original_top10_request':response,'after_top10_ids':new,'identical_order':actual==new,'overlap_count':len(set(actual)&set(new))})
  print(entry['query'],'identical',actual==new,'overlap',len(set(actual)&set(new)),flush=True)
finally:engine.close()
(ROOT/'reports/search_depth_original_top10_replay.json').write_text(json.dumps({'snapshot_source':str(p),'semantic_index_unchanged':True,'queries':rows},indent=2),encoding='utf-8')
