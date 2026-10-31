"""Fresh independent reader CLI and restricted writer checks, disposable only."""
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from scripts.institution_v2n_fixture import AuthMongo, seed_database, provision
from backend.services.library_worker_observer import Configuration, RestrictedWriter


def main():
    result = {'scope': 'Fresh authenticated disposable CLI/writer fixture; telemetry production flag unchanged.', 'commands': []}
    with AuthMongo() as server:
        seed_database(server); provision(server)
        writer = RestrictedWriter(Configuration(server.database, server.telemetry_uri), 'tenant-' + str(uuid4()))
        writer.start()
        try:
            assert writer.pulse()
            library = str(uuid4())
            for script in ['diagnose_worker_telemetry.py', 'diagnose_library_intelligence.py']:
                values = []
                for fmt in ['json', 'text']:
                    args = [sys.executable, str(ROOT / 'scripts' / script), '--database', server.database, '--library-id', library, '--format', fmt]
                    if script == 'diagnose_library_intelligence.py': args += ['--artifact-root', str(server.artifact_root)]
                    for _ in range(3):
                        at = time.perf_counter()
                        p = subprocess.run(args, cwd=ROOT, env={**os.environ, 'LUMINAR_OPERATOR_MONGO_URI': server.reader_uri}, capture_output=True, text=True, timeout=20)
                        values.append((time.perf_counter() - at) * 1000)
                        assert p.returncode == 0, 'Owned diagnostic invocation failed'
                        assert server.read_password not in p.stdout + p.stderr and server.reader_uri not in p.stdout + p.stderr
                        if fmt == 'json': json.loads(p.stdout)
                result['commands'].append({'script': script, 'calls': len(values), 'median_ms': statistics.median(values), 'samples_ms': values,
                                           'includes': 'Python process/import/SCRAM/bounded empty-tenant reads/JSON or text serialization; model excluded.'})
        finally: writer.close()
    result['owned_fixture_removed'] = True
    (ROOT / 'reports/institution_v2n_operator_fixture.json').write_text(json.dumps(result, indent=2))
    print('Authenticated operator CLI and restricted pulse PASS')


if __name__ == '__main__': main()
