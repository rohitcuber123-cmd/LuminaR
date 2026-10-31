"""Gold-blind local capture; controlled model data never includes labels."""
from pathlib import Path
from dataclasses import asdict
from datetime import datetime,timezone
import json,hashlib,time
from scratch.search_proof8_local.control import parser,restricted_parse
from scratch.search_proof8_local.runner import run_local

R=Path('reports')
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def save(name,data):
    with (R/('search_proof8a2_'+name+'.json')).open('x',encoding='utf-8') as stream:json.dump(data,stream,indent=2,ensure_ascii=False)


def main():
    freeze=json.loads((R/'search_proof8a2_comparison_freeze.json').read_text(encoding='utf-8'))
    assert all(sha(p)==h for p,h in freeze['files'].items())
    cfg=json.loads((R/'search_proof8a2_configuration.json').read_text(encoding='utf-8'))
    save('prediction_started',{'at_utc':datetime.now(timezone.utc).isoformat(),'population':'DEVELOPMENT_ONLY','attempt':2,'gold_consulted':False,'model_revision':cfg['revision']})
    controls=[]
    for row in cfg['queries']:
        record={'id':row['id'],'query':row['query']}
        for name,call in [('deterministic',lambda:parser.validate(parser.parse_query(row['query'],['Fiction','History','Science']),{})),('restricted',lambda:restricted_parse(row['query'],['Fiction','History','Science']))]:
            started=time.perf_counter();p=call();record[name]={'plan':asdict(p),'decision':p.decision['decision_type'],'executable':parser.executable(p),'elapsed_ms':(time.perf_counter()-started)*1000}
        controls.append(record)
    save('control_predictions',{'records':controls,'population':'18exposed_development_queries','control':'Frozen7r1 carried forward; no semantic edits in standaloneV8 experiment'})
    with (R/'search_proof8a2_model_events.jsonl').open('x',encoding='utf-8') as stream:
        def emit(event):
            stream.write(json.dumps(event,ensure_ascii=False)+'\n');stream.flush()
            small={k:event[k] for k in ['event','id','phase','status','schema_source_valid','elapsed_ms','generation_ms','output_tokens','parent_received_elapsed_ms'] if k in event}
            print(json.dumps(small),flush=True)
        result=run_local(cfg,enabled=True,event_sink=emit,worker_script=Path('scripts/search_proof8a2_model_worker.py').resolve())
    save('model_capture',result)
    save('prediction_complete',{'at_utc':datetime.now(timezone.utc).isoformat(),'status':result['status'],'model_calls':result['model_calls'],'event_sha256':sha(R/'search_proof8a2_model_events.jsonl'),'fresh_acceptance':False,'source_frozen':all(sha(p)==h for p,h in freeze['files'].items())})
    print(json.dumps({'completed_status':result['status'],'model_calls':result['model_calls'],'peak_tree_RAM':result.get('peak_worker_tree_RSS_bytes')}),flush=True)


if __name__=='__main__':main()
