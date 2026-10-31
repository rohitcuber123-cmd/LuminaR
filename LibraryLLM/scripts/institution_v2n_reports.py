"""Evidence-backed N review bundle. Never deploys or mutates production state."""
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); R = ROOT / 'reports'
PRODUCT = ['backend/database/mongo_configuration.py', 'backend/database/mongodb.py', 'search/luminar_search.py', 'search/maintenance.py']
KNOWN = ['tests.test_assistant_backend::test_protected_rag_files_match_original_hashes',
         'tests.test_lexical_api_fallback::test_search_route_works_with_failed_lexical_and_keeps_public_schema']


def read(name): return json.loads((R / ('institution_v2n_' + name + '.json')).read_text())
def write(name, value): (R / ('institution_v2n_' + name + '.json')).write_text(json.dumps(value, indent=2, default=str), encoding='utf8')
def md(name, value): (R / ('institution_v2n_' + name + '.md')).write_text(value.strip() + '\n', encoding='utf8')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def totals(rows): return {key: sum(row.get(key, 0) for row in rows) for key in ['passed', 'failed', 'skipped']}


def docs():
    host = read('host_audit'); inventory = read('client_inventory'); boundary = read('boundary')
    clients = read('client_inventory_baseline')['clients']
    md('architecture', '''# Architecture and identity boundaries

AUDITED source: scripts/start_local.py supervises Core8002, Search8003, Recommendation8004, RAG8005 and Vite5173; it loads one shared environment and is guarded for local development. It can create an unauthenticated loopback Mongo for its own local database. It is not a production authentication cutover launcher. Actual database luminar_library does not satisfy its luminar_local guard. No launcher was executed in N.

Core imports backend.database.mongodb once per process; registration/membership, Staff/platform, catalogue, circulation, events, notifications, analytics and digital assets share that client. Recommendation imports it for history/feedback/catalogue. RAG imports it through book/private authorization and its library document worker. Personal document/session registries and model artifacts also use SQLite/filesystem; Mongo authentication does not secure those files. Search owns a distinct global catalogue client plus backend tenant client. Its resident tenant worker reuses the backend client; telemetry has an independent restricted writer. Both diagnostic CLIs use an independent read-only client. Frontend has no Mongo client or credential delivery path.

```mermaid
flowchart LR
  Core --> Shared[backend Mongo client per process]
  RAG --> Shared
  Recommendations --> Shared
  Search --> Catalogue[Search catalogue client]
  Search --> Native[Resident tenant worker]
  Native --> Shared
  Native --> Observer[Opt-in observer]
  Observer --> Writer[Separate restricted writer]
  Operator[Local diagnostics] --> Reader[Separate DB reader]
  Shared --> DB[(Selected application database)]
  Catalogue --> DB
  Writer --> DB
  Reader --> DB
```

Source/import dependency edges and line references: client_inventory.json and permission_inventory.json. These are conservative Python import closures, including conditional imports, rather than an execution proof for all deployed processes. Current service ownership is not established for the application processes. Supplemental boundary inspection maps MongoDB Windows service to NetworkService; current deployment classification remains UNKNOWN.
''')
    rows = ['# Mongo clients and connection behavior', '', f'Baseline scan parsed {read("client_inventory_baseline")["python_files_parsed"]} Python files, found {len(clients)} constructor sites; no parse failures. Current scan and symbols are in client_inventory.json. All client arguments are recorded as names/options, never URI values.', '',
            '| Source | Function | Classification |', '|---|---|---|']
    rows += [f"| `{c['path']}:{c['line']}` | {c['function']} | {c['scope']} |" for c in clients]
    rows += ['', 'Five baseline runtime client sites are backend/database/mongodb.py, search/luminar_search.py, search/maintenance.py, library_worker_telemetry.py and library_operator_access.py. N consolidates the first three constructors behind backend/database/mongo_configuration.py. Multiple helper constructors in the current inventory include the authenticated connection and short-lived deny-only probe; they do not create another resident worker.', '',
             'Core/RAG/Recommendation/native credential source: MONGO_URI/MONGO_DB_NAME after dotenv load; Search formerly used equivalent defaults with a separate pool. Legacy development permits MongoClient(None) or localhost default. Explicit authenticated mode now requires username/password, URI database equal to explicit selected DB, explicit authSource, supported SCRAM and bounded qualification. Invalid login never reaches the anonymous deny probe or an application fallback. Pool and steady-state retry semantics stay with PyMongo defaults/callers; only authenticated startup gains 3s selection/connect bounds and a10s qualification deadline.', '',
             'Backend imports create the reading_list unique index immediately. Core lifespan creates more indexes and starts existing due/outbox workers unless explicitly disabled in a fixture. Search initializes IndexManager and resident tenant builds after model startup. Manual maintenance is an operator action, never executed globally here. Telemetry remains exact flag1 plus dedicated URI, pool2, acknowledged journaled writes and500ms bounds. Operator requires explicit loopback SCRAM URI and one DB-local builtin-read role; it imports no application index initializer.', '',
             'Tests and historical/controlled scripts also connect directly. Their full line/function records appear above and in the machine inventory. Migration/seed/import scripts can write, index or drop their owned databases; none is automatically production-approved by the new application mode. They require individual approved maintenance wrappers and the appropriate explicit DB. Existing historical test fixtures retain anonymous loopback test configuration and are unchanged. Exec-generated prior harnesses are identified by their source templates; runtime trace supplements static scanning.', '',
             'INVENTORY COMPLETENESS: repository constructor/config/import sites audited; exact deployed process graph and all dynamically selected collection/action edges are NOT fully qualified. MONGO_CLIENT_INVENTORY_COMPLETE remains NO under the request\'s exact minimum-per-process standard. Supplementary scan limitations and unresolved dynamic paths remain explicit. No Motor runtime constructor found.']
    md('mongo_clients', '\n'.join(rows))
    md('security_boundary', '''# Actual security boundary

AUDITED, read-only: host_audit.json and boundary.json. Mongo8.3.4 responds on loopback27017. getCmdLineOpts reports bindIp127.0.0.1 and authorization absent; configured connection has zero authenticated users and anonymous tenant _id read succeeds. That establishes absent database authorization for this local endpoint, not public internet exposure. No remote write/read probe was attempted.

Supplemental PID5548 lookup identifies Windows service MongoDB, Running/Auto, StartName NT AUTHORITY\\NetworkService. Process owner retrieval remains NOT_VERIFIED and executable path unavailable through that provider. The generic listener inventory returned zero rows despite connectivity; absence of application process records does not prove those services are stopped. Service owner approval and deployment purpose remain unconfirmed.

Domain/Private/Public firewall profiles report enabled. Default action fields are raw0/NotConfigured; effective inherited policy, port-specific rules, router/NAT and remote reachability are NOT_VERIFIED. CURRENT_EXTERNAL_EXPOSURE UNKNOWN. No firewall mutation occurred.

Database path C:\\Program Files\\MongoDB\\Server\\8.3\\data has NetworkService full control and inherited Builtin Users/application-package ReadAndExecute grants at the directory. This is directory-level evidence, not a recursive ACL/effective access audit of every data file. Review actual child file ACLs under approved owner control before migration. Backup location/retention/encryption/restore ownership NOT_VERIFIED; no production data export performed.

Application Mongo roles cover collections, not tenant rows. Infrastructure credentials remain trusted service secrets; users, tenants and Platform Admin still pass application JWT and current membership checks. Mongo authentication does not replace document filesystem/SQLite/DPAPI and code integrity boundaries. Actual security qualification remains incomplete.
''')
    md('authentication', '''# Authentication evidence and constraints

IMPLEMENTED IN SOURCE: backend/database/mongo_configuration.py, integrated in backend/database/mongodb.py, Search constructor and manual maintenance constructor. LUMINAR_MONGO_MODE=AUTHENTICATED is explicit opt-in, never selected in the actual environment. DEVELOPMENT remains the legacy default and is not production-secure. No .env or service configuration was changed.

The gate checks explicit credentials/database/authSource/SCRAM, forces authenticated connectionStatus, verifies existing selected DB visibility with authorizedDatabases, reads only an impossible readiness _id from users, then demands denial13/18 for an unauthenticated read of a never-created readiness namespace. It never writes that namespace or returns its anonymous client. Bad login fails before this probe, which only verifies enforcement after a successful authenticated login. Unexpected probe/network behavior fails closed. Invalid/wrong/unavailable/missing DB cannot proceed to import-time index creation. Startup has a10s deadline without imposing that deadline on later runtime operations.

ACTUAL SERVER TESTS: focused.xml/log, test_mongo_authentication.py and authenticated application/native reports. Valid login succeeds; anonymous/invalid credential/wrong authSource/wrong DB/unrelated role/forbidden namespace/write are denied; role-scoped reconnect and config rollback preserve data. A separate owned server with valid users but authorization disabled is rejected by the gate. Tests verify no unrestricted fallback and no secret-bearing error text or repr. Steady-state service-level logs/retry handling are inherited and not globally rewritten.

The visibility check uses [MongoDB authorizedDatabases semantics](https://www.mongodb.com/docs/manual/reference/command/listdatabases/) and does not need a cluster-wide listDatabases grant. Synthetic principals are randomly generated in memory. Fixture administrator is used only for provisioning/seeding, lease fault injection, dump/restore and cleanup; actual application/native actions use fixture_application. That role is a named-resource compatibility envelope, broader than deployment minimum due to synthetic setup/cleanup. It must not be provisioned in production.
''')
    md('configuration', '''# Configuration compatibility

Opt-in contract: LUMINAR_MONGO_MODE=AUTHENTICATED, nonempty MONGO_URI containing SCRAM username/password, URI database exactly MONGO_DB_NAME, explicit authSource. Prefer a DB-local application principal; an explicitly chosen admin authSource can be used when supported by the reviewed deployment. Never infer authSource or use an anonymous fallback. A typo/missing selected DB fails before schema initialization. Unsupported/unknown mode fails with fixed safe code.

Implementation paths: backend/database/mongo_configuration.py; backend/database/mongodb.py client before reading_list create_index; search/luminar_search.py separate catalogue client; search/maintenance.py manual operator constructor. Search still loads its existing models before its late direct-client initialization; backend imports may qualify earlier. No global Search algorithms, ranking/model logic, native store/worker, RAG or Recommendation algorithm changed. No maintenance/rebuild command was executed against current data.

DEVELOPMENT preserves default URI/database and lazy client behavior. A legacy credential-bearing URI still uses existing driver authentication, but full enforcement/readiness qualification is guaranteed only in explicit authenticated mode. Existing tests/configurations do not become production-secure by continuing to work. Diagnostics/telemetry retain their independent stricter parsers and do not inherit MONGO_URI.

Authenticated fixture verifies Core lifespan/index initialization, Staff login, tenant routes and native worker. Historical seed/migration/import CLIs that directly construct clients remain independently inventoried and unqualified for unattended deployment. Shared start_local.py environment cannot independently rotate per-service URI without a reviewed launcher/service boundary. No production launcher or secret injection was installed here.
''')
    md('secret_management', '''# Secret delivery and rotation plan

AUDITED: secret_audit.json records .env key names/presence and potential credential-URI patterns without values. host_audit.json records .env/code/log/artifact DACL metadata. Existing project dotenv is loaded by backend and Search, and the local launcher passes one inherited environment to children. Mongo URI currently has no native credentials; telemetry/operator URI and exact enabled flags are absent. Runtime Windows application identities remain unconfirmed; Mongo service StartName is NetworkService. No frontend Mongo delivery exists.

DESIGNED, not installed: owner assigns existing service accounts and trusted code/launch directories first. Enroll separate application, telemetry-writer and operator-reader secret files using Windows SecureString Export-Clixml DPAPI under each actual execution identity/profile. Protect each parent/file for only its service SID/current owner and SYSTEM, with operator readers unable to read application/writer secrets. M's accepted current-user DPAPI/ACL fixture proves only same-user/machine handling, not a production NetworkService profile or cross-account launcher. See frozen institution_v2m_secret_management.md and secret fixture evidence; no external vault infrastructure is assumed.

Future protected launcher imports the correct DPAPI file inside the actual service identity, injects MONGO_URI/MONGO_DB_NAME/LUMINAR_MONGO_MODE only into its child environment, starts the process, removes the parent variable, and emits fixed safe errors. Avoid password/URI argv, plaintext config/log output or browser/build variables. Restrict code write access as well as secret read access: a writable launcher can steal a decrypted secret. Existing .env must be protected under separately approved ACL work before any production credential is placed there.

Independent rotation: DBA creates an equally scoped replacement principal, enrolls replacement DPAPI material under the assigned identity, validates in disposable deployment-equivalent services, then stops/restarts only the approved client processes and revokes old fresh logins after drained pools are confirmed. Never drop native locks/jobs, reset pointers or disable authorization to rotate. Current local launcher shares one URI and is a dependency to close before independent service rotation is claimed. No production secret/account/password was created or changed.

Synthetic mongodump/mongorestore uses a task-owned ACL-protected temporary YAML directory, password URI supplied through stdin during file creation, never argv/report. It contains only disposable credentials and is removed with its owned fixture. This is distinct from a production DPAPI enrollment. [Microsoft Export-Clixml documentation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/export-clixml?view=powershell-7.4) describes Windows credential encryption; actual deployment account qualification remains mandatory.
''')
    md('acl_review', '''# Windows ACL review

AUDITED read-only: host_audit.json filesystem_acls and boundary.json database_path_acl. Project .env owner Builtin Administrators, protected DACL, but Authenticated Users Modify and Builtin Users ReadAndExecute. Code launcher, local logs, tenant intelligence artifacts and rag/private_documents include broad inherited local-group grants. Database directory has NetworkService full control plus inherited Users/application-package read/execute. No recursive effective-access certification is claimed.

Current interactive identity observed as ROHIT-PC\\Rohit Siddani. Workspace path naming does not establish execution owner. MongoDB Windows service declares NetworkService; actual app service accounts/secret enrollment contexts are unknown. No current .env, service-account ACL, database path DACL or firewall rule was modified. Only newly created owned temporary tool-secret directories received fixture ACLs.

Review is complete as an evidence inventory with NOT_VERIFIED child-file/effective-access/account gaps. Hardening is not complete. Owner-approved follow-up must preserve recovery access, protect executable code/launcher/secret parents and files, separate readers from writers, verify actual service profile DPAPI decrypt/restart/rotation, and establish backup ACLs. Do not remove inherited ACEs or change service identities by applying a generic copied ACL. Actual production approval and deployment qualification remain absent.
''')
    md('migration_plan', '''# Controlled migration runbook for operator review

DESIGNED ONLY. NOT APPROVED, NOT EXECUTED. Target class UNKNOWN; no current credential, authorization, service, URI, ACL or firewall changed. Single standalone service is observed; replica-set/rolling availability and zero-downtime migration are not established. Plan an approved full application maintenance window with an explicit no-write interval and evidence-based duration after a representative rehearsal.

1. Installation owner classifies endpoint and approves named DBA, application/Search/RAG/Recommendation, Windows service/secret, backup and incident owners. Capture approved DB/host/service/config paths, Mongo8.3.4/tool compatibility, actual launcher/process inventory, listener/firewall scope, disk free space and protected rollback copies. Refuse execution while any are unknown.
2. Complete dynamic per-process permissions from source plus traced representative full-stack workload. Reconcile import-time indexes/upserts/aggregation lookups and global Search queue collection, and remove fixture-only grants. Install no wildcard/root/readWrite application role. Validate exact approved credentials on a separate auth-enabled clone seeded with approved synthetic data, including full Qwen/global Search/recommendation dependencies and all maintenance CLIs that will be used.
3. Backup owner supplies approved encrypted backup of all intended databases and required config/users/roles, tenant source files/artifacts, private SQLite/documents and global artifact manifests; record checkpoint/retention/access/hash and restore commands. Under separately authorized work, test restoration to an isolated host and compare collections, BSON/logical totals, indexes/options/validators, required roles and cross-store generation pointers. N did not export private current data. Missing approved restore evidence is an abort condition.
4. Agree maintenance window, outage notice/communications and write freeze. Stop accepting mutations and drain Core/API/document/native work through existing lifecycle controls; record in-flight fenced jobs and last-good pointers. Do not auto-recover, unlock or cancel. Stop all approved app/worker processes and verify no unknown writers. Keep telemetry off.
5. DBA, in a protected local administrative context under separately granted cutover approval, provisions the reviewed administrator/recovery and scoped client roles/principals with prompted random secrets. No credential in argv/log/source. On a no-auth standalone instance, minimize the local provisioning interval and retain owner-controlled host isolation; order must be rehearsed and approved before this step. Stage identity-specific DPAPI secrets/launcher environments, without launching clients against the unauthenticated server: explicit authenticated mode intentionally rejects that state.
6. DBA validates backup/config/roles, changes only the approved mongod authorization configuration, and restarts only the approved MongoDB service within the window. Keep the previous protected config for operator rollback, never automatically restore no-auth operation. Verify authenticated administrative access, authorization enabled, intended DB exists, and anonymous deny before app startup. Abort on Mongo health/auth/restore discrepancies.
7. Start Core in AUTHENTICATED mode with its reviewed application identity; qualification must precede index initialization. Validate login, Staff/platform, registration/membership, inventory/lending/reservation/fees/events/notifications/analytics/assets and private isolation. Start Search with its reviewed client identity and resident worker; validate read-only status first, preserve uncertain jobs for manual recovery. Only explicitly requested disposable/canary work can build. Then start Recommendation and RAG with reviewed identities; validate entitlement/current membership, history, document workers and external dependencies. Start frontend last; it receives no DB secret.
8. Independent operator runs J/L read-only diagnostics, verifies preserved generation/artifact/queue checkpoints and fresh auth-denied negatives in approved synthetic scope. No production write-denial experiments against tenant/global collections. Keep telemetry disabled even if its role/secret is staged. Reopen writes only after all owners sign validation evidence.
9. Observe actual error/latency/pool behavior through approved logs; verify no secret output, new empty DB, denied legitimate operations or unsolicited build/recovery. Rotate/revoke temporary commissioning credentials through a separately reviewed procedure. Remove no-auth contingency paths only with owner approval. Archive sanitized evidence and exact next rollback checkpoint.

Abort: unexpected client/owner/data delta; no tested restore; incomplete roles/secrets; anonymous read still allowed; valid credentials denied; fresh empty DB; Core/Search/RAG/Recommendation startup or private isolation failure; worker uncertain publication; missing last-good artifact; Mongo restart/unavailability. Keep clients stopped and writes closed. Follow rollback.md, not an automatic security-disable action. A later separately authorized cutover is required; this document is reviewable preparation only.
''')
    md('backup_restore', '''# Backup and restore readiness

Actual approved backup arrangement, location/access, retention, RPO/RTO, owner and tested restore: NOT_VERIFIED. Installed MongoDB Database Tools were located, but installation does not establish a backup. No current private Mongo collection was exported, and no application data was deleted. Real deployment restore is not qualified.

TESTED IN ISOLATED FIXTURE: backup_restore_fixture.json, mongodump.log and mongorestore.log. Real Database Tools dump and restore151 synthetic books plus library/native/telemetry collections into a new owned database. Six collection snapshots compare exact BSON content hashes/counts, full index specs and collection options/strict validator; source fixture remains unchanged. Includes empty indexed collections and auxiliary validator. Destination was absent before restore. Task administrator handles tools; runtime does not receive backup or restore powers. Temporary synthetic YAML credential config is ACL-protected and removed with its owned Mongo root.

Initial restore using a URI database path produced exit0 with zero documents because the tool treated the input differently. Independent content/index assertions caught this; the no-op log and initial difference are retained. The corrected tool URI omits a default DB and uses explicit DB dump/nsInclude/nsFrom/nsTo restore. Both tool success and snapshot equivalence are required. See [official mongodump --config documentation](https://www.mongodb.com/docs/database-tools/mongodump/).

Synthetic restoration proves this fixture only: no production users/roles restore, filesystem/SQLite synchronization, full5M/global artifacts, crash-consistent checkpoint, physical disaster recovery or real retention/restore time is established. Approved future backup must include every authoritative store and a coherent publication checkpoint; restoration must keep tenant generations paired with corresponding durable Mongo pointers. Do not restore an old data checkpoint over new writes merely to roll back a credential/config change.
''')
    md('rollback', '''# Controlled rollback and abort handling

DESIGNED production procedure, TESTED limited fixture cases. No automatic authorization disable, data restore, native job recovery, cancellation or lock removal exists. Before cutover record last-known-good scoped principals, protected launch/config/secret versions, Mongo service configuration, dataset/artifact/pointer checkpoint and owner contacts. Keep user writes closed on uncertainty.

Invalid password/wrong authSource/DB/role: fixed-code startup gate fails before import-time index initialization. Authorized operator restores the previously validated scoped secret/env and restarts only the affected client. If a permission is genuinely required, DBA reviews source/trace and applies only that action/resource, then repeats disposable tests; never temporarily substitute root/anonymous app credentials. Fixture wrong-password→known-good reconnect passes with unchanged user count and no fresh DB created.

Worker startup/Search connection failure: keep Search stopped and telemetry off, preserve native jobs/pointers/fences/lease records and last-good files. Restore reviewed connection configuration; read-only diagnostics checks state. Authenticated real-process crash/restart tests preserve both jobs and pointers. After explicit fixture-only lease expiry and manual library-admin recovery, prepublication state resolves FAILED, postpublication acknowledgment loss resolves SUCCEEDED. Restart alone never rebuilds or recovers.

Staff/Core failure: restore its validated scoped URI and code release under protected service ownership; withhold traffic until login/lifespan/index/private authorization checks pass. RAG failure: keep document intake/jobs stopped, restore its validated secret/config; validate current membership/asset/entitlement and artifact access before restart. Recommendation failure: preserve feedback/history, restore its scoped connection and verify reads/feedback plus Search dependency. Do not rewrite data or widen a tenant role to repair an infrastructure credential.

Telemetry auth failure: leave telemetry disabled (or approved future operator disables exact opt-in flag and restarts only its approved host process); preserve auxiliary singleton/history and all native state. Separate writer rotation/read-only denial remains tested by frozen L/M suites and fresh N Mongo denials/CLI. Telemetry cannot trigger native recovery.

Mongo unavailable after approved restart: keep all clients stopped/write freeze; DBA checks service log/config/storage/ownership, protected current config and administrative credentials. A return to no-auth is a distinct security regression requiring explicit DBA/security/installation-owner authorization, host isolation and a new maintenance decision, never automatic application rollback. Prefer repairing authenticated configuration and reconfirming restore prerequisites. N did not perform a real service restart or prove this failure recovery on the actual server.
''')
    md('deployment_readiness', '''# Deployment readiness decision

PART_2N_RESULT PARTIAL. AUDITED: source clients/configuration, source action lower bounds, conservative import closures, local Mongo anonymous behavior, Windows service name/StartName, selected ACLs and firewall profiles. IMPLEMENTED: explicit application authenticated-mode qualification and safe connection errors at three application connection sites. TESTED: disposable auth enforcement/negatives, bounded application identity/API workloads, actual native worker, independent writer/reader, rollback, paired timings and synthetic Database Tools restore.

NOT QUALIFIED FOR DEPLOYMENT: deployment purpose/owner UNKNOWN; exact dynamic per-service minimum grants and full representative full-stack workload remain incomplete; real backup/restore and cross-store checkpoint absent; actual service-account DPAPI/launcher/ACL hardening and effective network policy not approved/verified. Current server authorization absent, shared credentials not configured, broad local secret/code/data directory ACL grants observed. Two preexisting backend failures remain visible.

PRODUCTION APPROVED NO. ACTUALLY DEPLOYED NO. No actual Mongo authorization/configuration/user/password/URI/firewall/service ACL/restart change, no telemetry activation, no global HNSW/KG rebuild, no commit/deploy. Fixture roles and test results are not production approval. Obtain named installation/DBA/app/Search/RAG/Recommendation/Windows-secret/backup/incident approvals for a separately scheduled migration; do not infer approval from the user's instruction to continue this readiness phase.
''')
    md('improvement_review', '''# Improvement review

N closes a source-level readiness gap: explicit authenticated mode now checks actual authenticated identity, existing selected DB and denied anonymous access before import-time indexes. It retains deliberate development behavior and startup-only deadlines, sanitizes connection errors and never substitutes anonymous application access. New actual-server tests catch invalid credentials, authorization-disabled servers and a database typo. Three connection-site changes avoid service-specific inconsistent fallback.

Fresh application rehearsal uses a separate named-resource identity rather than the root maintenance account. Source and runtime evidence exposed missing migration marker/asset job permissions and the collStats need for catalogue totals; corrections remain fixture-only and traceable. A real no-op mongorestore exit0 was caught by content/index/validator equivalence, showing why exit status alone is insufficient. Real native crashes establish restart preservation and manual recovery under the application credential.

Remaining evidence gaps prevent PASS. The compatibility envelope intentionally includes setup/cleanup grants; a source lower bound is not a deployable least-privilege role. The local shared launcher, dynamic call edges, full model/global workloads, approved real restore, actual service identities/DPAPI profiles and effective remote network boundary require owner-led qualification. No unrelated Search/RAG/Recommendation algorithm changes or new maintenance automation were introduced.
''')
    md('next_scope', '''# Next recommended scope

Stop after Part2N. Next authorized planning scope should assign installation/DBA/application/Search/RAG/Recommendation/Windows-secret/backup owners and classify the endpoint. Close source/runtime dynamic privilege edges and trace a representative authenticated full-stack deployment with real service profiles and protected code/secret delivery. Approve and test a coherent real backup/restore in an isolated environment under a separate data-handling authorization, then review the downtime/rollback runbook and resolve the two preexisting backend failures.

Only after those prerequisites are evidenced should an operator request a separate, explicit authentication cutover maintenance window. Telemetry enablement remains a later separately approved action after Mongo/application readiness; do not couple it to authentication migration. No authorization switch, production user provisioning/rotation, ACL/firewall change, service restart, automatic recovery/maintenance or global rebuild is authorized by this completed readiness scope.
''')


