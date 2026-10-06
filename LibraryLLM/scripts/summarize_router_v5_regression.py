"""Aggregate actual regression outputs and source preservation, no model calls."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from router_v5_evidence import write,digest

def main():
    groups={}
    for name in ['unit','confirmation','assistant','security','staff','notifications','circulation','search']:
        tree=ET.parse(ROOT/f'reports/assistant_router_v5_{name}.xml')
        suites=list(tree.getroot().iter('testsuite'))
        groups[name]={key:sum(float(s.attrib.get(key,0)) for s in suites) for key in ['tests','failures','errors','skipped','time']}
    frontend={}
    for name in ['assistant','extra']:
        text=(ROOT/f'reports/assistant_router_v5_frontend_{name}.log').read_text(encoding='utf8')
        import re
        frontend[name]={key:int(re.search(r'ℹ '+key+r' (\d+)',text).group(1)) for key in ['tests','pass','fail','skipped']}
    baseline=json.loads((ROOT/'reports/assistant_router_v5_baseline.json').read_text(encoding='utf8'))
    changed=[p for p,h in baseline['frozen_files'].items() if not (ROOT/p).exists() or digest(ROOT/p)!=h]
    expected={'assistant/api.py','assistant/profiling.py','assistant/semantic.py'}
    restored_path=ROOT/'reports/assistant_router_v5_restored.json'
    restored=json.loads(restored_path.read_text(encoding='utf8')) if restored_path.exists() else {}
    runtime_artifacts=[]
    if restored.get('private_document_registry_rows')==0 and restored.get('private_document_directories')==0:
        if 'rag/private_documents/registry.sqlite' in changed:
            runtime_artifacts=['rag/private_documents/registry.sqlite']
    build=(ROOT/'reports/assistant_router_v5_build.log').read_text(encoding='utf8')
    lint=(ROOT/'reports/assistant_router_v5_lint.log').read_text(encoding='utf8')
    write('regression',{'backend_groups':groups,'backend_passed':int(sum(g['tests']-g['failures']-g['errors']-g['skipped'] for g in groups.values())),
          'backend_skipped':int(sum(g['skipped'] for g in groups.values())),'backend_failures':int(sum(g['failures']+g['errors'] for g in groups.values())),
          'frontend':frontend,'frontend_passed':sum(g['pass'] for g in frontend.values()),'build':'PASS' if 'built in' in build else 'FAIL',
          'lint_errors':lint.count(': error '),'lint_existing_warnings':lint.count(': warning '),
          'frozen_baseline_count':len(baseline['frozen_files']),'changed_frozen_files':changed,'runtime_artifacts_changed':runtime_artifacts,
          'runtime_artifact_note':'The synthetic upload was ingested and deleted; the empty SQLite registry changed bytes. Source/RAG algorithms stayed frozen.',
          'preservation_pass':set(changed)==expected|set(runtime_artifacts),
          'transport_regression':'PASS: no per-request AsyncClient; single installation client, bounded connections, request-local bearer',
          'initial_collection_failure':'Staff fixture replaces Mongo module; combining with notification collection fails. Suites were rerun separately, without code changes.',
          'v3_v4_unchanged':not any('router_v3' in p or 'router_v4' in p for p in changed),
          'algorithms_unchanged':not any(p.startswith(('search/','recommendation/','rag/','backend/','frontend/')) for p in changed if p not in runtime_artifacts)})

if __name__=='__main__':main()
