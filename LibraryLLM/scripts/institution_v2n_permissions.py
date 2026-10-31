"""Source-derived permission lower bound and conservative service import closures."""
import json
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; R = ROOT / 'reports'


def main():
    data = json.loads((R / 'institution_v2n_client_inventory.json').read_text())
    graph = data['import_graph']
    roots = {'Core': 'backend.main', 'Search_and_native_worker': 'search.api', 'Recommendation': 'recommendation.api', 'RAG_Qwen': 'rag.api'}
    closures = {}
    for service, root in roots.items():
        seen = set(); pending = [root]
        while pending:
            module = pending.pop()
            if module in seen: continue
            seen.add(module)
            for row in graph.get(module, []):
                imported = row['module']
                if imported in graph: pending.append(imported)
                pending.extend(imported + '.' + name for name in row['names'] if imported + '.' + name in graph)
        closures[service] = sorted(seen)
    action = {'find': ['find'], 'find_one': ['find'], 'aggregate': ['find'], 'distinct': ['find'],
              'count_documents': ['find'], 'estimated_document_count': ['collStats'], 'insert_one': ['insert'], 'insert_many': ['insert'],
              'update_one': ['update'], 'update_many': ['update'], 'replace_one': ['update'],
              'find_one_and_update': ['find', 'update'], 'find_one_and_replace': ['find', 'update'], 'find_one_and_delete': ['find', 'remove'],
              'delete_one': ['remove'], 'delete_many': ['remove'], 'create_index': ['createIndex'], 'create_indexes': ['createIndex'],
              'list_indexes': ['listIndexes'], 'index_information': ['listIndexes']}
    matrix = defaultdict(lambda: {'actions': set(), 'operations': set(), 'evidence': [], 'service_import_closures': set()})
    for row in data['resolved_collection_operations']:
        if not row['path'].startswith(('backend/', 'search/', 'rag/', 'recommendation/')) or '/scripts/' in row['path']: continue
        key = row['collection']; item = matrix[key]
        item['actions'].update(action.get(row['operation'], [])); item['operations'].add(row['operation'])
        item['evidence'].append({'path': row['path'], 'line': row['line'], 'function': row['function'], 'operation': row['operation']})
        module = row['path'][:-3].replace('/', '.')
        item['service_import_closures'].update(service for service, modules in closures.items() if module in modules)
    rows = []
    for name, item in sorted(matrix.items()):
        rows.append({'collection': name, **{k: sorted(v) if isinstance(v, set) else v for k, v in item.items()}})
    result = {'status': 'AUDITED_STATIC_LOWER_BOUND_NOT_DEPLOYMENT_ROLE', 'collections': rows, 'service_import_closures': closures,
              'scope': 'Core/Search/RAG/Recommendation module import reachability includes imports inside functions and branches; it does not imply every operation executes in every process.',
              'limits': ['Dynamic loops/specs, imported aliases, aggregation lookups, bulk models and script-passed databases require manual source and runtime trace reconciliation.',
                         'Implicit upsert needs insert as well as update where creation is possible; the listed update action alone is not a complete deployable grant.',
                         'Aggregate with lookups requires find on every source; $out/$merge would need additional output privileges. No broad aggregate privilege is invented.',
                         'No explicit runtime transactions or change streams found; implicit driver sessions do not justify cluster administration.',
                         'The fixture role includes all six data/index actions on named resources for test setup/cleanup, and is deliberately broader than this source lower bound.'],
              'deployment_role_qualified': False}
    (R / 'institution_v2n_permission_inventory.json').write_text(json.dumps(result, indent=2))
    lines = ['# Service permissions and least-privilege design', '',
             'Status: AUDITED/DESIGNED. Not a production-ready role definition. Source lower bounds and executed command metadata are separate from the named-resource compatibility fixture envelope.', '',
             '| Collection | Observed source actions | Source call sites |', '|---|---|---|']
    for row in rows:
        refs = ', '.join(f"`{e['path']}:{e['line']}`" for e in row['evidence'][:4])
        lines.append('| ' + row['collection'] + ' | ' + ', '.join(row['actions']) + ' | ' + refs + ' |')
    lines += ['', 'The complete per-operation evidence, functions and import closures are in [permission_inventory.json](institution_v2n_permission_inventory.json). Actual successful/failed commands by database/collection are in `institution_v2n_auth_*_commands.json`; they include fixture setup and must be separated before granting deployment rights.', '',
              'Core legitimately mutates identity/registration, memberships/security/audit, catalogue/holdings/copies/imports, durable circulation journals/locks, reservations/fees, events/outbox/notifications, assets/jobs, reading lists and platform assignment/audit records. Analytics reads aggregate sources but shared tenant barriers still insert/remove locks. Search hosts the native worker: jobs, leases, progress, target pointers, generations, sequences and audit require writes. Search queue bulk_write uses InsertOne models (`search/sync_queue.py:267`); grant insert on that actual passed collection, not arbitrary bulk authority.', '',
              'Recommendation reads books/issues/reservations/history/feedback and writes feedback. RAG rechecks current users/membership/asset permissions and its document worker claims/renews/publishes asset jobs; it is not purely read-only. All backend importers currently execute the reading_list unique-index initializer, so read-only service identities fail that initialization unless indexes are separately provisioned and initialization is deliberately redesigned in a later approved scope.', '',
              'Proposed boundaries: one application runtime identity initially where the common launcher supplies one shared environment; Search/native worker stays one identity until a real connection boundary exists. Separate operator reader (builtin read on one DB, no writes), telemetry writer (find/update auxiliary; find jobs/targets only), and controlled offline maintenance identity with exact migration/index/backup rights. Frontend receives no DB credential. Do not deploy the fixture role, reuse its root maintenance account, or grant root/readWrite/clusterAdmin/userAdmin to application processes.', '',
              'DB-level listCollections is required by accepted startup/index checks. createIndex/listIndexes are justified by startup and store initialization. Normal runtime does not drop databases/collections or administer users. Grant neither. Migration scripts run in a separate reviewed maintenance context; V1 marker find/update/insert on institution_migrations is justified by scripts/migrate_institution_v1.py:45,68,103. The fixture envelope includes it only because the unchanged V1 test bodies invoke that utility.', '',
              'Mongo actions and authorized-database visibility follow the [official privilege actions](https://www.mongodb.com/docs/manual/reference/privilege-actions/) and [listDatabases command](https://www.mongodb.com/docs/manual/reference/command/listdatabases/). Runtime tests establish server enforcement; this static lower bound alone cannot qualify a minimum production role.']
    (R / 'institution_v2n_service_permissions.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'resolved_runtime_collections': len(rows), 'role_qualified': False}))


if __name__ == '__main__': main()
