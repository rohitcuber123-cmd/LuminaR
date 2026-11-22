"""Read-only final comparison against the preimplementation Part 2Q checkpoint."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.institution_v2p_baseline import capture_state, capture_indexes, communication_state

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    baseline=json.loads((ROOT/'reports/institution_v2q_baseline.json').read_text(encoding='utf8'))
    state=capture_state()
    state['global_KG_metadata']={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in (ROOT/'knowledge_graph/data').glob('*') if p.is_file()}
    indexes=json.loads(json.dumps(capture_indexes(),default=str))
    communications=communication_state()
    state=json.loads(json.dumps(state,default=str))
    changes={n:{'before':h,'after':sha(ROOT/n) if (ROOT/n).exists() else None} for n,h in baseline['source_sha256'].items() if not (ROOT/n).exists() or sha(ROOT/n)!=h}
    reports={n:{'before':h,'after':sha(ROOT/n) if (ROOT/n).exists() else None} for n,h in baseline['reports_sha256'].items() if not n.startswith('reports/institution_v2q') and (not (ROOT/n).exists() or sha(ROOT/n)!=h)}
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    checks={k:state.get(k)==v for k,v in baseline['state'].items()}
    checks.update(mongo_indexes=indexes==baseline['mongo_indexes'],communications=communications==baseline['communication_state'],head=head==baseline['head'],prior_reports=not reports)
    allowed={
        'assistant/orchestrator.py','assistant/schemas.py','assistant/state.py','assistant/tools.py',
        'backend/routes/library_catalogue_experience.py','backend/services/library_catalogue_experience.py',
        'frontend/package.json','frontend/src/components/AIChatWidget.tsx','frontend/src/components/AssistantLibraryRequestButton.tsx',
        'frontend/src/components/BookPersonalActions.tsx','frontend/src/components/assistant/AssistantTurn.tsx','frontend/src/index.css',
        'frontend/src/lib/assistant.ts','frontend/src/lib/assistantTypes.ts','frontend/src/lib/libraryCatalogue.ts',
        'frontend/src/pages/LibraryCatalogue.tsx','frontend/src/store/useAssistantStore.ts','scripts/institution_v2q_checks.py'}
    checks['only_scoped_existing_source_changes']=set(changes)<=allowed
    checks['all_original_tests_unchanged']=not any(n.startswith('tests/') or n.startswith('frontend/tests/') for n in changes)
    names=subprocess.check_output(['rg','--files','--hidden','-g','!.git','-g','!.venv','-g','!node_modules','-g','!.scratch','-g','!scratch','-g','!dist','-g','!datasets','-g','!reports'],cwd=ROOT,text=True).splitlines()
    new_sources={Path(n).as_posix() for n in names if Path(n).suffix in {'.py','.ts','.tsx','.css','.json','.md','.html','.toml','.ps1','.mjs','.cjs'} and Path(n).as_posix() not in baseline['source_sha256']}
    expected_new={'assistant/library_scope.py','tests/test_assistant_library_scope.py','tests/institution_v2q_ai/conftest.py','tests/institution_v2q_ai/test_integration.py','frontend/tests/assistant-library-scope.test.tsx','scripts/institution_v2q_ai_checks.py','scripts/institution_v2q_ai_browser.py','scripts/institution_v2q_ai_preservation.py','scripts/institution_v2q_ai_report.py'}
    checks['only_expected_new_source_files']=new_sources==expected_new
    for name in ['assistant/api.py','rag/qa.py','frontend/src/lib/api.ts','frontend/src/lib/institutions.ts','frontend/src/lib/libraryIntelligence.ts']:
        checks[name]=sha(ROOT/name)==baseline['source_sha256'][name]
    data={'captured_at':datetime.now(timezone.utc).isoformat(),'result':'PASS' if all(checks.values()) else 'FAIL',
        'checks':checks,'state':state,'mongo_indexes':indexes,'communication_state':communications,
        'head':head,'existing_source_changes':changes,'new_source_files':sorted(new_sources),'unexpected_new_source_files':sorted(new_sources-expected_new),'changed_prior_reports':reports,
        'evidence_limits':'Large global artifacts compared by size/mtime; no 5M scan or rebuild. Private registries compared read-only logical digests. Existing source compared byte SHA256. Deployment classified UNKNOWN; no deployment writes performed.',
        'actions':{'global_hnsw_rebuilt':False,'global_kg_rebuilt':False,'tenant_auto_rebuild':False,'production_auth_changed':False,'production_telemetry_enabled':False,'protected_rag_modified':False,'deployed':False,'committed':False}}
    (ROOT/'reports/institution_v2q_ai_preservation.json').write_text(json.dumps(data,indent=2,default=str),encoding='utf8')
    print(json.dumps({'result':data['result'],'failed_checks':[k for k,v in checks.items() if not v],'changed_prior_reports':list(reports),'existing_source_changes':len(changes)}))

if __name__=='__main__':main()
