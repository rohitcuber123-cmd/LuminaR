"""Adapt only task-owned fixture scaffolding; original tests and reports untouched."""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from scripts.institution_v2n_fixture import AuthMongo, provision_application


def main():
    groups = ['institution_v1', 'institution_v2a', 'institution_v2b', 'institution_v2c', 'institution_v2d',
              'institution_v2e', 'institution_v2f', 'institution_v2g', 'institution_v2h', 'frontend_workspace',
              'dashboard_convergence', 'library_catalogue_experience', 'product_consistency']
    if len(sys.argv) > 1:
        groups = [g for g in groups if g in sys.argv[1:]]
    out = ROOT / 'reports/institution_v2n_application_results.json'
    results = json.loads(out.read_text()) if len(sys.argv) > 1 and out.exists() else []
    for group in groups:
        original = ROOT / 'tests' / group
        target = ROOT / '.scratch/institution-v2n' / ('auth_' + group)
        target.mkdir(parents=True, exist_ok=True)
        hashes = {}
        for path in original.glob('*.py'):
            source = path.read_text(encoding='utf8')
            if path.name.startswith('test_') and group == 'institution_v2g' and path.name not in {
                    'test_intelligence.py', 'test_validation_recovery.py', 'test_private_isolation.py', 'test_search_runtime.py'}:
                continue
            hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
            if path.name == 'conftest.py':
                source = re.sub(r"os.environ\['MONGO_URI'\]\s*=.*", "os.environ['MONGO_URI'] = os.environ['LUMINAR_V2N_APP_URI']", source)
                source = re.sub(r"os.environ\['MONGO_DB_NAME'\]\s*=.*", "os.environ['MONGO_DB_NAME'] = os.environ['LUMINAR_V2N_APP_DB']", source)
                source = re.sub(r"assert db.name.startswith\(.*\)", "assert db.name.startswith('luminar_v2n_fixture_')", source)
                source = source.replace('mongo.drop_database(db.name)', "mongo.close()  # Parent maintenance identity owns cleanup, no application drop privilege.")
                source = source.replace('for name in db.list_collection_names():', "for name in [n for n in db.list_collection_names() if not n.startswith('system.')]:")
            source = source.replace('Path(__file__).resolve().parents[2]', 'Path(' + repr(str(ROOT)) + ')')
            source = source.replace('institution_v2e_', 'institution_v2n_auth_v2e_') if path.name == 'test_analytics.py' else source
            (target / path.name).write_text(source, encoding='utf8')
        with AuthMongo() as server:
            role = provision_application(server)
            (ROOT / 'reports/institution_v2n_fixture_role.json').write_text(json.dumps(role, indent=2))
            env = {**os.environ, 'LUMINAR_MONGO_MODE': 'AUTHENTICATED', 'LUMINAR_V2N_APP_URI': server.app_uri,
                   'LUMINAR_V2N_APP_DB': server.database, 'LUMINAR_WORKER_TELEMETRY_ENABLED': '0',
                   'NOTIFICATION_DUE_WORKER_ENABLED': '0', 'NOTIFICATION_OUTBOX_WORKER_ENABLED': '0',
                   'LIBRARY_ASSET_ROOT': str(server.root / 'assets'), 'LIBRARY_INTELLIGENCE_ROOT': str(server.artifact_root),
                   'PYTHONPATH': str(ROOT), 'LUMINAR_V2N_TRACE_OUTPUT': str(ROOT / f'reports/institution_v2n_auth_{group}_commands.json')}
            xml = ROOT / f'reports/institution_v2n_auth_{group}.xml'
            if xml.exists():
                assert xml.resolve().parent == (ROOT / 'reports').resolve() and xml.name.startswith('institution_v2n_auth_')
                xml.unlink()  # Never parse a previous run's XML after a collection error.
            at = time.perf_counter()
            with xml.with_suffix('.log').open('w', encoding='utf8') as log:
                p = subprocess.run([sys.executable, '-m', 'pytest', str(target), '-q', '-p', 'scripts.institution_v2n_trace_plugin', '--junitxml=' + str(xml)],
                                   cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=900)
            cases = list(ET.parse(xml).iter('testcase')) if xml.exists() else []
            failed = sum(any(c.tag in {'failure', 'error'} for c in t) for t in cases)
            skipped = sum(any(c.tag == 'skipped' for c in t) for t in cases)
            row = {'group': group, 'exit': p.returncode, 'passed': len(cases) - failed - skipped, 'failed': failed, 'skipped': skipped,
                   'seconds': time.perf_counter() - at, 'original_test_sha256': hashes, 'fixture_principal': 'fixture_application',
                   'role_boundary': 'Named resources; no root/readWrite/drop/userAdmin/clusterAdmin. Compatibility envelope includes fixture setup writes.'}
            results = [r for r in results if r['group'] != group] + [row]
            out.write_text(json.dumps(results, indent=2)); print(json.dumps({k: v for k, v in row.items() if k != 'original_test_sha256'}), flush=True)
    return any(r['exit'] for r in results)


if __name__ == '__main__':
    raise SystemExit(main())
