"""Run existing suites in their established isolated processes."""
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import json

ROOT = Path(__file__).resolve().parents[1]
groups={}
for group in ('unit','assistant','security','staff','notifications','circulation','search'):
    tree=ET.parse(ROOT/'reports'/f'assistant_stabilization_{group}.xml')
    groups[group]=sorted({t.attrib['classname'].replace('.','/')+'.py' for t in tree.iter('testcase')})
groups['knowledge']=['tests/test_document_knowledge.py','tests/test_knowledge_algorithms.py','tests/test_knowledge_quiz.py',
    'tests/test_knowledge_artifacts.py','tests/test_private_document_cache.py','tests/test_document_rag_latency.py']
results=[]
for name,files in groups.items():
    assert files and all((ROOT/f).exists() and 'router_v' not in f for f in files)
    with (ROOT/'reports'/f'knowledge_quality_regression_{name}.log').open('w',encoding='utf8') as out:
        r=subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),'-m','pytest',*files,'-q',
            f'--junitxml=reports/knowledge_quality_regression_{name}.xml'],cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,timeout=600)
    tree=ET.parse(ROOT/'reports'/f'knowledge_quality_regression_{name}.xml')
    cases=list(tree.iter('testcase'))
    results.append({'group':name,'exit':r.returncode,'tests':len(cases),
        'failed':sum(any(c.tag in {'failure','error'} for c in t) for t in cases),
        'skipped':sum(any(c.tag=='skipped' for c in t) for t in cases)})
    print(name,r.returncode,flush=True)
    (ROOT/'reports/knowledge_quality_regressions.json').write_text(json.dumps(results,indent=2),encoding='utf8')
