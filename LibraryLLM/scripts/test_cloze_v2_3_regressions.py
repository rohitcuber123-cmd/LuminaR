"""Isolated frozen regressions; no Router research runs or source edits."""
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import json

ROOT=Path(__file__).resolve().parents[1]
groups={}
for name in ('unit','assistant','security','staff','notifications','circulation','search'):
    tree=ET.parse(ROOT/'reports'/f'assistant_stabilization_{name}.xml')
    groups[name]=sorted({t.attrib['classname'].replace('.','/')+'.py' for t in tree.iter('testcase')})
groups['kg']=['tests/test_kg_product.py','tests/test_kg_topics.py']
results=[]
for name,files in groups.items():
    assert all((ROOT/f).exists() and 'router_v' not in f for f in files)
    with (ROOT/'reports'/f'cloze_v2_3_regression_{name}.log').open('w',encoding='utf8') as out:
        run=subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),'-m','pytest',*files,'-q',f'--junitxml=reports/cloze_v2_3_regression_{name}.xml'],cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,timeout=600)
    tree=ET.parse(ROOT/'reports'/f'cloze_v2_3_regression_{name}.xml');cases=list(tree.iter('testcase'))
    results.append({'group':name,'exit':run.returncode,'tests':len(cases),'failed':sum(any(c.tag in {'failure','error'} for c in t) for t in cases),'skipped':sum(any(c.tag=='skipped' for c in t) for t in cases)})
    (ROOT/'reports/cloze_v2_3_regression_groups.json').write_text(json.dumps(results,indent=2),encoding='utf8');print(name,run.returncode,flush=True)

