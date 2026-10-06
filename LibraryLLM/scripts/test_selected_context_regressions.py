"""Repeat the previously passing production suites without router research."""
from pathlib import Path
import argparse
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--groups', nargs='+', choices=['unit', 'assistant', 'security', 'staff', 'notifications', 'circulation', 'search'],
               default=['unit', 'assistant', 'security', 'staff', 'notifications', 'circulation', 'search'])
for group in p.parse_args().groups:
    tree = ET.parse(ROOT / 'reports' / f'assistant_stabilization_{group}.xml')
    files = sorted({t.attrib['classname'].replace('.', '/') + '.py' for t in tree.iter('testcase')})
    assert files and all((ROOT / f).exists() for f in files)
    assert not any('router_v' in f for f in files), 'Frozen router tests must stay excluded.'
    with (ROOT / 'reports' / f'assistant_selected_context_regression_{group}.log').open('w', encoding='utf8') as out:
        result = subprocess.run([str(ROOT / '.venv/Scripts/python.exe'), '-m', 'pytest', *files, '-q',
            f'--junitxml=reports/assistant_selected_context_regression_{group}.xml'], cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, timeout=600)
    print(group, result.returncode, flush=True)
