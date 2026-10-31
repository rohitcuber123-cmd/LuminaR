"""Owned N authentication laboratory. Administrative identity is provisioning only."""
import ast
import json
import secrets
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'scripts/institution_v2k_fixture.py').read_text(encoding='utf8')
source = source.replace('luminar-v2k-auth-', 'luminar-v2n-auth-').replace('luminar_v2k_fixture_', 'luminar_v2n_fixture_')
exec(compile(source, str(ROOT / 'scripts/institution_v2k_fixture.py'), 'exec'))


def resources():
    """Conservative named-resource envelope; exact operation matrix is separate.

    Includes test setup operations, so this is NOT deployment least privilege.
    No wildcard namespace, database administration, role administration or drop.
    """
    inventory = json.loads((ROOT / 'reports/institution_v2n_client_inventory_baseline.json').read_text())
    names = set(inventory['collection_export_aliases'].values())
    for row in inventory['resolved_collection_operations']:
        if row['path'].startswith(('backend/', 'search/', 'rag/', 'recommendation/')):
            names.add(row['collection'])
    evidence = {}
    for folder in ('backend', 'search', 'rag', 'recommendation'):
        for path in (ROOT / folder).rglob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
            constants = {target.id: node.value.value for node in tree.body if isinstance(node, ast.Assign)
                         and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
                         for target in node.targets if isinstance(target, ast.Name)}
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and node.args:
                    func = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ''
                    first = node.args[0]
                    if func == 'collection' and isinstance(first, ast.Constant) and isinstance(first.value, str):
                        name = 'institution_' + first.value
                        names.add(name); evidence.setdefault(name, []).append(f'{path.relative_to(ROOT).as_posix()}:{node.lineno}')
                    if func == 'collection' and isinstance(first, ast.Name) and first.id in constants:
                        name = 'institution_' + constants[first.id]
                        names.add(name); evidence.setdefault(name, []).append(f'{path.relative_to(ROOT).as_posix()}:{node.lineno}')
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'specs' for t in node.targets) and isinstance(node.value, ast.Dict):
                    if 'institution_repository' in path.name or 'library_' in path.name:
                        for key in node.value.keys:
                            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                                names.add('institution_' + key.value)
    # Accepted V1 suite also invokes its controlled migration utility. This grant
    # is fixture-only; deployment migration authority must be separate.
    names.add('institution_migrations')
    evidence['institution_migrations'] = ['scripts/migrate_institution_v1.py:45,68,103 (fixture migration tests only)']
    # Frozen test bodies seed non-runtime historical namespaces and invoke
    # maintenance migrations. These are compatibility-only, never app-role design.
    for name in ['historical_documents', 'private_documents', 'authority_migration_locks', 'institution_v2c_migrations']:
        names.add(name)
    evidence['historical_documents'] = ['tests/institution_v2f/test_asset_recovery.py:148,149 (synthetic setup only)', 'scripts/migrate_library_assets_v2f.py:42 (dry-run read)']
    evidence['private_documents'] = ['tests/institution_v2f/test_assets.py:488,490 (synthetic setup only)']
    evidence['authority_migration_locks'] = ['scripts/migrate_management_authority.py:88,118 (controlled utility only)']
    evidence['institution_v2c_migrations'] = ['backend/services/library_canonical_defaults.py:59 (dynamic read for safe promotion)']
    # Ignore unresolved parser symbols, paths and non-collection strings.
    names = {n for n in names if n and all(c.isalnum() or c == '_' for c in n)}
    return sorted(names), evidence


def provision_application(server):
    assert server.database.startswith('luminar_v2n_fixture_')
    names, evidence = resources()
    actions = ['find', 'insert', 'update', 'remove', 'createIndex', 'listIndexes']
    privileges = [{'resource': {'db': server.database, 'collection': n}, 'actions': actions} for n in names
                  if n != 'institution_worker_telemetry_v2k']
    # Real catalogue totals use estimated_document_count ($collStats), not find.
    # Source: backend/services/book_service.py:51 and routes/notifications.py:87.
    for privilege in privileges:
        if privilege['resource']['collection'] == 'books':
            privilege['actions'] = [*actions, 'collStats']
    privileges += [{'resource': {'db': server.database, 'collection': ''}, 'actions': ['listCollections']},
                   {'resource': {'db': server.database, 'collection': 'institution_worker_telemetry_v2k'}, 'actions': ['find']}]
    server.db.command('createRole', 'fixture_application_envelope', privileges=privileges, roles=[])
    server.app_password = secrets.token_urlsafe(32)
    server.db.command('createUser', 'fixture_application', pwd=server.app_password,
                      roles=[{'role': 'fixture_application_envelope', 'db': server.database}])
    server.app_uri = f'mongodb://fixture_application:{quote(server.app_password)}@127.0.0.1:{server.port}/{server.database}?authSource={server.database}'
    server.db.users.insert_one({'_id': '__fixture_database_exists__', 'fixture': True})
    return {'collections': names, 'privileges': privileges, 'collection_helper_evidence': evidence,
            'qualification': 'Named-resource compatibility envelope, includes synthetic fixture setup actions; not a deployment minimum-role claim.'}
