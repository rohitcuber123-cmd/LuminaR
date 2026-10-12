"""Read-only final Part 2F preservation verification after personal QA cleanup.

Reads immutable baselines and current local development state. It does not
modify Mongo, personal SQLite, assets, sources or protected artifacts. Only the
two final evidence reports are written, after every preservation check passes.
Run explicitly with --after-qa-cleanup; do not run while QA is still active.
"""
import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.institution_v2e_baseline import TEST, digest

REPORTS = ROOT / 'reports'
SOURCE_SUFFIXES = {'.py', '.ts', '.tsx', '.css', '.json', '.md', '.html', '.toml', '.ps1', '.cjs', '.mjs'}
ASSET_COLLECTIONS = {'institution_library_assets', 'institution_library_asset_jobs'}
ASSET_AUDIT_EVENTS = {
    'ASSET_UPLOADED', 'ASSET_PROCESSING_STARTED', 'ASSET_READY',
    'ASSET_PROCESSING_FAILED', 'ASSET_VISIBILITY_CHANGED',
    'ASSET_LINKED_BOOK_CHANGED', 'ASSET_METADATA_CHANGED',
    'ASSET_DELETED', 'ASSET_REPROCESSED',
}
PERSONAL_ROOTS = ('rag/private_documents', '.local/private_documents')
PERSONAL_TABLES = ('documents', 'knowledge_artifacts', 'document_knowledge')
SQLITE_PHYSICAL_FILES = {'registry.sqlite', 'registry.sqlite-journal', 'registry.sqlite-wal', 'registry.sqlite-shm'}


class PreservationFailure(RuntimeError):
    """A bounded failure description, never a document/account payload."""


def require(condition, message):
    if not condition:
        raise PreservationFailure(message)


def read_report(name):
    return json.loads((REPORTS / name).read_text(encoding='utf8'))


