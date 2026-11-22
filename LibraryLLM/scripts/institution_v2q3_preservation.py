"""Compare live state read-only with the Part 2Q.1 observation checkpoint."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, subprocess, sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.institution_v2p_baseline import capture_state,capture_indexes,communication_state

def main():
    before=json.loads((ROOT/'reports/institution_v2q3_checkpoint.json').read_text(encoding='utf8'))
    state=capture_state()
    state['global_KG_metadata']={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in (ROOT/'knowledge_graph/data').glob('*') if p.is_file()}
    state=json.loads(json.dumps(state,default=str));indexes=json.loads(json.dumps(capture_indexes(),default=str));comms=communication_state()
    freeze=before['source_sha256']
    drift=[name for name,sha in freeze.items() if not (ROOT/name).exists() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha]
    checks={name:state.get(name)==value for name,value in before['state'].items()}
    expected_changes={'backend/routes/library_catalogue_experience.py', 'frontend/tests/assistant-library-scope.test.tsx', 'frontend/src/lib/assistantTypes.ts', 'backend/routes/books.py', 'assistant/orchestrator.py', 'assistant/schemas.py', 'frontend/src/components/assistant/AssistantTurn.tsx', 'assistant/qwen.py'}
    checks.update(mongo_indexes=indexes==before['mongo_indexes'],communications=comms==before['communications'],
        source_freeze_only_reviewed_change=set(drift)==expected_changes,rag_qa='rag/qa.py' not in drift, dotenv_sha256=hashlib.sha256((ROOT/'.env').read_bytes()).hexdigest()==before['dotenv_sha256'])
    for label,prefix in [('frontend_source','frontend/'),('backend_authority_source','backend/'),
                         ('native_search_source','search/'),('protected_rag_source','rag/')]:
        members=[name for name in freeze if name.startswith(prefix)]
        checks[label]=bool(members) and not any(name in drift and name not in expected_changes for name in members)
    baseline=before
    checks['head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==baseline['head']
    prior=before['prior_reports_sha256']
    prior={name:value for name,value in prior.items() if not name.endswith(('rag_restored_stdout.log','rag_restored_stderr.log'))}
    changed_reports=[name for name,sha in prior.items() if not (ROOT/name).exists() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha]
    checks['prior_reports']=not changed_reports
    result={'captured_at':datetime.now(timezone.utc).isoformat(),'result':'PASS' if all(checks.values()) else 'DRIFT_OBSERVED',
        'checks':checks,'source_drift':drift,'changed_prior_reports':changed_reports,'prior_report_count':len(prior),'state':state,'mongo_indexes':indexes,'communications':comms,
        'limits':'Read-only comparison against the immutable continuation checkpoint. Global large artifacts use size and mtime; global book count is estimated. Concurrent user activity is not reverted.',
        'actions':'No index rebuild, auth/telemetry activation, deployment or commit performed by this evaluation.'}
    (ROOT/'reports/institution_v2q3_preservation.json').write_text(json.dumps(result,indent=2,default=str),encoding='utf8')
    print(json.dumps({'result':result['result'],'failed_checks':[key for key,value in checks.items() if not value]}))

if __name__=='__main__':main()