def finalize():
    docs()
    from scripts.institution_v2i_baseline import capture_state
    from scripts.institution_v2l_baseline import capture_indexes
    baseline = read('baseline'); checks = read('final_backend'); front = read('final_frontend')
    assert checks[-1]['group'] == 'events' and any(row['group'] == 'institution_v2n' for row in checks)
    assert len(front) == 3 and all(row['exit'] == 0 for row in front)
    failures = []
    for path in R.glob('institution_v2n_final_*.xml'):
        for case in ET.parse(path).iter('testcase'):
            if any(child.tag in {'failure', 'error'} for child in case):
                failures.append(case.attrib['classname'] + '::' + case.attrib['name'])
    assert sorted(failures) == sorted(KNOWN), failures
    app = read('application_results')
    assert len(app) == 13 and not any(row['exit'] for row in app), 'Authenticated fixture evidence still has failures'
    native = read('native_results'); backup = read('backup_restore_fixture'); benchmark = read('benchmark_results'); operator = read('operator_fixture')
    assert native.get('owned_fixture_removed') and native.get('authenticated_success') and backup['result'] == 'PASS' and benchmark.get('owned_fixtures_removed') and operator.get('owned_fixture_removed')
    state = capture_state()
    state['global_KG_metadata'] = {p.relative_to(ROOT).as_posix(): {'bytes': p.stat().st_size, 'mtime_ns': p.stat().st_mtime_ns} for p in (ROOT / 'knowledge_graph/data').glob('*') if p.is_file()}
    state = json.loads(json.dumps(state, default=str)); indexes = json.loads(json.dumps(capture_indexes(), default=str))
    changes = [name for name, digest in baseline['source_sha256'].items() if not (ROOT / name).exists() or sha(ROOT / name) != digest]
    unexpected = [name for name in changes if name not in PRODUCT and 'institution_v2n' not in name]
    frozen = [name for name, digest in baseline['frozen_reports_sha256'].items() if not (ROOT / name).exists() or sha(ROOT / name) != digest]
    state_changes = [key for key, value in baseline['state'].items() if state.get(key) != value]
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    preservation = {'result': 'PASS' if not unexpected and not frozen and not state_changes and indexes == baseline['mongo_indexes'] and head == baseline['head'] else 'FAIL',
                    'expected_product_changes': [n for n in changes if n in PRODUCT], 'unexpected_previous_source_changes': unexpected,
                    'frozen_I_J_K_L_M_reports': len(baseline['frozen_reports_sha256']), 'frozen_report_changes': frozen,
                    'state_changes': state_changes, 'mongo_indexes_unchanged': indexes == baseline['mongo_indexes'], 'head_unchanged': head == baseline['head'],
                    'state_after': state, 'I_status_sha256': sha(ROOT / 'backend/services/library_intelligence_service.py'),
                    'limits': 'Global count estimated, not full5M digest; large artifact size/mtime vs bounded tenant hashes. Personal registry logical state compared. Own disposable fixture mutations/cleanup only.'}
    write('preservation', preservation); assert preservation['result'] == 'PASS', preservation
    text = (R / 'institution_v2n_final_frontend.log').read_text(encoding='utf8')
    ft = {key: sum(map(int, re.findall(r'^.*?\b' + key + r' (\d+)\s*$', text, re.M))) for key in ['tests', 'pass', 'fail', 'skipped']}
    assert ft['pass'] > 0 and ft['fail'] == 0
    warning_lines = lambda content: {line for line in content.splitlines() if ': warning ' in line}
    new_warnings = sorted(warning_lines((R / 'institution_v2n_final_lint.log').read_text()) - warning_lines((R / 'institution_v2m_final_lint.log').read_text()))
    regression = {'result': 'PARTIAL_PREEXISTING_FAILURES', 'backend': totals(checks), 'groups': checks, 'preexisting_failures': failures, 'new_failures': [],
                  'frontend': ft, 'build': 'PASS', 'lint_exit': 0, 'new_lint_warnings': new_warnings,
                  'method': 'Unmodified frozen suites V1 through M plus new N in independent processes. Existing date-aligned Events wrapper; protected generated reports restored by accepted runner. No suppression/hash rebaseline.'}
    write('regression', regression)
    focused = next(row for row in checks if row['group'] == 'institution_v2n')
    write('security_tests', {'fresh_N': focused, 'actual_Mongo_server': True, 'application_auth_suites': totals(app),
                             'native': native, 'operator_cli': operator, 'known_harness_discoveries': ['Initial encoding typo corrected in new fixture only.', 'Missing institution_migrations and constant-named library_asset_jobs grants corrected in fixture role; initial denials retained.', 'Expected outsider404 corrected in new benchmark, no product behavior altered.', 'Tool URI default DB caused no-op restore; snapshot equality caught it and corrected invocation passes.'],
                             'limits': 'Named-resource fixture envelope is broader than minimum deployment roles; full external-model/global service workload not qualified.'})
    auth = read('benchmark_authenticated'); dev = read('benchmark_development')
    pairs = {}
    for key in ['connection_and_first_read', 'core_module_import_ms', 'core_lifespan_start_ms', 'catalogue_read', 'tenant_status', 'native_claim_ms', 'native_lease_renewal', 'private_rag_metadata_retrieval', 'recommendation_history_retrieval']:
        pairs[key] = {'development': dev[key], 'authenticated': auth[key]}
    write('performance', {'fixture_pairs': pairs, 'native_builds': {label: read('native_benchmark_' + label)['builds'] for label in ['development', 'authenticated']},
                          'model_load_separate': {label: read('native_benchmark_' + label)['model'] for label in ['development', 'authenticated']},
                          'operator_diagnostics': operator['commands'], 'limits': 'One machine, sequential paired runs, fresh owned servers, small synthetic151-book catalogue. No production SLO, causal authentication-only slowdown estimate or full5M/Qwen/semantic-rec endpoint claim. Connection timing includes enforcement gate and first read; Core index startup and Mongo caches vary. Native timings exclude explicit success-scenario delays; model loads reported separately. RAG metadata authorization/history retrieval is not model inference.'})
    isolation = {'result': 'PASS_TESTED_SCOPE', 'authenticated_real_JWT_fixture': auth['isolation'], 'two_private_library_UUIDs': True,
                 'private_institution_private_code': True, 'staff_password_login_http': auth['staff_password_login_http'],
                 'native_JWT_status_checks': read('native_success')['security'], 'authenticated_suites': totals(app),
                 'infrastructure_login_is_not_app_membership': 'Actual server login cannot mint JWT; current identity/membership guards remain unchanged.',
                 'platform_admin_no_tenant_bypass': 'Explicit approved fixture platform assignment user5 remains404 on unrelated private inventory/RAG metadata; frozen platform/tenant suites also exercised.',
                 'limits': 'Private RAG metadata and frozen asset pipeline tests, not fresh complete Qwen model serving across a full production stack.'}
    write('private_library_security', isolation)
    md('authenticated_rehearsal', f'''# Authenticated application rehearsal

TESTED IN ISOLATED FIXTURES: {totals(app)['passed']} passed, {totals(app)['failed']} failed, {totals(app)['skipped']} skipped across13 task-owned adapted copies of accepted V1/A–H/workspace/dashboard/catalogue/product suites. Detailed groups, original source SHA256 and timings: application_results.json; actual command metadata: auth_*_commands.json; XML/logs retained. Original tests remain unchanged and also run in normal full regression.

Only fixture scaffolding is adapted: explicit authenticated fixture URI/DB/env before application imports, own DB prefix guard, parent-owned cleanup in place of application dropDatabase, system namespace exclusion in synthetic cleanup, original source-root paths and N-specific generated report names. Test bodies otherwise retain domain assertions and their established dependency overrides/encoders. Those copies establish Mongo compatibility, not actual JWT/model behavior by themselves.

Separate benchmark_authenticated.json runs real Core lifespan and indexes, actual JWT decoder and Staff bcrypt password login, registers two private libraries, checks ADMIN/LIBRARIAN/GENERAL_USER/outsider/approved PLATFORM_ADMIN catalogue access, private RAG metadata authorization and recommendation history/book retrieval. Native success/crash children use actual JWT and cached MiniLM/FAISS/KG without dependency override. Operator CLIs use independent read-only credentials.

Domain suite coverage includes registration/membership, catalogue/inventory/import, circulation/reservations/fees, events/notifications, analytics, digital asset/private knowledge controls and Staff/platform boundaries. Fixture app identity has named collection data/index grants plus books collStats and DB listCollections, no root/readWrite/drop/user administration. Setup/cleanup and migration utility tests make this envelope broader than deployment minimum; source lower bounds and command traces must still be reconciled.

APPLICATION_AUTH_COMPATIBILITY PARTIAL: representative actual Mongo application paths pass, but full global5M Search/CrossEncoder, Qwen/document model HTTP serving, external Search-dependent semantic recommendation and every Knowledge Tools workflow under minimum per-service principals were not replayed end-to-end. Ordinary frozen regression is additional preservation evidence, not an authenticated full-stack substitute. No live app service was restarted or pointed at new credentials.
''')
    md('worker_rehearsal', '''# Authenticated native worker rehearsal

TESTED: native_results.json and native_success/crash/restart/manual JSON/logs. Actual search.library_intelligence.TenantIntelligence, accepted cached CPU all-MiniLM-L6-v2 revision, real FAISS Search and KG,151 synthetic tenant books per target. Backend connection is explicit AUTHENTICATED mode using fixture_application named resources, not root. Actual library-admin JWT requests build jobs; native code claims, renews, persists progress, validates artifacts, publishes atomically and acknowledges matching pointer/generation. Success events show more than one native heartbeat. Both Search and KG succeed; serial completion is checked.

Two genuine child exits77 after previously successful last-good KG generations exercise SERIALIZATION_ACK and ACKNOWLEDGEMENT_LOSS. Fresh authenticated restart changes neither saved native job nor target pointer and preserves last-good file hashes. Only fixture maintenance identity then expires that one owned lease to allow explicit existing library-admin recover endpoint. Prepublication resolves FAILED; postpublication resolves SUCCEEDED. Neither restart nor telemetry automatically starts a recovery/rebuild.

90s lease,10s renewal,2s idle, fencing, progress/publication/ack code, last-good behavior and manual recovery remain byte-preserved; N makes no native worker/store change. Existing frozen L protocol guard and J–M tests run unchanged in regression. Privileged serverStatus connection-count sampling is intentionally removed from this harness rather than granting it to the application identity. No model/store/worker method is replaced. Paired native benchmark reports model load separately and uses actual builder code. This qualifies the fixture identity/protocol, not unattended production worker ownership or a global build.
''')
    md('telemetry_readiness', '''# Telemetry and operator readiness

Part2L canonical implementation remains unchanged. Production exact flag remains off and dedicated writer/operator URI absent in host_audit.json. Actual source never provisions roles/namespace or falls back to application credentials. Fresh N server tests verify writer find/update on fixed auxiliary singleton plus find native jobs/targets and actual13 denials for native jobs, targets, generations, locks, catalogue, memberships and global DB mutations/reads. Named role does not grant insert/delete/index administration. Separate operator builtin-read principal can read and actual write is denied13.

Actual native authenticated success/crash/restart phases opt in only inside owned fixtures. Independent operator fixture invokes both J/L CLIs in JSON/text under separate credentials;12 calls succeed and a real restricted writer pulse succeeds. Native success reports observer lifecycle/metrics; reader/writer are not substitutes for current application membership and no public/Staff infrastructure route was introduced. Frozen L/M tests also retain wrong credentials, revocation/reconnect, epoch/future clock and shutdown contracts.

Telemetry production prerequisites remain absent: target classification, named ownership, authorization-enabled existing application deployment, protected service-specific secrets/code, real profile enrollment, approved backup/restore, exact roles and actual service launch/stop/rollback qualification. Telemetry is disabled by default and must receive a separate explicit later enablement approval even after authentication migration. No production telemetry activation occurred.
''')
    qa = {'PART_2N_RESULT': 'PARTIAL', 'CURRENT_MONGO_AUTH_ENABLED': 'NO', 'CURRENT_DEPLOYMENT_CLASS': 'UNKNOWN', 'CURRENT_EXTERNAL_EXPOSURE': 'UNKNOWN',
          'MONGO_CLIENT_INVENTORY_COMPLETE': 'NO', 'AUTHENTICATED_FIXTURE_PASS': 'YES', 'ANONYMOUS_FIXTURE_DENIED': 'YES', 'APPLICATION_AUTH_COMPATIBILITY': 'PARTIAL',
          'NATIVE_WORKER_AUTH_COMPATIBILITY': 'PASS', 'TELEMETRY_WRITER_ISOLATED': 'YES', 'OPERATOR_READ_ONLY': 'YES', 'SECRET_ACL_REVIEW_COMPLETE': 'YES',
          'MIGRATION_PLAN_COMPLETE': 'YES', 'BACKUP_RESTORE_QUALIFIED': 'FIXTURE_ONLY', 'ROLLBACK_FIXTURE_PASS': 'YES', 'PRODUCTION_MONGO_AUTH_CHANGED': 'NO',
          'PRODUCTION_CREDENTIAL_CREATED': 'NO', 'PRODUCTION_TELEMETRY_ENABLED': 'NO', 'GLOBAL_HNSW_REBUILT': 'NO', 'GLOBAL_KG_REBUILT': 'NO',
          'NEW_BACKEND_FAILURES': 0, 'PREEXISTING_BACKEND_FAILURES': 2, 'FRONTEND_TESTS': f"{ft['pass']} passed / {ft['fail']} failed / {ft['skipped']} skipped", 'PRODUCTION_BUILD': 'PASS',
          'NEXT_RECOMMENDED_SCOPE': 'Owner-led deployment classification, exact role/full-stack qualification, protected service identities and approved real restore; separate later cutover approval.'}
    write('qa_summary', qa)
    descriptions = [
        ('A', 'FINAL PASS / PARTIAL / FAIL', 'PARTIAL. Isolated readiness improvements pass; actual deployment and complete minimum-role/full-stack qualification remain incomplete.'),
        ('B', 'EXECUTIVE SUMMARY', 'Opt-in authenticated-mode fail-closed gate added at application client sites; source inventory/role lower bounds, auth-negative tests, actual native builds/crashes, synthetic restore and migration/rollback runbooks completed. No live cutover.'),
        ('C', 'CURRENT MONGODB SECURITY STATE', 'Mongo8.3.4 loopback27017, authorization absent, configured authenticated users0, anonymous tenant read allowed. Current auth NO. See host_audit.json.'),
        ('D', 'DEPLOYMENT CLASSIFICATION', 'UNKNOWN. Ownership/purpose unconfirmed; continuing readiness work is not cutover approval. Mongo Windows service NetworkService observed, application owners still unknown.'),
        ('E', 'DATABASE CLIENT INVENTORY', 'Five baseline runtime sites plus test/operator/script constructors inventoried with file/function/import/config evidence. Exact deployed/dynamic per-process graph incomplete; completeness NO. See mongo_clients.md and machine inventory.'),
        ('F', 'REQUIRED COLLECTION PERMISSIONS', 'Source action lower bounds with per-call evidence and actual command traces; fixture data/index/listCollections/books collStats grants are a compatibility envelope, not deployable minimum. See service_permissions.md.'),
        ('G', 'SERVICE IDENTITY DESIGN', 'Application connection boundaries follow actual process/shared client usage. Search and resident native worker share tenant identity. Independent operator reader/auxiliary writer and reviewed maintenance context; frontend receives no credential.'),
        ('H', 'AUTHENTICATED FIXTURE RESULTS', f"{focused['passed']} fresh actual-server security tests pass; anonymous, wrong credential/authSource/DB/role denied; valid-user no-auth server rejected. See security_tests.json."),
        ('I', 'APPLICATION COMPATIBILITY', f"{totals(app)['passed']} authenticated adapted domain tests pass plus actual Core lifespan, Staff login/JWT/private access and metadata/history checks. PARTIAL full-stack/model/minimum-role qualification; see authenticated_rehearsal.md."),
        ('J', 'NATIVE WORKER COMPATIBILITY', 'PASS fixture: actual cached MiniLM/FAISS/KG, claims/renewal/progress/validation/pointer acknowledgment, two genuine crashes, unchanged restart, last-good file hashes and explicit recovery. Protocol source unchanged.'),
        ('K', 'TELEMETRY WRITER SECURITY', 'Separate restricted writer enforced by Mongo, forbidden native/global writes denied13; live default remains disabled. No native-job authority added.'),
        ('L', 'OPERATOR READER SECURITY', 'Independent builtin-read principal; actual write denial13 and both diagnostics in JSON/text succeed. No app JWT/platform substitution or provisioning on import.'),
        ('M', 'SECRET MANAGEMENT', 'Existing dotenv flow/keys audited without values; DPAPI identity-specific launcher/rotation design, protected synthetic tool config exercised; real service-profile delivery unqualified. See secret_management.md.'),
        ('N', 'WINDOWS ACL REVIEW', 'Broad .env/code/log/artifact local grants and database directory read grants observed. Directory-level review with explicit unverified effective child-file/account scope; no production ACL changes.'),
        ('O', 'NETWORK EXPOSURE REVIEW', 'Loopback bind observed, firewall profiles enabled, effective port policy/NAT/remote reachability NOT_VERIFIED; external exposure UNKNOWN. Anonymous local read is not proof of internet exposure.'),
        ('P', 'PRIVATE LIBRARY ISOLATION', 'Two private UUIDs, PRIVATE_INSTITUTION/PRIVATE_CODE, owner/librarian/member/outsider/approved platform-admin checks preserved. Actual unrelated platform assignment receives404; private RAG metadata denied. See private_library_security.json.'),
        ('Q', 'MIGRATION SEQUENCE', 'Exact review runbook covers owners/roles/backup/write freeze/client drain/provision-secret staging/DB auth restart/startup order/checkpoints/abort/rotation; maintenance downtime assumed pending rehearsal. Designed, unapproved, unexecuted.'),
        ('R', 'BACKUP/RESTORE READINESS', 'FIXTURE_ONLY: actual Database Tools restore six synthetic collections with exact BSON/count/index/options/validator equality. Real approved backup/restore/cross-store recovery NOT_VERIFIED; no sensitive current export.'),
        ('S', 'ROLLBACK', 'Fixture wrong credential→known-good and native crash/restart/manual repair pass; exact per-service outage/role/authSource/Mongo restart rollback design. Never automatically disable security or restore old data over newer writes.'),
        ('T', 'PERFORMANCE', 'Paired owned anonymous-development vs authenticated Core/connection/read/status/claim/renewal/RAG metadata/history/native builds, separate model load and operator process latency. Small synthetic workload, no production SLO/causal auth-only estimate.'),
        ('U', 'TESTS AND REGRESSION', f"Backend {totals(checks)}; exactly2 known failures, zero new. Frontend {qa['FRONTEND_TESTS']}; build/lint pass; no new lint warnings. No frozen tests/hashes modified."),
        ('V', 'GLOBAL PRESERVATION', f"PASS: {len(baseline['frozen_reports_sha256'])} I–M reports, prior source except declared connection changes, current data/pointers/indexes/artifacts and Git HEAD preserved. TEST151/150/5, global estimated5M; limitations explicit."),
        ('W', 'FILES CHANGED', 'Four product files: new mongo_configuration.py, backend mongodb.py, Search constructor, manual maintenance constructor. New N tests/scripts/reports only; existing I optimization and L telemetry/native protocol preserved. No commit.'),
        ('X', 'REPORTS CREATED', 'All25 required reports plus raw inventory/command metadata/XML/logs/security/backup/native/performance/QA/acceptance/manifest evidence; task-only review package.'),
        ('Y', 'DEPLOYMENT BLOCKERS', 'UNKNOWN purpose/owners, exact dynamic minimum privileges, full model/global workload, real restore/checkpoint, protected actual service-profile launch/secrets/ACLs and effective network scope.'),
        ('Z', 'APPROVAL REQUIREMENTS', 'Named installation owner, DBA, Windows/service-secret, application/Search/RAG/Recommendation, backup and incident owners must approve a concrete later maintenance/cutover and rollback. No production approval inferred here; no confirmation requested to finish N.'),
        ('AA', 'IMPROVEMENT REVIEW', 'Explicit gate closes auth-disabled/empty-DB/fallback gaps. Real server denials refine fixture grants; content assertions caught a no-op tool restore. Lower bounds and fixture roles remain visibly distinct from deployment qualification.'),
        ('AB', 'NEXT RECOMMENDED PHASE', qa['NEXT_RECOMMENDED_SCOPE'] + ' Stop after N; no telemetry activation/global rebuild or unrelated phase.')]
    md('completion', '\n\n'.join('## ' + number + '. ' + title + '\n\n' + body for number, title, body in descriptions) + '\n\n## FINAL QA SUMMARY\n\n```text\n' + '\n'.join(f'{key}: {value}' for key, value in qa.items()) + '\n```\n\nKnown failures remain unsuppressed:\n\n' + '\n'.join('- ' + name for name in KNOWN))
    request = Path('C:/Users/balak/.codex/attachments/87748f8a-75b3-48a4-9ab9-d81f55253f64/Pasted text.txt').read_text(encoding='utf8')
    block = request.split('PART V — ACCEPTANCE CRITERIA')[1].split('Report PARTIAL')[0]
    criteria = re.findall(r'(\d+)\.\s+(.*?)(?=\n\s*\d+\.|\Z)', block, re.S); assert len(criteria) == 33
    write('acceptance', {'overall': 'PARTIAL', 'criteria': [{'number': int(n), 'requirement': ' '.join(value.split()),
                       'status': 'PARTIAL' if int(n) in {1, 4, 7} else 'FIXTURE_PASS_WITH_DEPLOYMENT_LIMITS' if int(n) in {5, 8, 12, 15, 17} else 'PASS',
                       'evidence': 'completion.md A–AB and linked machine/raw evidence; deployment_readiness.md documents unqualified boundaries.'} for n, value in criteria]})
    paths = sorted({p for p in [*R.glob('institution_v2n_*'), *(ROOT / 'scripts').glob('*institution_v2n*'), *(ROOT / 'tests/institution_v2n').rglob('*.py'),
                               *(ROOT / '.scratch/institution-v2n').rglob('*.py'), *(ROOT / name for name in PRODUCT)]
                    if p.is_file() and p.suffix != '.zip' and '__pycache__' not in p.parts and p.name not in {'institution_v2n_changed_files.json', 'institution_v2n_package_manifest.json'}})
    files = [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p),
              'category': 'product connection configuration' if p.relative_to(ROOT).as_posix() in PRODUCT else 'report/evidence' if p.parent == R else 'N owned harness/test/snapshot'} for p in paths]
    write('changed_files', {'product_paths': PRODUCT, 'baseline_changed_paths': changes, 'unexpected_previous_source_changes': unexpected, 'files': files,
                            'no_commit_deploy_or_production_activation': True, 'delivery_files': ['reports/institution_v2n_changed_files.json', 'reports/institution_v2n_package.zip', 'reports/institution_v2n_package_manifest.json']})
    paths.append(R / 'institution_v2n_changed_files.json')
    package = R / 'institution_v2n_package.zip'
    with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in paths: archive.write(path, path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(package) as archive:
        assert archive.testzip() is None
        entries = len(archive.namelist())
    write('package_manifest', {'package': package.name, 'bytes': package.stat().st_size, 'sha256': sha(package), 'entries': entries,
                                'scope': 'N source/config/tests/runbooks/evidence/owned harness snapshots only; no production secrets, fixture tool YAML, DB dumps, model/data/artifact payload.'})
    print(json.dumps({'result': 'PARTIAL', 'backend': totals(checks), 'authenticated_application': totals(app), 'frontend': ft, 'preservation': preservation['result'], 'package_entries': entries}))


if __name__ == '__main__':
    docs() if '--docs' in sys.argv else finalize()
