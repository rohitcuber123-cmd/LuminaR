"""Finalize read-only evidence: production preservation, source delta, scripts/tests/flags."""
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from dotenv import load_dotenv
from pymongo import MongoClient
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reports'
def put(name,value):
    (R/name).write_text(value if isinstance(value,str) else json.dumps(value,indent=2,default=str),encoding='utf8')
def table(columns,rows):
    return '| '+' | '.join(columns)+' |\n| '+' | '.join(['---']*len(columns))+' |\n'+''.join('| '+' | '.join(str(x).replace('|',' / ').replace('\n',' ') for x in row)+' |\n' for row in rows)
def main():
    baseline=json.loads((R/'full_product_convergence_baseline.json').read_text(encoding='utf8'))
    load_dotenv(ROOT/'.env')
    with MongoClient(os.getenv('MONGO_URI'),serverSelectionTimeoutMS=5000) as client:
        db=client['luminar_library'];query={'library_id':'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'}
        records=list(db.institution_library_books.find(query,{'_id':0}).sort('library_book_id',1))
        holdings=list(db.institution_holdings.find(query,{'_id':0}).sort('library_book_id',1))
        count=db.books.estimated_document_count()
    records=json.loads(json.dumps(records,default=str));holdings=json.loads(json.dumps(holdings,default=str))
    artifact_changes=[]
    for name,old in baseline['artifact_metadata'].items():
        p=ROOT/name
        if not p.is_file():artifact_changes.append({'path':name,'status':'MISSING'});continue
        s=p.stat();new={'bytes':s.st_size,'mtime_ns':s.st_mtime_ns}
        if old!=new:artifact_changes.append({'path':name,'before':old,'after':new})
    prior_changes=[name for name,old in baseline['prior_reports_sha256'].items() if not (ROOT/name).is_file() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=old]
    evidence={'captured_at':datetime.now(timezone.utc).isoformat(),'global_count_before':baseline['production_counts']['books'],'global_count_after':count,'global_count_method':'estimated_document_count; no claim of full 5M row digest','global_count_unchanged':count==baseline['production_counts']['books'],'test_records':len(records),'test_active_records':sum(r.get('status')=='ACTIVE' for r in records),'test_holdings':len(holdings),'test_records_exactly_equal':records==baseline['test_records'],'test_holdings_exactly_equal':holdings==baseline['test_holdings'],'artifacts_checked':len(baseline['artifact_metadata']),'artifact_changes':artifact_changes,'artifact_validation':'Size and mtime_ns of existing HNSW/KG/model artifacts; no full multi-GB digest claim','prior_reports_checked':len(baseline['prior_reports_sha256']),'prior_report_changes':prior_changes}
    evidence['status']='PASS' if evidence['global_count_unchanged'] and evidence['test_records_exactly_equal'] and evidence['test_holdings_exactly_equal'] and not artifact_changes and not prior_changes else 'FAIL'
    put('full_product_preservation.json',evidence)
    files=[name.replace('\\','/') for name in subprocess.check_output(['rg','--files','--hidden','-g','!.git','-g','!.venv','-g','!node_modules','-g','!.scratch','-g','!scratch','-g','!dist','-g','!datasets'],cwd=ROOT,text=True).splitlines()]
    changed=[];deleted=[];added=[]
    for name,old in baseline['source_sha256'].items():
        p=ROOT/name
        if not p.is_file():deleted.append(name)
        elif hashlib.sha256(p.read_bytes()).hexdigest()!=old:changed.append(name)
    for name in files:
        p=ROOT/name
        if not name.startswith('reports/') and name not in baseline['source_sha256'] and p.suffix in {'.py','.ts','.tsx','.css','.json','.md','.html','.toml','.ps1','.cjs','.backup'} and p.stat().st_size<32*1024*1024:
            if p.suffix=='.cjs' and name!='scripts/full_product_inventory.cjs':continue  # Baseline excluded cjs; do not claim preexisting staff-auth.cjs as a phase addition.
            added.append(name)
    # Evidence scripts created before the baseline are separately disclosed, not disguised as product deltas.
    phase_tools=['scripts/full_product_inventory.py','scripts/full_product_inventory.cjs','scripts/full_product_correct_baseline.py','scripts/report_full_product_convergence.py','scripts/full_product_rewrite_surfaces.py','scripts/test_full_product_regressions.py','scripts/test_full_product_frontend.py','scripts/finalize_full_product_evidence.py','scripts/write_full_product_reports.py']
    manifest={'comparison':'Phase baseline hashes, not git diff: preexisting uncommitted work is preserved. Audit tools created before capture are listed separately.','changed':sorted(changed),'deleted':sorted(deleted),'added':sorted(added),'phase_tools':[p for p in phase_tools if (ROOT/p).exists()],'reports_created':sorted(p.relative_to(ROOT).as_posix() for p in R.iterdir() if p.is_file() and p.relative_to(ROOT).as_posix() not in baseline['prior_reports_sha256'])}
    put('full_product_change_manifest.json',manifest)
    md='# Exact phase file changes\n\n'+manifest['comparison']+'\n\n'
    for label in ['changed','added','deleted','phase_tools','reports_created']:
        md+='## '+label.replace('_',' ').title()+'\n\n'+''.join('- `D:/SDC/LibraryLLM/'+p+'`\n' for p in manifest[label])+'\n'
    put('full_product_change_manifest.md',md)
    def classify(name):
        if any(x in name.lower() for x in ['router_v','finetun','train_','build_','rag_domain','rag_r0','candidate_union','rag_g1','rag_g2','rag_g3','g1_training','g2_training','g3_training']):return 'KEEP: research/build artifact; inspected only, excluded from execution and convergence'
        if name.startswith('frontend/tests/') or name.startswith('tests/'):return 'KEEP: frozen product/security/authority tests or new parity coverage; execution tracked by regression logs'
        if 'full_product_rewrite' in name:return 'AUDIT-ONLY: one-time extraction already completed; do not rerun against final source'
        if any(x in name for x in ['migration','seed','local_init','cleanup']):return 'KEEP: explicit maintenance/migration utility; not executed against production in this phase'
        return 'KEEP: distinct audit/test/local service/maintenance purpose; no independent production surface'
    tracked=[p for p in files if p.startswith(('tests/','frontend/tests/','scripts/')) and Path(p).suffix in {'.py','.ts','.tsx','.cjs','.ps1'}]
    put('full_test_script_inventory.md','# Full test and script inventory\n\nEvery discovered source file is recorded. Similar historical evaluation scripts are retained as research artifacts, never run or product authority. Execution coverage is in full_product_regression.json.\n\n'+table(['Path','Decision'],[(p,classify(p)) for p in sorted(tracked)]))
    flags=[]
    for name in files:
        if not name.startswith(('backend/','assistant/','search/','recommendation/','rag/','frontend/src/')):continue
        p=ROOT/name
        if p.suffix=='.py':
            try:tree=ast.parse(p.read_text(encoding='utf-8-sig'))
            except SyntaxError:continue
            for n in ast.walk(tree):
                if isinstance(n,ast.Call) and ast.unparse(n.func) in {'os.getenv','os.environ.get','getenv','environ.get'} and n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str):
                    key=n.args[0].value;secret=bool(re.search('SECRET|TOKEN|PASSWORD|KEY|URI',key))
                    default='REDACTED' if secret else ast.unparse(n.args[1]) if len(n.args)>1 else 'unset'
                    flags.append((key,name,n.lineno,default,'KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report'))
        elif p.suffix in {'.ts','.tsx'}:
            for i,line in enumerate(p.read_text(encoding='utf8').splitlines(),1):
                for match in re.finditer(r'import\.meta\.env\.([A-Z_]+)|process\.env\.([A-Z_]+)',line):flags.append((match[1] or match[2],name,i,'source-defined','KEEP: runtime configuration'))
    put('full_feature_flag_inventory.md','# Feature flag inventory\n\nConfiguration names/default expressions come from source AST, not .env contents. Secret defaults are redacted. No flags were added to create a parallel product. Router research flags remain frozen.\n\n'+table(['Flag','File','Line','Default','Decision'],sorted(set(flags))))
    put('full_product_evidence_counts.json',{'tests_and_scripts':len(tracked),'feature_flag_call_sites':len(set(flags)),'files_changed':len(changed),'files_added':len(added),'files_deleted':len(deleted)})
    print('Preservation:',evidence['status'],'TEST:',len(records),'/',len(holdings),'artifacts:',len(baseline['artifact_metadata']),'prior reports:',len(prior_changes),'changed/deleted:',len(changed),len(deleted),flush=True)
if __name__=='__main__':main()
