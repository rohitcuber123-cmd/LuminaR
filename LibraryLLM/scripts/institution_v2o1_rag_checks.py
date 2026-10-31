"""Controlled RAG behavior only; no private persistent document inspection."""
import ast,json,subprocess,sys,time,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
controlled=[];external=[]
tree=ast.parse((ROOT/'tests/test_urgent_document_rag.py').read_text())
for node in tree.body:
    if isinstance(node,ast.FunctionDef) and node.name.startswith('test_'):
        name='tests/test_urgent_document_rag.py::'+node.name
        (external if any(arg.arg=='actual_document' for arg in node.args.args) else controlled).append(name)
files=['tests/test_private_document_cache.py','tests/test_document_rag_latency.py','tests/test_rag_query_types.py','tests/test_rag_hard_negatives.py',
       'tests/test_document_knowledge.py','tests/test_knowledge_artifacts.py','tests/test_knowledge_tools_v2_1.py',
       'tests/institution_v2f/test_asset_recovery.py']
# v2f files use their own Mongo conftest; run separately to preserve established
# process isolation from unit suites that replace/import application modules.
groups=[('controlled_rag',[*files[:-1],*controlled]),('private_asset_isolation',[files[-1]])]
rows=[]
for label,targets in groups:
    xml=ROOT/f'reports/institution_v2o1_{label}.xml';at=time.perf_counter()
    with xml.with_suffix('.log').open('w',encoding='utf8') as out:
        p=subprocess.run([sys.executable,'-m','pytest',*targets,'-q','--junitxml='+str(xml)],cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,timeout=600)
    cases=list(ET.parse(xml).iter('testcase'));failed=sum(any(c.tag in {'failure','error'} for c in t) for t in cases);skip=sum(any(c.tag=='skipped' for c in t) for t in cases)
    rows.append({'group':label,'exit':p.returncode,'passed':len(cases)-failed-skip,'failed':failed,'skipped':skip,'seconds':time.perf_counter()-at,'targets':targets})
(ROOT/'reports/institution_v2o1_rag_behavior.json').write_text(json.dumps({'groups':rows,'controlled_fixture_only':True,'persistent_document_dependent_cases_not_selected':external,
    'explanation':'Targeted controlled-fixture validation, not a changed/skipped frozen test. Existing full product groups run independently and unsuppressed. No private document content is copied to reports.'},indent=2))
print(json.dumps([{k:v for k,v in row.items() if k!='targets'} for row in rows]))
raise SystemExit(any(r['exit'] for r in rows))
