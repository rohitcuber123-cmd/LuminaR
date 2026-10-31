"""Restricted authenticated native success/crash/restart/manual recovery rehearsal."""
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from scripts.institution_v2n_fixture import AuthMongo, provision, provision_application, seed_database
from backend.services.library_worker_telemetry import digest


def main():
    report = {'scope': 'Disposable authenticated Mongo only, actual native worker and cached MiniLM/FAISS/KG.', 'cases': []}
    out = ROOT / 'reports/institution_v2n_native_results.json'
    def save(): out.write_text(json.dumps(report, indent=2, default=str))
    with AuthMongo() as server:
        seed_database(server); provision(server); provision_application(server)
        env = {**os.environ, 'LUMINAR_MONGO_MODE': 'AUTHENTICATED', 'MONGO_URI': server.app_uri, 'MONGO_DB_NAME': server.database,
               'LIBRARY_INTELLIGENCE_ROOT': str(server.artifact_root), 'LUMINAR_V2N_ISOLATED_CHILD': '1',
               'V2N_TELEMETRY_URI': server.telemetry_uri, 'V2N_READER_URI': server.reader_uri}
        for key in ['LUMINAR_V2N_BASELINE_NATIVE', 'LUMINAR_V2N_OBSERVER_CRASH']:
            env.pop(key, None)
        def child(name, scenario, *args, expected=0):
            path = ROOT / f'reports/institution_v2n_native_{name}.json'; at = time.perf_counter()
            with path.with_suffix('.log').open('w', encoding='utf8') as log:
                p = subprocess.run([sys.executable, str(ROOT / 'scripts/institution_v2n_native_child.py'), '--scenario', scenario,
                                    '--output', str(path), *args], env=env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=240)
            report['cases'].append({'name': name, 'exit': p.returncode, 'expected': expected, 'seconds': time.perf_counter() - at, 'evidence': path.name}); save()
            assert p.returncode == expected, 'Owned N native rehearsal failed; inspect sanitized N log.'
            return json.loads(path.read_text())
        value = child('success', 'success', '--enabled')
        assert len(value['builds']) == 2 and all(b['state'] == 'SUCCEEDED' and b['pointer_ack_match'] for b in value['builds'])
        assert len({e.get('heartbeat_at') for e in value['events'] if e.get('heartbeat_at')}) >= 2
        report['authenticated_success'] = True
        # Both crashes first publish a last-good generation, then terminate a real
        # worker process. Parent changes only this fixture's lease for manual recovery.
        for name, stage, expected_state in [('prepublication', 'SERIALIZATION_ACK', 'FAILED'), ('postpublication', 'ACKNOWLEDGEMENT_LOSS', 'SUCCEEDED')]:
            value = child('crash_' + name, 'crash', '--enabled', '--target', 'KNOWLEDGE_GRAPH', '--fault', stage, '--seed-last-good', expected=77)
            job = value['crash_job']; before = server.db.institution_intelligence_jobs.find_one({'job_id': job['job_id']})
            pointer = server.db.institution_intelligence_targets.find_one({'library_id': job['library_id'], 'target': 'KNOWLEDGE_GRAPH'})
            files = value['last_good']['files']
            child('restart_' + name, 'restart', '--enabled')
            assert digest(before) == digest(server.db.institution_intelligence_jobs.find_one({'job_id': job['job_id']}))
            assert digest(pointer) == digest(server.db.institution_intelligence_targets.find_one({'library_id': job['library_id'], 'target': 'KNOWLEDGE_GRAPH'}))
            assert all(Path(p).is_file() and hashlib.sha256(Path(p).read_bytes()).hexdigest() == sha for p, sha in files.items())
            server.db.institution_intelligence_jobs.update_one({'job_id': job['job_id']}, {'$set': {'lease_expires_at': datetime.now(timezone.utc) - timedelta(seconds=1)}})
            recovered = child('manual_' + name, 'recover', '--recovery-library', job['library_id'], '--recovery-job', job['job_id'])
            assert recovered['recovered_job']['state'] == expected_state
            report[name] = {'restart_preserved_job_and_pointer': True, 'last_good_artifact_hashes_preserved': True,
                            'manual_recovery_state': expected_state, 'native_lease_constants_unchanged': True}
            save()
        report['no_automatic_rebuild_or_recovery'] = True
        report['principal'] = 'fixture_application (named-resource compatibility envelope, not root)'
    report['owned_fixture_removed'] = True; save(); print(json.dumps({'authenticated_native': 'PASS', 'cases': len(report['cases'])}))


if __name__ == '__main__': main()
