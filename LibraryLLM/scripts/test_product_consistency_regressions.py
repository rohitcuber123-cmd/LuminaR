"""Run frozen product suites in isolated processes; exclude Router V1-V5 research."""
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
groups = {}
for name in ('unit', 'assistant', 'security', 'staff', 'notifications', 'circulation', 'search'):
    tree = ET.parse(ROOT / 'reports' / f'assistant_stabilization_{name}.xml')
    groups[name] = sorted({t.attrib['classname'].replace('.', '/') + '.py' for t in tree.iter('testcase')})
groups['private_knowledge_ocr'] = ['tests/test_private_document_cache.py', 'tests/test_private_preparation_status.py',
    'tests/test_document_knowledge.py', 'tests/test_knowledge_artifacts.py', 'tests/test_knowledge_quiz.py',
    'tests/test_knowledge_tools_v2_1.py', 'tests/test_quiz_v2_2.py', 'tests/test_cloze_v2_3.py']
groups['kg'] = ['tests/test_kg_product.py', 'tests/test_kg_topics.py', 'tests/test_knowledge_graph.py']
groups.update({f'institution_{version}': [f'tests/institution_{version}'] for version in ['v1','v2a','v2b','v2c']})
groups['workspace_authorization'] = ['tests/frontend_workspace']
groups['dashboard_authority'] = ['tests/dashboard_convergence']
groups['catalogue_experience'] = ['tests/library_catalogue_experience']
groups['product_consistency'] = ['tests/product_consistency']
results = []
previous = json.loads((ROOT / 'reports/product_consistency_regression.json').read_text()) if '--resume' in sys.argv else []
if isinstance(previous, dict):
    previous = previous.get('backend', {}).get('groups', [])
for name, files in groups.items():
    completed = next((r for r in previous if r['group'] == name and r.get('exit', 0) == 0 and r.get('failed', 0) == 0), None)
    if completed:
        results.append({**completed, 'exit': 0})
        continue
    assert all((ROOT / f).exists() and 'router_v' not in f for f in files)
    xml = f'reports/product_consistency_regression_{name}.xml'
    with (ROOT / 'reports' / f'product_consistency_regression_{name}.log').open('w', encoding='utf8') as out:
        run = subprocess.run([sys.executable, '-m', 'pytest', *files, '-q', '--junitxml=' + xml], cwd=ROOT,
                             stdout=out, stderr=subprocess.STDOUT, timeout=600)
    tree = ET.parse(ROOT / xml); cases = list(tree.iter('testcase'))
    results.append({'group': name, 'exit': run.returncode, 'tests': len(cases),
        'failed': sum(any(c.tag in {'failure', 'error'} for c in t) for t in cases),
        'skipped': sum(any(c.tag == 'skipped' for c in t) for t in cases)})
    (ROOT / 'reports/product_consistency_regression.json').write_text(json.dumps(results, indent=2), encoding='utf8')
    print(name, run.returncode, flush=True)

# Existing Events fixtures pin an old wall clock. Align only test timestamps;
# expiry and JWT verification remain enabled, as in the previous phase.
event_runner = ROOT / '.scratch/library-catalogue/events_regression.py'
event_runner.parent.mkdir(parents=True, exist_ok=True)
event_runner.write_text('''import sys
from datetime import datetime, timezone
sys.path.insert(0, r"''' + str(ROOT) + '''")
sys.path.insert(0, r"''' + str(ROOT / 'tests/events') + '''")
import test_events as events
import test_event_presets as presets
events.NOW = presets.NOW = datetime.now(timezone.utc)
import pytest
raise SystemExit(pytest.main(['tests/events/test_events.py', 'tests/events/test_event_presets.py', '-q', '--junitxml=reports/product_consistency_regression_events.xml']))
''', encoding='utf8')
with (ROOT / 'reports/product_consistency_regression_events.log').open('w', encoding='utf8') as out:
    run = subprocess.run([sys.executable, str(event_runner)], cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, timeout=180)
cases = list(ET.parse(ROOT / 'reports/product_consistency_regression_events.xml').iter('testcase'))
results.append({'group': 'events', 'exit': run.returncode, 'tests': len(cases),
                'failed': sum(any(c.tag in {'failure', 'error'} for c in t) for t in cases),
                'skipped': sum(any(c.tag == 'skipped' for c in t) for t in cases)})
(ROOT / 'reports/product_consistency_regression.json').write_text(json.dumps(results, indent=2), encoding='utf8')
print('events', run.returncode, flush=True)
raise SystemExit(any(r['exit'] for r in results))


