"""Independent product suite processes; isolated existing fixtures, no research."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def run_backend(tag):
    # Use the accepted suite inventory, with only the accepted infrastructure
    # tests from 2G. Later parser research is unrelated to operational 2I.
    groups = {}
    for name in ('unit', 'assistant', 'security', 'staff', 'notifications', 'circulation', 'search'):
        tree = ET.parse(ROOT / 'reports' / f'assistant_stabilization_{name}.xml')
        groups[name] = sorted({t.attrib['classname'].replace('.', '/') + '.py' for t in tree.iter('testcase')})
    groups['private_knowledge_ocr'] = ['tests/test_private_document_cache.py', 'tests/test_private_preparation_status.py',
        'tests/test_document_knowledge.py', 'tests/test_knowledge_artifacts.py', 'tests/test_knowledge_quiz.py',
        'tests/test_knowledge_tools_v2_1.py', 'tests/test_quiz_v2_2.py', 'tests/test_cloze_v2_3.py']
    groups['kg'] = ['tests/test_kg_product.py', 'tests/test_kg_topics.py', 'tests/test_knowledge_graph.py']
    groups.update({f'institution_{v}': [f'tests/institution_{v}'] for v in ['v1', 'v2a', 'v2b', 'v2c', 'v2d', 'v2e', 'v2f', 'v2h']})
    groups['institution_v2g'] = ['tests/institution_v2g/' + n for n in ['test_intelligence.py', 'test_validation_recovery.py', 'test_private_isolation.py', 'test_search_runtime.py']]
    groups.update({'workspace_authorization': ['tests/frontend_workspace'], 'dashboard_authority': ['tests/dashboard_convergence'],
                   'catalogue_experience': ['tests/library_catalogue_experience'], 'product_consistency': ['tests/product_consistency']})
    extras = [str(p.relative_to(ROOT)).replace('\\', '/') for p in (ROOT / 'tests').glob('test_*.py')
              if any(s in p.name for s in ('recommendation', 'post2h', 'post_2h', 'book_capabilit', 'online_book', 'platform_'))]
    if extras:
        groups['current_product_extensions'] = extras
    if tag != 'baseline' and (ROOT / 'tests/institution_v2i').exists():
        groups['institution_v2i'] = ['tests/institution_v2i']
    results = []
    for name, files in groups.items():
        xml = ROOT / f'reports/institution_v2i_{tag}_{name}.xml'
        log = xml.with_suffix('.log')
        started = time.perf_counter()
        try:
            with log.open('w', encoding='utf8') as out:
                p = subprocess.run([sys.executable, '-m', 'pytest', *files, '-q', '--junitxml=' + str(xml)],
                                   cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, timeout=900)
            cases = list(ET.parse(xml).iter('testcase'))
            failed = sum(any(c.tag in {'failure', 'error'} for c in t) for t in cases)
            skipped = sum(any(c.tag == 'skipped' for c in t) for t in cases)
            result = {'group': name, 'exit': p.returncode, 'tests': len(cases), 'passed': len(cases)-failed-skipped,
                      'failed': failed, 'skipped': skipped, 'seconds': time.perf_counter()-started, 'files': files}
        except Exception as error:
            result = {'group': name, 'exit': -1, 'error': type(error).__name__, 'files': files}
        results.append(result)
        (ROOT / f'reports/institution_v2i_{tag}_backend.json').write_text(json.dumps(results, indent=2))
        print(json.dumps({k: v for k, v in result.items() if k != 'files'}), flush=True)
    # Preserve the established Events date alignment without modifying fixtures.
    event = ROOT / f'.scratch/institution-v2i/events_{tag}.py'
    event.parent.mkdir(parents=True, exist_ok=True)
    xml = ROOT / f'reports/institution_v2i_{tag}_events.xml'
    event.write_text("import sys\nfrom datetime import datetime, timezone\nsys.path.insert(0, " + repr(str(ROOT)) + ")\nsys.path.insert(0, " + repr(str(ROOT / 'tests/events')) + ")\nimport test_events as events\nimport test_event_presets as presets\nevents.NOW = presets.NOW = datetime.now(timezone.utc)\nimport pytest\nraise SystemExit(pytest.main(['tests/events/test_events.py','tests/events/test_event_presets.py','-q','--junitxml=" + str(xml).replace('\\', '/') + "']))\n")
    with xml.with_suffix('.log').open('w', encoding='utf8') as out:
        p = subprocess.run([sys.executable, str(event)], cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, timeout=240)
    cases = list(ET.parse(xml).iter('testcase'))
    failed = sum(any(c.tag in {'failure', 'error'} for c in t) for t in cases)
    skipped = sum(any(c.tag == 'skipped' for c in t) for t in cases)
    results.append({'group': 'events', 'exit': p.returncode, 'tests': len(cases), 'passed': len(cases)-failed-skipped, 'failed': failed, 'skipped': skipped})
    (ROOT / f'reports/institution_v2i_{tag}_backend.json').write_text(json.dumps(results, indent=2))
    print('events', p.returncode, flush=True)
    return any(r['exit'] for r in results)


def frontend(tag):
    results = []
    for name, command in [('frontend', ['npm.cmd', 'test']), ('build', ['npm.cmd', 'run', 'build']), ('lint', ['npm.cmd', 'run', 'lint'])]:
        log = ROOT / f'reports/institution_v2i_{tag}_{name}.log'
        with log.open('w', encoding='utf8') as out:
            p = subprocess.run(command, cwd=ROOT / 'frontend', stdout=out, stderr=subprocess.STDOUT, timeout=900)
        results.append({'check': name, 'exit': p.returncode, 'log': log.name})
        (ROOT / f'reports/institution_v2i_{tag}_frontend.json').write_text(json.dumps(results, indent=2))
        print(name, p.returncode, flush=True)
    return any(r['exit'] for r in results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('kind', choices=['backend', 'frontend'])
    parser.add_argument('tag')
    a = parser.parse_args()
    protected = {name: (ROOT/'reports'/name).read_bytes()
                 for name in ['institution_v2e_backend_benchmark.json', 'full_product_generated_test_plan.json']
                 if (ROOT/'reports'/name).exists()}
    try:
        result = run_backend(a.tag) if a.kind == 'backend' else frontend(a.tag)
    finally:
        for name, original in protected.items():
            p = ROOT/'reports'/name
            if p.read_bytes() != original:
                (ROOT/'reports'/f'institution_v2i_{a.tag}_generated_{name}').write_bytes(p.read_bytes())
                p.write_bytes(original)
    raise SystemExit(result)