def sha256(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for piece in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(piece)
    return value.hexdigest()


def repository_path(name):
    path = ROOT / name
    require(not Path(name).is_absolute() and path.resolve().is_relative_to(ROOT),
            'Evidence path is outside the project root.')
    return path


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(isinstance(value, datetime), 'An ownership timestamp is missing or invalid.')
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def canonical_uuid(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (TypeError, ValueError, AttributeError):
        return False


def capture_sources():
    names = subprocess.check_output([
        'rg', '--files', '--hidden', '-g', '!.git', '-g', '!.venv',
        '-g', '!node_modules', '-g', '!.scratch', '-g', '!scratch',
        '-g', '!dist', '-g', '!datasets',
    ], cwd=ROOT, text=True).splitlines()
    result = {}
    for name in names:
        name = name.replace('\\', '/')
        path = repository_path(name)
        if (not name.startswith('reports/') and path.suffix in SOURCE_SUFFIXES
                and path.stat().st_size < 32 * 1024 * 1024):
            result[name] = sha256(path)
    return result


def protected_source(name):
    return (name.startswith(('search/', 'recommendation/', 'rag/', 'assistant/', 'knowledge_graph/', 'kg/'))
            or name.startswith('backend/') and any(part in name.lower() for part in ('assistant', 'qwen', 'router')))


def verify_rag_install(before_sha):
    """Allow only the reviewed import/installation, preserving all old bytes."""
    before = ROOT / '.scratch/institution-v2f/before/rag/api.py'
    current = ROOT / 'rag/api.py'
    require(before.is_file() and sha256(before) == before_sha,
            'RAG before-source evidence does not match the immutable baseline.')
    original, installed = before.read_bytes(), current.read_bytes()
    possible = [
        b'from rag.services.library_asset_routes import install_library_assets\ninstall_library_assets(app, engine)\n',
        b'from rag.services.library_asset_routes import install_library_assets\r\ninstall_library_assets(app, engine)\r\n',
    ]
    matches = [insert for insert in possible if installed.count(insert) == 1 and installed.replace(insert, b'', 1) == original]
    require(len(matches) == 1, 'rag/api.py changed beyond the explicit two-line library adapter installation.')
    return {
        'classification': 'MINIMAL_LIBRARY_ASSET_ADAPTER_INSTALLATION',
        'before_sha256': before_sha,
        'after_sha256': sha256(current),
        'only_change': 'Import install_library_assets and call install_library_assets(app, engine).',
        'baseline_bytes_restored_by_removing_only_adapter_lines': True,
        'router_ranking_generation_logic_changed': False,
    }


def personal_snapshot(path):
    """Logical rows only; read-only connection, no content/owner fields exported."""
    require(path.is_file(), 'Personal registry is missing.')
    snapshots = {}
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=15)
    try:
        connection.execute('PRAGMA query_only=ON')
        connection.row_factory = sqlite3.Row
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        require(set(PERSONAL_TABLES).issubset(tables), 'Personal registry tables are missing.')
        for name in PERSONAL_TABLES:
            rows = [dict(row) for row in connection.execute('SELECT * FROM ' + name)]
            encoded_rows = [json.dumps(row, sort_keys=True, default=str) for row in rows]
            encoded_rows.sort()
            # The immutable empty-table baseline uses SHA-256 of json.dumps([]).
            # Sorting rows makes nonempty comparisons independent of SQLite order.
            payload = json.dumps([json.loads(row) for row in encoded_rows], sort_keys=True, default=str)
            snapshots[name] = {'rows': len(rows), 'sha256': hashlib.sha256(payload.encode()).hexdigest()}
    finally:
        connection.close()
    return snapshots


def verify_personal(baseline, logical_before):
    current = {}
    physical_sqlite = []
    for directory in PERSONAL_ROOTS:
        root = ROOT / directory
        if root.exists():
            for path in root.rglob('*'):
                if not path.is_file():
                    continue
                name = path.relative_to(ROOT).as_posix()
                require(path.resolve().is_relative_to(root.resolve()), 'Personal artifact escaped its baseline root.')
                if path.parent == root and path.name in SQLITE_PHYSICAL_FILES:
                    physical_sqlite.append(name)
                    continue
                stat = path.stat()
                current[name] = {'bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns, 'sha256': sha256(path)}
    before = {name: value for name, value in baseline['personal_artifact_metadata'].items()
              if not (Path(name).parent.as_posix() in PERSONAL_ROOTS and Path(name).name in SQLITE_PHYSICAL_FILES)}
    require(current == before, 'Personal source/derived artifact files differ from the immutable baseline or QA cleanup is incomplete.')
    logical_after = personal_snapshot(ROOT / 'rag/private_documents/registry.sqlite')
    require(logical_after == logical_before, 'Personal registry logical rows differ from the immutable baseline or QA cleanup is incomplete.')
    require(all(value['rows'] == 0 for value in logical_after.values()),
            'This phase baseline requires zero retained personal QA registry rows.')
    return {
        'status': 'PASS',
        'baseline_artifact_files_compared_excluding_sqlite_physical': len(before),
        'original_non_sqlite_files_unchanged': True,
        'unexpected_personal_artifact_files': 0,
        'logical_before': logical_before,
        'logical_after': logical_after,
        'logical_snapshot_unchanged': True,
        'retained_personal_QA_rows': 0,
        'sqlite_physical_metadata_excluded': sorted(physical_sqlite),
        'method': 'Original non-SQLite files use SHA-256, bytes and mtime_ns. SQLite tables use read-only logical row hashes; physical database/journal bytes may change during safe QA and cleanup.',
        'personal_to_library_migration_performed': False,
    }


def verify_test(db, baseline):
    captured = utc(baseline['captured_at'])
    assets = list(db.institution_library_assets.find({'library_id': TEST}, {'_id': 0}))
    qa = read_report('institution_v2f_live_assets.json')
    qa_ids = {qa[name]['asset_id'] for name in ('TEST_members', 'TEST_staff')}
    activity_path = REPORTS / 'institution_v2f_concurrent_user_activity.json'
    observed = read_report(activity_path.name)['assets'] if activity_path.is_file() else []
    observed_ids = {row['asset_id'] for row in observed}
    require(qa_ids.isdisjoint(observed_ids) and len(qa_ids) == 2,
            'QA resources and explicitly observed user assets must have separate identities.')
    require({row['asset_id'] for row in assets} == qa_ids | observed_ids,
            'TEST contains an asset not included in the explicit QA or concurrent user inventory.')
    for expected in observed:
        row = next(row for row in assets if row['asset_id'] == expected['asset_id'])
        require(canonical_uuid(row['asset_id']) and row['library_id'] == TEST
                and row['uploaded_by_user_id'] == expected['uploaded_by_user_id'] == 4
                and utc(row['created_at']) == utc(expected['created_at']) >= captured,
                'Observed Owner upload identity or provenance changed.')
    qa_assets = [row for row in assets if row['asset_id'] in qa_ids]
    require(len(qa_assets) == 2, 'TEST must retain the two explicitly reported safe QA assets.')
    ids = set()
    public_assets = []
    for row in qa_assets:
        require(canonical_uuid(row.get('asset_id')) and row['library_id'] == TEST,
                'TEST asset has invalid canonical ownership.')
        require(utc(row.get('created_at')) >= captured, 'TEST asset predates the phase ownership baseline.')
        require(row.get('status') == 'READY', 'A retained TEST resource is not READY.')
        require(row.get('visibility') in ('STAFF_ONLY', 'MEMBERS') and row.get('asset_type') == 'PDF',
                'A retained TEST resource has unexpected visibility or format.')
        require(db.institution_library_books.count_documents({'library_id': TEST,
                'library_book_id': row.get('library_book_id'), 'status': 'ACTIVE'}) == 1,
                'A retained TEST resource is not linked to its canonical ACTIVE TEST book.')
        ids.add(row['asset_id'])
        public_assets.append({key: row.get(key) for key in (
            'asset_id', 'library_id', 'title', 'original_filename', 'visibility',
            'status', 'library_book_id', 'global_work_id', 'asset_type', 'byte_size', 'checksum',
        )})
    require(len(ids) == 2, 'TEST assets do not have distinct immutable identities.')
    audit_asset_ids = ids | observed_ids
    jobs = list(db.institution_library_asset_jobs.find({'library_id': TEST}, {'_id': 0}))
    require(all(canonical_uuid(row.get('job_id')) and row.get('asset_id') in audit_asset_ids
                and utc(row.get('created_at')) >= captured for row in jobs),
            'A TEST processing job lacks current explicit asset ownership.')

    snapshots, allowed_audit = {}, []
    names = set(baseline['TEST']['collection_digests']) | {
        name for name in db.list_collection_names()
        if name.startswith('institution_') or name in ('events', 'notifications', 'notification_outbox')
    }
    for name in sorted(names):
        if name in ASSET_COLLECTIONS:
            continue
        rows = list(db[name].find({'library_id': TEST}, {'_id': 0}))
        compare_rows = rows
        if name == 'institution_audit':
            compare_rows = []
            for row in rows:
                metadata = row.get('metadata')
                is_asset = (isinstance(metadata, dict) and metadata.get('asset_id') in audit_asset_ids
                            and row.get('event') in ASSET_AUDIT_EVENTS
                            and utc(row.get('created_at')) >= captured)
                if is_asset:
                    allowed_audit.append({
                        'event_id': row.get('event_id'), 'event': row['event'],
                        'asset_id': metadata['asset_id'], 'created_at': row['created_at'],
                    })
                else:
                    compare_rows.append(row)
        before = baseline['TEST']['collection_digests'].get(name, {'count': 0, 'sha256': digest([])})
        after = {'count': len(compare_rows), 'sha256': digest(compare_rows)}
        require(before == after, 'Original TEST domain rows changed in ' + name + '.')
        snapshots[name] = {'unchanged': True, 'before': before, 'after': after,
                           'current_total_count': len(rows)}
    require(allowed_audit, 'The new TEST asset operations have no canonical asset audit evidence.')
    require(not db.institution_locks.find_one({'_id': TEST}), 'TEST has a pending durable mutation lock.')
    books = db.institution_library_books.count_documents({'library_id': TEST, 'status': 'ACTIVE'})
    holdings = db.institution_holdings.count_documents({'library_id': TEST})
    require(books == holdings == baseline['TEST']['ACTIVE_books'] == baseline['TEST']['holdings'] == 150,
            'TEST ACTIVE book or holding count changed.')
    owner = db.institution_memberships.find_one({'library_id': TEST, 'user_id': 4, 'status': 'ACTIVE'}, {'role': 1})
    patron = db.institution_memberships.find_one({'library_id': TEST, 'user_id': 10, 'status': 'ACTIVE'}, {'role': 1})
    require(owner and owner.get('role') == 'ADMIN' and patron and patron.get('role') == 'GENERAL_USER',
            'Accepted TEST human workspace authority changed.')
    return {
        'library_id': TEST, 'ACTIVE_records': books, 'holdings': holdings,
        'owner_role': owner['role'], 'patron_role': patron['role'],
        'original_domain_collection_digests': snapshots,
        'all_original_non_asset_rows_unchanged': True,
        'allowed_new_audit_rows': {'count': len(allowed_audit),
            'method': 'Only whitelisted ASSET events created after baseline for the two exact QA UUIDs or separately inventoried concurrent Owner upload UUIDs are excluded before exact original audit digest comparison.',
            'events': sorted(allowed_audit, key=lambda row: str(row['event_id']))},
        'retained_safe_resources': sorted(public_assets, key=lambda row: row['asset_id']),
        'retained_QA_asset_count': len(qa_assets),
        'concurrent_owner_uploads_preserved': observed,
        'retained_asset_count': len(assets), 'processing_job_count': len(jobs),
        'pending_library_lock': False,
    }


def capture():
    """Call only when root has finished personal QA cleanup."""
    from backend.database.mongodb import db
    require(db.name == 'luminar_library' and db.client.address[0] in ('localhost', '127.0.0.1', '::1'),
            'Preservation capture is limited to the accepted local development database.')
    baseline = read_report('institution_v2f_baseline.json')
    personal_before = read_report('institution_v2f_personal_baseline.json')
    require(baseline['TEST']['library_id'] == TEST, 'Baseline TEST identity is incorrect.')
    test = verify_test(db, baseline)
    global_count = db.books.estimated_document_count()
    require(global_count == baseline['global_count'] == 5000000, 'Global estimated catalogue count changed.')
    artifacts = []
    for name, before in sorted(baseline['artifact_metadata'].items()):
        path = repository_path(name)
        require(path.is_file(), 'A protected artifact is missing: ' + name)
        stat = path.stat()
        after = {'bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
        require(before == after, 'Protected artifact size/mtime changed: ' + name)
        artifacts.append({'path': name, 'unchanged': True, 'before': before, 'after': after})
    require(len(artifacts) == 196, 'Protected artifact inventory does not contain the accepted 196 entries.')

    sources = capture_sources()
    before_sources = baseline['source_sha256']
    deleted = sorted(set(before_sources) - set(sources))
    require(not deleted, 'Baseline source files were deleted: ' + ', '.join(deleted))
    protected = {name: sources.get(name) == value for name, value in before_sources.items() if protected_source(name)}
    require(len(protected) == 156, 'Protected source selection does not contain the accepted 156 entries.')
    rag_adapter = verify_rag_install(before_sources['rag/api.py'])
    require(all(unchanged for name, unchanged in protected.items() if name != 'rag/api.py'),
            'Frozen ranking, Assistant/router, Book/personal RAG or Knowledge Tool source changed.')
    require(not protected['rag/api.py'], 'Expected explicit library adapter installation is missing.')
    personal = verify_personal(baseline, personal_before)
    changed = sorted(name for name, value in sources.items() if before_sources.get(name) != value)
    stamped = datetime.now(timezone.utc).isoformat()
    baseline_sha = sha256(REPORTS / 'institution_v2f_baseline.json')
    result = {
        'status': 'PASS', 'captured_at': stamped,
        'baseline_captured_at': baseline['captured_at'], 'baseline_sha256': baseline_sha,
        'TEST': test,
        'global_catalogue': {'count': global_count, 'baseline_count': baseline['global_count'],
            'unchanged': True, 'method': 'estimated_document_count', 'full_document_digest': False},
        'artifacts': {'compared': len(artifacts), 'unchanged': True,
            'method': 'Accepted immutable baseline bytes and mtime_ns; not a complete binary rehash.', 'inventory': artifacts},
        'protected_sources': {'compared': len(protected), 'sha256_unchanged': sum(protected.values()),
            'minimal_adapter_exceptions': {'rag/api.py': rag_adapter},
            'sha256_comparisons': dict(sorted(protected.items())),
            'all_frozen_implementation_bytes_unchanged_except_classified_installation': True},
        'personal_documents': personal,
        'tenant_catalogue_hnsw_or_kg_build_performed': False,
        'scope_limits': ['Global count is an estimate, not a complete 5M row digest.',
            'Protected binary preservation compares bytes and mtime_ns, not all binary content hashes.',
            'Personal SQLite preservation compares logical rows; transient database/journal physical bytes are intentionally excluded.'],
    }
    manifest = {
        'status': 'PASS', 'captured_at': stamped, 'baseline_sha256': baseline_sha,
        'method': 'Exact SHA-256 differences against immutable pre-implementation source inventory, with the same rg exclusions and suffix/size bounds.',
        'source_file_count': len(changed),
        'source_files': [{'path': name, 'absolute_path': str(ROOT / name),
            'kind': 'CREATED' if name not in before_sources else 'MODIFIED',
            'before_sha256': before_sources.get(name), 'sha256': sources[name]} for name in changed],
        'deleted_source_files': deleted,
        'excluded': ['reports/', '.scratch/', 'scratch/', '.git/', '.venv/', 'node_modules/', 'dist/', 'datasets/'],
        'baseline_operator_note': 'Files already present and byte-identical at immutable capture time are not falsely counted as changed.',
        'phase_operators_authored_before_capture': [{'path': 'scripts/institution_v2f_baseline.py',
            'absolute_path': str(ROOT / 'scripts/institution_v2f_baseline.py'),
            'kind': 'BASELINE_OPERATOR', 'sha256': sources['scripts/institution_v2f_baseline.py'],
            'note': 'Authored for this phase before capturing the immutable product-source baseline; listed separately from post-baseline differences.'}],
    }
    # All assertions precede PASS evidence publication. No source/private data writes.
    for name, payload in [('institution_v2f_preservation.json', result), ('institution_v2f_files_changed.json', manifest)]:
        (REPORTS / name).write_text(json.dumps(payload, indent=2, default=str), encoding='utf8')
    return result, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--after-qa-cleanup', action='store_true', required=True,
                        help='Confirm the root operator has finished and removed temporary personal QA artifacts.')
    parser.parse_args()
    try:
        result, manifest = capture()
    except (PreservationFailure, OSError, sqlite3.Error, ValueError) as error:
        # Do not serialize database rows, file content or arbitrary exception payloads.
        reason = str(error) if isinstance(error, PreservationFailure) else type(error).__name__
        print(json.dumps({'status': 'FAIL', 'reason': reason}))
        return 1
    print(json.dumps({'status': result['status'], 'TEST_books': result['TEST']['ACTIVE_records'],
        'TEST_holdings': result['TEST']['holdings'], 'TEST_resources': result['TEST']['retained_asset_count'],
        'protected_artifacts': result['artifacts']['compared'],
        'protected_source_comparisons': result['protected_sources']['compared'],
        'unchanged_protected_source_hashes': result['protected_sources']['sha256_unchanged'],
        'personal_registry_rows': result['personal_documents']['retained_personal_QA_rows'],
        'changed_source_files': manifest['source_file_count']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
