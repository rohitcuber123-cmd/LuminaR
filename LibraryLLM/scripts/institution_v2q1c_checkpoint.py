"""Continuation checkpoint; read-only deployed data and existing evidence."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,subprocess,sys,urllib.request
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.institution_v2p_baseline import capture_state,capture_indexes,communication_state

def main():
    target=ROOT/'reports/institution_v2q1c_checkpoint.json'
    assert not target.exists(),'Preserve the original continuation checkpoint'
    freeze=json.loads((ROOT/'reports/institution_v2q_ai_final_source_freeze.json').read_text(encoding='utf8'))
    source={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in freeze}
    reports={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'reports').glob('institution_v2q1*') if p.is_file() and not p.name.startswith('institution_v2q1c_')}
    state=capture_state()
    state['global_KG_metadata']={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in (ROOT/'knowledge_graph/data').glob('*') if p.is_file()}
    services={}
    for name,port in [('core',8002),('search',8003),('recommendation',8004),('rag',8005)]:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=3) as r:services[name]={'http_status':r.status,'body':json.load(r)}
        except Exception as e:services[name]={'error':type(e).__name__}
    before=ROOT/'.scratch/institution-v2q/continuation/before'
    for name in ['assistant/qwen.py','assistant/semantic.py','assistant/orchestrator.py','assistant/library_scope.py','assistant/profiling.py','rag/api.py','rag/qa.py']:
        copy=before/name;copy.parent.mkdir(parents=True,exist_ok=True);copy.write_bytes((ROOT/name).read_bytes())
    data={'captured_at':datetime.now(timezone.utc).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'tracked_status':subprocess.check_output(['git','status','--short','--untracked-files=no'],cwd=ROOT,text=True).splitlines(),
        'source_sha256':source,'prior_reports_sha256':reports,'dotenv_sha256':hashlib.sha256((ROOT/'.env').read_bytes()).hexdigest(),
        'state':state,'mongo_indexes':capture_indexes(),'communications':communication_state(),'services':services,
        'baseline_tests':{'backend':{'passed':3053,'failed':0,'skipped':20},'frontend':{'passed':1028,'failed':0,'skipped':0}},
        'classification':'Existing localhost deployment ownership remains UNKNOWN; disposable diagnostic environment will be explicit and separate.'}
    target.write_text(json.dumps(data,indent=2,default=str),encoding='utf8')
    reviewed=['institution_v2q1_completion.md','institution_v2q1_before_after.json','institution_v2q1_resumed_summary.json','institution_v2q1_resumed_browser.json',
        'institution_v2q1_query_inventory.json','institution_v2q1_performance.json','institution_v2q1_regression.json','institution_v2q1_preservation.json',
        'institution_v2q1_grounding_followup_proposal.md','institution_v2q1_global_search_probe.json','institution_v2q1_tenant_search_probe.json',
        'institution_v2q1_live_browser_observations.json','institution_v2q1_public_rag_results.json','institution_v2q1_public_rag_extended.json','institution_v2q1_public_rag_resumed.json']
    summary={'reviewed_evidence':{name:reports['reports/'+name] for name in reviewed},'rag_runs':[]}
    for name in ['institution_v2q1_public_rag_results.json','institution_v2q1_public_rag_extended.json','institution_v2q1_public_rag_resumed.json']:
        raw=json.loads((ROOT/'reports'/name).read_text(encoding='utf8'))
        summary['rag_runs'].append({'path':'reports/'+name,'run_id':raw['run_id'],'cases':len(raw['queries']),
            'llm_calls':[len(row.get('response',{}).get('profile',{}).get('llm_calls',[])) for row in raw['queries']]})
    (ROOT/'reports/institution_v2q1c_evidence_review.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps({'sources':len(source),'prior_reports':len(reports),'services':{n:v.get('http_status',v.get('error')) for n,v in services.items()},'rag_samples':sum(r['cases'] for r in summary['rag_runs'])}))

if __name__=='__main__':main()
