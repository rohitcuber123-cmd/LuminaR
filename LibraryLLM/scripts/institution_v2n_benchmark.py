"""Paired fresh owned auth-enabled and anonymous-development server measurements."""
import json
import os
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import scripts.institution_v2n_fixture as fixture


def main():
    result = {'scope': 'Two owned fresh loopback servers; no actual deployment load/credentials.', 'phases': []}
    for label, mode in [('development', 'DEVELOPMENT'), ('authenticated', 'AUTHENTICATED')]:
        cls = fixture.AuthMongo
        if mode == 'DEVELOPMENT':
            namespace = {'__file__': fixture.__file__}
            source = fixture.source.replace(",'--auth'", '').replace('luminar-v2n-auth-', 'luminar-v2n-noauth-')
            exec(compile(source, fixture.__file__, 'exec'), namespace)
            cls = namespace['AuthMongo']
        with cls() as server:
            fixture.seed_database(server); fixture.provision(server); fixture.provision_application(server)
            uri = server.app_uri if mode == 'AUTHENTICATED' else f'mongodb://127.0.0.1:{server.port}/{server.database}'
            env = {**os.environ, 'LUMINAR_MONGO_MODE': mode, 'MONGO_URI': uri, 'MONGO_DB_NAME': server.database,
                   'LIBRARY_INTELLIGENCE_ROOT': str(server.artifact_root), 'LIBRARY_ASSET_ROOT': str(server.root / 'assets'),
                   'LUMINAR_SESSION_DB': str(server.root / 'sessions.sqlite'), 'JWT_SECRET_KEY': 'n-owned-benchmark-key',
                   'NOTIFICATION_DUE_WORKER_ENABLED': '0', 'NOTIFICATION_OUTBOX_WORKER_ENABLED': '0', 'LUMINAR_WORKER_TELEMETRY_ENABLED': '0'}
            output = ROOT / f'reports/institution_v2n_benchmark_{label}.json'
            with output.with_suffix('.log').open('w', encoding='utf8') as log:
                p = subprocess.run([sys.executable, str(ROOT / 'scripts/institution_v2n_benchmark_child.py'), str(output)],
                                   cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
            result['phases'].append({'label': label, 'exit': p.returncode, 'evidence': output.name})
            (ROOT / 'reports/institution_v2n_benchmark_results.json').write_text(json.dumps(result, indent=2))
            assert p.returncode == 0, 'Owned metadata benchmark failed; inspect N log.'
            # Fresh native data for paired actual encoder builds, isolated from claim-only benchmark.
            for name in ['institution_intelligence_jobs', 'institution_intelligence_targets', 'institution_intelligence_generations', 'institution_locks']:
                server.db[name].delete_many({})
            env.update(LUMINAR_V2N_ISOLATED_CHILD='1', V2N_TELEMETRY_URI=server.telemetry_uri, V2N_READER_URI=server.reader_uri,
                       LUMINAR_V2N_ANONYMOUS_COMPARISON='1' if mode == 'DEVELOPMENT' else '0')
            output = ROOT / f'reports/institution_v2n_native_benchmark_{label}.json'
            with output.with_suffix('.log').open('w', encoding='utf8') as log:
                p = subprocess.run([sys.executable, str(ROOT / 'scripts/institution_v2n_native_child.py'), '--scenario', 'benchmark', '--output', str(output)],
                                   cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
            result['phases'].append({'label': label + '_native', 'exit': p.returncode, 'evidence': output.name})
            (ROOT / 'reports/institution_v2n_benchmark_results.json').write_text(json.dumps(result, indent=2))
            assert p.returncode == 0, 'Owned paired native benchmark failed; inspect N log.'
    result['owned_fixtures_removed'] = True
    (ROOT / 'reports/institution_v2n_benchmark_results.json').write_text(json.dumps(result, indent=2))
    print('Paired owned fixture benchmark PASS')


if __name__ == '__main__': main()
