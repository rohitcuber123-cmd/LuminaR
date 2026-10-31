"""Real mongodump/mongorestore against synthetic owned databases only."""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from bson import BSON

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from scripts.institution_v2n_fixture import AuthMongo, seed_database, provision


def snapshot(db):
    rows = {}
    for name in sorted(db.list_collection_names()):
        if name.startswith('system.'): continue
        docs = sorted(BSON.encode(row) for row in db[name].find({}))
        rows[name] = {'count': len(docs), 'bson_sha256': hashlib.sha256(b''.join(docs)).hexdigest(),
                      'indexes': [{k: v for k, v in row.items() if k not in {'ns'}} for row in db[name].list_indexes()],
                      'options': db[name].options()}
    return rows


def main():
    tools = Path('C:/Program Files/MongoDB/Tools/bin')
    result = {'scope': 'Synthetic owned DB only; no current user data exported.', 'actual_deployment_restore': 'NOT_VERIFIED'}
    with AuthMongo() as server:
        seed_database(server); provision(server)
        server.db.books.insert_many([{'work_id': f'N-{n}', 'title': f'Synthetic restore {n}', 'subjects': ['fixture']} for n in range(151)])
        server.db.books.create_index('work_id', unique=True)
        server.db.institution_libraries.insert_one({'library_id': 'synthetic-private', 'library_type': 'PRIVATE_INSTITUTION'})
        before = snapshot(server.db)
        p = subprocess.run([shutil.which('pwsh.exe'), '-NoProfile', '-NonInteractive', '-File', str(ROOT / 'scripts/institution_v2n_tools_secret.ps1')],
                           input=json.dumps({'fixture_root': str(server.root), 'uri': server.writer_uri.replace('/' + server.database + '?', '/?')}), capture_output=True, text=True, timeout=20)
        assert p.returncode == 0, 'Owned tool credential ACL setup failed'
        result['secret_config_acl'] = json.loads(p.stdout)
        assert result['secret_config_acl']['directory_protected']
        config = server.root / 'tools-secret/mongo-tools.yml'
        dump = server.root / 'synthetic-dump'
        def run(label, args):
            started = time.perf_counter()
            p = subprocess.run([str(tools / (label + '.exe')), '--config=' + str(config), *args], capture_output=True, text=True, timeout=120)
            assert server.password not in p.stdout + p.stderr, 'Tool output leaked synthetic password'
            # Tool output has synthetic collection names/counts only; no documents.
            (ROOT / f'reports/institution_v2n_{label}.log').write_text(p.stdout + p.stderr)
            result[label] = {'exit': p.returncode, 'seconds': time.perf_counter() - started}
            assert p.returncode == 0, 'Owned Mongo tool operation failed'
        run('mongodump', ['--db=' + server.database, '--out=' + str(dump)])
        restored = server.database + '_restore'
        assert restored not in server.writer.list_database_names()
        run('mongorestore', ['--nsFrom=' + server.database + '.*', '--nsTo=' + restored + '.*', '--nsInclude=' + server.database + '.*', str(dump)])
        after = snapshot(server.writer[restored])
        if before != after:
            (ROOT / 'reports/institution_v2n_restore_initial_difference.json').write_text(json.dumps({'before': before, 'after': after}, indent=2, default=str))
        assert before == after, 'Synthetic collection/document/index/validator restore differs'
        assert snapshot(server.db) == before, 'Restore changed its source fixture database'
        result.update(result='PASS', collections=before, restored_collections=after,
                      exact_bson_indexes_options_equal=True, source_unchanged=True,
                      database_tools_version=subprocess.run([str(tools / 'mongodump.exe'), '--version'], capture_output=True, text=True).stdout.strip(),
                      password_in_argv=False, synthetic_secret_directory_only=True)
    result['owned_fixture_removed'] = True
    (ROOT / 'reports/institution_v2n_backup_restore_fixture.json').write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps({'restore': 'PASS', 'collections': len(before), 'actual_restore': 'NOT_VERIFIED'}))


if __name__ == '__main__': main()
