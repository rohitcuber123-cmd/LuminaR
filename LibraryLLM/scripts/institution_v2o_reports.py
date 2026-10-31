"""Part O evidence/runbooks; all unqualified and conflicting gates stay visible."""
import hashlib,json,re,subprocess,sys,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));R=ROOT/'reports'
PRODUCT=['frontend/src/pages/LibraryIntelligence.tsx','frontend/src/lib/libraryIntelligence.ts','frontend/package.json',
         'search/query_execution.py','search/luminar_search.py','search/maintenance.py','scripts/build_lexical_sidecar.py','scripts/lexical_worker.py','scripts/lexical_maintenance.py']
OLD='tests.test_assistant_backend::test_protected_rag_files_match_original_hashes'
NEW='tests.institution_v2j.test_diagnostics::test_existing_staff_status_unchanged'
def read(n):return json.loads((R/f'institution_v2o_{n}.json').read_text())
def write(n,v):(R/f'institution_v2o_{n}.json').write_text(json.dumps(v,indent=2,default=str),encoding='utf8')
def md(n,v):(R/f'institution_v2o_{n}.md').write_text(v.strip()+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def totals(rows):return {k:sum(r.get(k,0) for r in rows) for k in ['passed','failed','skipped']}


def documents():
    md('existing_ux_audit','''# Existing UX audit and implementation boundary

Audited before editing: frontend/src/pages/LibraryIntelligence.tsx, pages/LibraryIntelligence.css, lib/libraryIntelligence.ts, both institution-intelligence frontend suites, Part2H routes/status service/store and Part2L native worker installer/observer. Before-source copies and SHA256 are in institution-v2o_baseline.json and .scratch/institution-v2o/before. The canonical /staff/libraries/:libraryId/intelligence route and two cards already existed; no second dashboard or native protocol was created.

Existing behavior: Admin build/rebuild/retry confirmations, Librarian read-only access, membership guard, existing real current_job counters and three-second active polling, terminal stop, token/library remount key, foreign-library response check, last-good pointer/technical details and shared keyboard dialog. Backend service already projects safe errors, active_status, publication metadata and latest_job; no new privileged projection was needed.

Defects found: latest attempt timestamps/state were not displayed; counter clamping could convert invalid input into fabricated progress; stage100% was not explained separately from publication; stage counters were always labelled books although KG counts can have different units; invalid dates could crash formatting; hidden-tab polling and request deadlines were absent; focus could fetch for nonstaff; role changes did not remount in-flight action/session state.

Implemented in that existing page/helper: finite safe-integer bounded counters, accessible indeterminate progress, stage-items/percentage plus publication disclaimer, latest attempt/retained generation separation, safe timestamps and explicit worker activity unavailable. Polling gains10s request deadline, hidden-tab abort/stop, visible/focus revalidation and role/session/library remount. Existing backend authorization and Part2I status-read implementation remain byte-preserved. Backend cost per status request is unchanged; hidden polling reduces calls.

CONTRACT CONFLICT: frozen J test pins the entire old page SHA256. O requests page changes while forbidding hash rebasing/test suppression. The authorized refinement therefore makes that unchanged guard fail. This is reported as one NEW backend failure, not hidden as preexisting and not rebaselined. A reviewed resolution of that frozen-file contract is required for a clean technical PASS.
''')
    md('mongo_client_inventory','''# Source-to-runtime Mongo inventory

Whole current source inventory: client_inventory.json. It includes constructor path/function, symbols/options, environment keys, static imports and resolved collection operations; it excludes historical snapshots/venv/datasets from active code. Runtime instrumentation in scripts/institution_v2o_trace.py wraps real PyMongo clients in disposable processes and records owning PID, call stack, option names, close observation and command database/resource/source stack. It never serializes URI values, authentication exchanges, queries or documents.

mongo_runtime_coverage.json maps each source constructor to observed traces or SOURCE_ONLY_NOT_EXECUTED. Actual Core, Search (catalogue and shared tenant client), resident native worker, Recommendation and real RAG entrypoints are traced. Cold and warm institution initialization plus actual native KG methods are traced independently; separate operator/writer tests exercise their original boundaries. Historical scripts/test/exec-generated sites remain explicitly source-only where not executed. No runtime inventory is inferred solely from string search.

Core/Staff/platform/catalogue/analytics/outbox/assets use backend.database.mongodb. Recommendation reads history/catalogue and writes feedback through that module. RAG uses the same module for current identity, private assets and durable jobs; personal registries are separate filesystem/SQLite authorities. Search has a separate catalogue connection and a shared backend tenant connection; native builds use the latter. Observer uses a dedicated restricted URI, diagnostics another builtin-read principal. Frontend receives no Mongo credential.

The connection helper now serves runtime plus four supported maintenance entrypoints. Source-to-runtime coverage is improved, but actual deployed Core/Search/RAG/Recommendation owners, conditional/historical utilities and the representative5M workload remain NOT_VERIFIED. MONGO_CLIENT_INVENTORY_COMPLETE NO under the exact deployed/dynamic standard. No Motor client was found in current source. Do not execute source-only maintenance utilities merely to fill a coverage cell.
''')
    md('authenticated_configuration','''# Authenticated mode compatibility fixes

Preserved backend/database/mongo_configuration.py byte-for-byte: explicit AUTHENTICATED mode, explicit credential/database/authSource/SCRAM validation, expected authenticated identity, existing authorized DB and users readiness check, deny-only anonymous enforcement probe, safe fixed errors, bounded startup, no anonymous runtime fallback or new empty DB initialization. Actual environment/.env/service mode unchanged.

Fixed a configuration inconsistency in search/luminar_search.py: settings are captured once for construction, and that same database is used for client selection and lexical expected-source binding. Previously a fresh helper settings read could qualify a new environment DB while module-level MONGO_DATABASE selected an older one. search/maintenance.py now also selects the database from the validated settings object.

Three active lexical tools (build_lexical_sidecar --check, lexical_worker, lexical_maintenance process-once) previously constructed PyMongo directly and ignored authenticated-mode qualification. They now use connect/settings with the original development URI default. Four actual CLI missing-secret probes fail before connection/work and emit the fixed safe code; command preflight/explicit --apply boundaries remain unchanged. No lexical/global build/process was run against current deployment data.

Actual-server O tests replay frozen N assertions: missing/wrong credentials, authSource/DB/collection privileges, enforcement-disabled server, reconnect, rollback and no unrestricted fallback. CLI logs may include source-code localhost literals in Python tracebacks but never configured credential values; the probe tests the actual supplied URI is absent. Historical audit/seed/migration tools remain separately inventoried and not automatically deployment-approved.
''')
    md('permission_matrix','''# Minimum permission contracts for tested operations

least_privilege_tests.json is the executable matrix: service, exact database/resource/actions, command, source call stack, reason classification, positive replay and action-group subtraction result. Roles have only command-proven named resources; no application root/readWrite/dbOwner/userAdmin/clusterAdmin grant. Fixture administrator alone seeds, resets/provisions/restores/cleans its owned database. Cold and warm startup are both observed before forming a candidate role.

Tested contracts: Core institution index checks + durable mutation/audit + catalogue/count; Recommendation history/book/feedback-read entrypoint; RAG current private asset authorization; native actual KG publication plus Search claim/renewal/progress. Every action group in each derived role is removed in a fresh process: the tested workflow must fail with server denial/startup qualification failure, then the full role passes. Fresh revoked credentials fail. This establishes group necessity for these tested operations, not every resource's irreducible minimum or all business paths.

createIndex/listIndexes/listCollections are initialization-only where shown. find/aggregate requires find on the primary and every $lookup source; runtime tracing now records joined namespace names without pipeline/documents. Native format aggregation revealed implicit holding/asset reads missed by simple constructor/command search. update-upsert needs both update and insert, captured as a boolean action hint. Actual estimated_document_count used count/find in this Mongo version; no speculative collStats privilege is added when no collStats command is observed. Transactions/change streams are not observed and receive no invented grants; implicit sessions do not justify cluster administration.

Telemetry: exact auxiliary find/update plus native jobs/targets find, never native mutation. Operator: independent DB-local builtin read, no writes, bounded CLI code. Migration utilities require separate reviewed marker/lock/index/write privileges. Source-only utilities and full Core/Staff/circulation/assets/Recommendation mutations outside these explicit replay contracts remain pending additional qualification. MINIMUM_ROLE_QUALIFIED PARTIAL overall; tested groups qualified YES. Do not deploy the broader discovery/compatibility envelope used for full application fixtures.
''')
    md('fullstack_auth_rehearsal','''# Actual authenticated application entrypoints

fullstack.json and fullstack_commands.json: actual Core lifespan/index startup, real bcrypt Staff login/JWT, two private registrations/memberships, Admin/Librarian/Patron/outsider/approved-platform isolation, catalogue/status/history, actual Search API startup with cached MiniLM/CrossEncoder, manual tenant Search/KG publication, tenant Search and Recommendations. Global Search uses a deliberately empty owned global snapshot; no live9GB/5M global index is loaded, added to or rebuilt. It proves startup/API compatibility, not representative catalogue retrieval quality.

Recommendation is its actual ASGI entrypoint. Its Search dependency is bridged to the real Search ASGI handler rather than contacting the live fixed default port; this is explicitly a controlled transport adapter, not a network-deployed stack. Real upload/TXT chunking/embedding/FAISS/validated private prepared retrieval and extractive summary generation reuse the actual resident encoder. All Mongo operations use a separate authenticated application principal, not the provisioning root.

rag_entrypoint.json/log/commands: a separate process loads the unmodified actual RAG API and real cached Qwen4-bit, with LUMINAR_MOCK_LLM=0. Only the PrivateDocuments storage constructor and legacy uploaded-document paths are redirected inside this fixture to avoid touching existing private registries; source files are unchanged. Health, authenticated private /rag and Knowledge Tools summary HTTP200 are observed. The answer has zero returned sources; this is not claimed as validated cited-answer quality. The CPU-only RAM concern did not justify skipping the available GPU: the actual CUDA/Qwen attempt ran successfully.

Native worker/crash evidence and real Chromium use separate isolated fixtures. Full deployment equivalence remains PARTIAL: sequential processes/ASGI bridges, synthetic small catalogue, broader compatibility identity, no representative live5M/global index, no real service-account/secret enrollment or complete external network stack. Ordinary frozen domain regression supplements preservation and is not misreported as authenticated full-stack execution.
''')
    md('deployment_ownership','''# Deployment ownership and approval checklist

Read-only host_audit.json/boundary.json/extended_audit.json: Mongo8.3.4 on loopback27017, Windows service MongoDB Running/Auto with StartName NT AUTHORITY\\NetworkService. Process owner/executable command-line inspection is partly inaccessible; generic listener/process providers can return empty records despite connectivity. Current interactive identity is ROHIT-PC\\Rohit Siddani. Existing local source launcher is guarded for luminar_local and one shared child environment; actual database luminar_library does not establish development/staging/production purpose.

CURRENT_DEPLOYMENT_CLASS UNKNOWN. Actual Core/Search/RAG/Recommendation owner/supervisor and native-worker process ownership remain unconfirmed. No port number, workspace username, service name or successful localhost read is treated as installation ownership or production approval.

Installation owner must supply: deployment class/asset identifier; approved Mongo host/DB/config/service and backup authority; actual per-process account/supervisor/launch command without secret values; named DBA, application/Search/RAG/Recommendation, Windows-secret, backup and incident owners; maintenance window, minimum-role and full-stack proof; protected DPAPI profile enrollment/rotation/rollback proof; restore checkpoint approval. Run migration_preflight.py with a completed reviewed manifest. Unknown owners keep the live cutover blocked. No real service/terminal process was restarted in O; only independently verified task-owned fixture processes were cleaned up.
''')
    md('secret_acl_review','''# Secret and ACL findings / safe remediation manifest

Audited .env, code/launcher/log/tenant-artifact/private-document directories, Mongo storage directory and bounded child files in extended_audit.json. Broad Authenticated Users Modify/Builtin Users ReadAndExecute grants remain on .env/code/log/artifact paths; storage directory includes NetworkService full control and inherited Users/application-package read/execute. Bounded child-file SDDL is evidence, not recursive/effective-access certification. Actual app service accounts/required identity profiles remain unknown; no production ACL was changed.

secret_fixture.json: actual DPAPI SecureString export/import and protected current-owner/SYSTEM directory/file DACLs in owned Temp, ciphertext excludes plaintext. Owner read succeeds. An impersonated restricted token with Builtin Users restriction receives Win32 access denied5 on the secret file. This is a real token/file access test, not merely DACL text; it is not a logon/decrypt test as the eventual NetworkService or another named service account. Rotation creates equally scoped fixture writer/new protected file; old fresh authentication is revoked, replacement works, missing secret fails closed, rollback to a valid scoped replacement succeeds. No persistent OS account is created.

Exact future remediation manifest categories: .env/DPAPI secret parent+file READ only to the approved executing account and SYSTEM, WRITE only approved enrollment owner/SYSTEM; executable code/launcher READ+EXECUTE to service account, WRITE only release owner; logs/artifact/private SQLite/doc roots READ+WRITE only owning service with separately approved backup/operator READ; Mongo data/config only actual Mongo service SID/SYSTEM/approved DBA; backup destination encrypted and restricted to backup/recovery owners. Current observed paths are in audit JSON; actual account SIDs and approved ACE changes must be supplied by the installation owner before any apply operation. No blanket recursive icacls plan or unknown-account ACL mutation is supplied.

Code integrity matters: broadly writable launch code can steal a decrypted secret even when the secret file is protected. No plaintext production secret is enrolled. Temporary tool YAML contains only synthetic credentials in a protected owned directory and is removed with the fixture. Cross-identity DPAPI/service restart and effective real file permissions remain DEPLOYMENT PREREQUISITE PENDING.
''')
    md('network_review','''# Network exposure evidence

host_audit.json/boundary.json: configured loopback bind, Mongo responds locally, authorization absent, anonymous tenant read allowed; Windows Domain/Private/Public firewall profiles enabled. extended_audit.json adds bounded interface/listener/process/potential-tunnel classification, Mongo-named firewall-rule evidence and child ACLs. Provider empty/inaccessible results are NOT_VERIFIED, not evidence of stopped services or absence of forwarding. An initial expensive firewall provider call timed out; the subsequent bounded named-rule audit completed without changing policy.

NETWORK_EXPOSURE UNKNOWN. Local anonymous read does not establish public access. Effective Any/program/service/inherited firewall rules, router/NAT, tunnels and off-host reachability are not fully qualified. No remote scan, firewall rule modification or network change occurred.

Authorized network operator procedure: confirm actual mongod config/service PID/listener matches approved host/DB; enumerate effective inbound rules for that executable/service and port including Any/profile inheritance/address filters; inspect approved proxies/tunnels/NAT; from an approved outside host attempt only TCP connection and anonymous denial to the approved endpoint, recording source/destination/time and effective rule; compare approved network boundary and close unapproved exposure through a separately approved change. Do not infer internet safety from enabled firewall profiles alone.
''')
    md('backup_restore','''# Backup / restore hardening

backup_fixture.json and actual Database Tools logs: coherent stopped synthetic fixture checkpoint,45 collections, exact BSON content/counts, named index specs/options/validators and source unchanged. Index enumeration order is normalized by name; key order within each index remains part of its spec. A first comparison caught enumeration-order differences and was corrected without discarding index content. No current private user data was exported.

Owned tenant Search/KG datasets/generations, TXT source/derived chunks/vectors/FAISS and Knowledge Tools files are copied to a separate owned restore root and every file hash compared. Real Core startup and authenticated APIs then verify restored inventory, assets and membership plus Search/KG READY pointers with artifact_verified true. A duplicate insert is denied by the restored reading-list unique constraint; the owned probe is removed. Source fixture state stays unchanged. Roles are provisioned separately for the restored DB; no application root/restore power is granted.

This extends N beyond six synthetic collections and Mongo-only comparison: it validates application relationships, job/generation references and filesystem/Mongo coupling. It is still FIXTURE_PASS only. Approved real backup owner/location/access/encryption/retention, RPO/RTO, users/roles/config/SQLite checkpoint and authorized production restore remain NOT_VERIFIED. The real checkpoint must freeze writers, record all authoritative stores and generations together, verify restore on an isolated approved host and secure owner sign-off; never overwrite newer writes with an older backup to undo credentials.
''')
    md('migration_runbook','''# Executable preflight and operator cutover procedure

DESIGNED/VALIDATOR FIXTURE-TESTED; NOT OPERATOR APPROVED OR EXECUTED. scripts/institution_v2o_migration_preflight.py consumes a reviewed JSON manifest and rejects missing named owners, class, maintenance/approval reference, rehearsed Mongo8.3.4 version, minimum-role review, actual service-profile DPAPI proof, approved cross-store restore, write freeze and restore-evidence hash. It never changes authorization, credentials, services or ACLs. preflight_validation.json proves missing/invalid evidence blocked and a clearly synthetic completed fixture manifest passes validation; that is not a production approval.

Operator stages, all requiring separate real cutover authorization: (1) classify target and fill exact host/DB/service/config/account/SID/owner manifest; verify installed version/tool compatibility and all deployed clients. (2) reconcile minimum roles from representative full-stack traces, including conditional/upsert/lookup and initialization/migration permissions, not the compatibility envelope. (3) obtain protected cross-store backup and independently tested isolated restore/checkpoint, record hashes and restore authority. (4) schedule downtime/write freeze, stop intake/drain app and workers using existing lifecycle, preserve in-flight jobs/last-good pointers and stop all approved clients. Unknown writers abort.

(5) DBA locally provisions reviewed administrator/recovery and scoped application/reader/optional-writer roles using prompted generated secrets, in the separately approved isolated provisioning interval; enroll protected per-identity DPAPI secrets/launcher environments. Auth-mode clients stay stopped while authorization is off. (6) DBA validates protected config/backup/credential evidence, enables authorization in the approved mongod configuration and restarts only that approved MongoDB service. Verify authenticated administrator, selected existing DB, actual enforcement and anonymous denial before app startup. (7) start Core then Search/native, Recommendation then RAG, frontend last; qualify each authenticated client before initialization. Check Staff/JWT/platform/private membership, domain workflows, no empty DB, global read-only discovery, native queue/pointers/artifacts and controlled manually requested fixture/canary builds only. (8) independent operator diagnostics, no production denial-write experiments. Keep telemetry off. (9) reopen writes only after named owners approve validation; observe actual error/latency/secret output and rotate/revoke commissioning credentials after drained pools.

Abort thresholds are categorical: unknown owner/writer, untested restore, mismatched hash/version/DB, missing secret/role/profile, anonymous access, legitimate operation denied, new empty DB, service unavailable, tenant leak, corrupt/mismatched pointer/artifact or uncertain publication. Keep writes closed and follow rollback.md. Full downtime is assumed pending representative rehearsal; no zero-downtime claim. Exact live service-control/config edits are deliberately not executed or guessed for unconfirmed owners; execution must use the signed manifest's actual protected paths and approved service identities. No automatic security-disable or data-restore action exists.
''')
    md('rollback','''# Rollback procedure

Fixture-proven: wrong/absent/revoked credential fails closed; equally scoped replacement restores fresh authenticated operation; secret rotation/revocation does not change native ownership. Real native crash restart leaves jobs/pointers/last-good files unchanged; explicit existing Admin recovery resolves prepublication FAILED or postpublication SUCCEEDED. No restart triggers a rebuild/recovery. Backup restoration is a separate verified isolated checkpoint exercise, not automatic client rollback.

For wrong password/authSource/DB/missing role or Core/Staff startup failure: keep traffic stopped, restore last validated scoped secret/config under actual service identity, review only proven missing action/resource, restart only affected approved service and rerun qualification/API checks. Never substitute root/anonymous credentials. Search/native failure preserves fences/leases/jobs/pointers/artifacts and requires read-only diagnosis before any existing manual recovery; do not unlock/cancel or start another build on an uncertain outcome.

For RAG/Recommendation failure: stop intake, preserve asset/history/feedback and artifact roots, restore validated scoped connection/dependency configuration, verify current identity/membership and private retrieval before reopening. Telemetry failure leaves the flag off or uses an independently approved future disable/restart; writer failure has no native authority. For Mongo unavailable after approved restart: all clients remain stopped; DBA investigates actual service/config/storage/credential evidence. Returning to no-auth is an explicit separately authorized security regression with host isolation, never automatic rollback. Never restore an older database over newer accepted writes merely to revert a credential or application release.
''')
    md('rag_hash_regression','''# Protected RAG hash regression investigation

RAG_HASH_DRIFT REQUIRES_APPROVAL. rag_hash_evidence.json records every expected/actual hash; the unchanged frozen assertion fails on rag/qa.py: expected0E78A7C780F691B14C8E3A3337F62054E4C117F0C2DF7828099D80DA90A793C6, actual4A1141649A4CE9B4BCE6413627C27557F5817BB8718A4E842A4D12021BD89DE3. rag/api.py also differs but is explicitly excluded by that test; llm/retriever/reranker/document_service match their frozen hashes.

Git history and diff in rag_hash_history.json/rag_source_diff.txt show committed document-grounding additions (valid document IDs, definition evidence/category and unsupported citation suppression). Available Git blobs/line-ending hashes do not recreate the exact expected snapshot, so the precise first hash divergence is NOT_ESTABLISHED. This is source/byte drift, not a generated model/file output; normalizing line endings alone is not a justified repair. Existing document behavior is covered by frozen private-document/knowledge suites and actual unmodified RAG/Qwen startup/fixture requests.

No protected source, frozen expected hash or test was changed. Reverting could destroy legitimate existing grounding behavior; rebasing/suppressing the test is prohibited. Explicit protected-file/baseline contract review is required before a repair is chosen. This remains one preexisting failure; full backend PASS is not claimed.
''')
    md('lexical_fallback_regression','''# Lexical fallback HTTP500 investigation and repair

LEXICAL_FALLBACK FIXED. Initial frozen test reproduces500; thread-aware exception tracing identifies AttributeError: Books object has no database at search/api.py's GlobalQuerySearch path. This was optional facet discovery, before semantic retrieval, not a failure of semantic candidate ranking or exception conversion. Earlier trace on the main thread alone missed ASGI worker exceptions; the corrected trace and raw initial/fixed XML/logs are retained.

Narrow source fix: search/query_execution.py global_facets treats database-less find-only catalogue providers as having no optional facet rows. Normal Mongo facet lookup and its authorization/driver errors are preserved; there is no alternate client, credential fallback, broad error swallow or switch of query/ranking mode. Frozen response assertions remain unchanged and pass for missing/corrupt/stale lexical fixtures with current Mongo metadata hydration/public schema. Two new tests cover find-only provider compatibility and explicit authorization-error propagation. Full Search group passes161 tests and actual authenticated Search API returns200 in the controlled owned snapshot.
''')
    md('improvement_review','''# Improvement review

Implemented real UX corrections on the existing page rather than recreating2H; tests cover malformed counters, stage completion vs publication, latest attempt, worker unknown, date safety, unauthorized focus, role/logout/visibility/network/503 lifecycle. Actual Chromium uses real JWT/ASGI/Mongo and actual cached encoder/native builds at six sizes with keyboard/axe checks.

N shortcomings improved through runtime constructor/command stacks, cold+warm initialization and lookup-source evidence, exact command-derived roles with group subtraction/revocation, actual Core/Search/Recommendation and separate real Qwen/RAG serving, private document/Knowledge Tools, protected-token ACL denial/DPAPI rotation, child ACL/network inventory and45-collection cross-store restore checked through real APIs. Narrow config fixes unify selected DB and close active lexical CLI authentication-gate gaps. The lexical500 is fixed without changing ranking/schema/tests.

Remaining technical conflict: J's frozen whole-page SHA forbids the requested frontend changes; no test/hash is weakened, so one NEW guard failure is reported. Protected RAG hash drift remains one preexisting review requirement. Representative5M/network/service-profile/deployment role coverage and real owner/restore/cutover approvals remain incomplete. Partial is an evidence result, not a reason to perform unapproved security or source changes.
''')
    md('next_scope','''# Next recommended scope

Stop after Part2O. First obtain explicit review of the frozen J whole-page contract versus the authorized frontend refinement and the protected RAG hash conflict, with behavioral coverage preserved and no silent hash rebasing. Then assign/classify the actual installation, close dynamic conditional/minimum role and representative full-stack5M/network/service-profile coverage, and approve a protected coherent real backup/restore in an isolated environment. Only after those gates pass should a separately authorized maintenance window plan a live authentication cutover. Telemetry activation remains a distinct later approval; no automatic maintenance/distributed worker/cancellation/global rebuild is introduced.
''')


def finalize():
    documents();b=read('baseline');checks=read('final_backend');front=read('final_frontend');browser=read('browser');native=read('native_results');stack=read('fullstack');roles=read('least_privilege_tests')
    assert checks[-1]['group']=='events' and any(r['group']=='institution_v2o' for r in checks)
    assert browser['status']=='PASS' and stack.get('owned_fixture_removed') and native.get('owned_fixture_removed') and roles.get('owned_fixture_removed')
    assert all(r['exit']==0 for r in front)
    failures=[]
    for p in [*(R.glob('institution_v2o_final_*.xml')),R/'institution_v2o_focused.xml']:
        for t in ET.parse(p).iter('testcase'):
            if any(c.tag in {'failure','error'} for c in t):failures.append(t.attrib['classname']+'::'+t.attrib['name'])
    assert sorted(failures)==sorted([OLD,NEW]),failures
    from scripts.institution_v2i_baseline import capture_state
    from scripts.institution_v2l_baseline import capture_indexes
    state=capture_state();state['global_KG_metadata']={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in (ROOT/'knowledge_graph/data').glob('*') if p.is_file()}
    state=json.loads(json.dumps(state,default=str));indexes=json.loads(json.dumps(capture_indexes(),default=str))
    changed=[n for n,h in b['source_sha256'].items() if not (ROOT/n).exists() or sha(ROOT/n)!=h]
    unexpected=[n for n in changed if n not in PRODUCT and 'institution_v2o' not in n]
    frozen=[n for n,h in b['frozen_reports_sha256'].items() if not (ROOT/n).exists() or sha(ROOT/n)!=h]
    state_bad=[k for k,v in b['state'].items() if state.get(k)!=v]
    preservation={'result':'PASS' if not unexpected and not frozen and not state_bad and indexes==b['mongo_indexes'] else 'FAIL',
        'authorized_product_changes':[n for n in changed if n in PRODUCT],'unexpected_source_changes':unexpected,'prior_I_to_N_reports':len(b['frozen_reports_sha256']),'frozen_report_changes':frozen,
        'state_changes':state_bad,'mongo_indexes_unchanged':indexes==b['mongo_indexes'],'state_after':state,'I_status_and_native_protocol_changed':False,
        'head_unchanged':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==b['head'],
        'limits':'Global catalogue estimated count; large global artifact size/mtime, bounded tenant hashes; personal registry logical hashes. No full5M digest. One failed owned J fixture startup was independently identified and cleaned, not the actual Mongo service.'}
    write('preservation',preservation);assert preservation['result']=='PASS',preservation
    output=(R/'institution_v2o_final_frontend.log').read_text(encoding='utf8')
    ft={k:sum(map(int,re.findall(r'^.*?\b'+k+r' (\d+)\s*$',output,re.M))) for k in ['tests','pass','fail','skipped']}
    assert ft['pass']==959 and ft['fail']==0
    write('backend_tests',{'totals':totals(checks),'groups':checks,'preexisting_remaining':[OLD],'preexisting_fixed':['tests.test_lexical_api_fallback::test_search_route_works_with_failed_lexical_and_keeps_public_schema'],'new_failures':[NEW],
                          'initial_fixture_start_failure':'J server startup deadline failed under concurrent workload; initial54 setup errors retained. Fresh unmodified rerun53 passed/1 deliberate page-hash guard failure. No suppression or hash rebasing.'})
    warning=lambda t:{line for line in t.splitlines() if ': warning ' in line}
    newwarnings=sorted(warning((R/'institution_v2o_final_lint.log').read_text())-warning((R/'institution_v2n_final_lint.log').read_text()))
    write('frontend_tests',{'totals':ft,'checks':front,'new_focused_tests':16,'focused_all_pass':True,'new_lint_warnings':newwarnings})
    write('regression',{'result':'FAIL','backend':totals(checks),'new_failures':[NEW],'preexisting_remaining':[OLD],'lexical_fallback':'FIXED','rag_hash':'REQUIRES_APPROVAL','frontend':ft,'production_build':'PASS','lint_exit':0,'new_lint_warnings':newwarnings})
    success=read('native_success')
    for target,key in [('SEARCH_INDEX','search_status'),('KNOWLEDGE_GRAPH','kg_status')]:
        write(key,{'result':'PASS_TESTED_SCOPE','source':'Existing safe tenant status, no new backend projection','actual_builds':[x for x in success['builds'] if x['target']==target],
            'backend_states':['NOT_BUILT','READY','STALE','BUILDING','FAILED','RECOVERY_REQUIRED'],'durable_job_states':['QUEUED','RUNNING','VALIDATING','PUBLISHING','SUCCEEDED','FAILED','RECOVERY_REQUIRED'],
            'browser_evidence':browser['steps'],'latest_attempt':'Separate from retained pointer and last-success metadata; no serving assertion from pointer alone.'})
    write('progress',{'result':'PASS','source':'stageProgress finite safe integers,0<=current<=total,total>0; otherwise indeterminate','stage100_is_not_publication':True,
        'actual_durable_samples':success['events'],'publication_ack':success['builds'],'new_UI_tests':'16 focused tests, all pass; frozen controls40 pass','worker_health_fabricated':False})
    write('polling',{'result':'PASS_TESTED_SCOPE','active_poll_ms':3000,'request_deadline_ms':10000,'terminal_polling_stop':True,'hidden_tab_abort_stop':True,'resume_revalidate':True,
        'session_role_library_keys':True,'foreign_response_guard':True,'503_retry_limit':3,'network_failure':'Clear data/actions; explicit manual retry','backend_status_read_implementation_unchanged':True,
        'browser_evidence':browser['steps'],'unit_evidence':'institution-v2o-intelligence.test.tsx and unchanged controls tests; hidden-tab/deadline are browser lifecycle code plus unit-tested cancellation, not a claimed native health signal.'})
    write('worker_auth_validation',{'result':'PASS','native':native,'entrypoint_builds':stack['manual_builds'],'protocol':b['native_contract'],'no_global_rebuild':True,'no_automatic_build_or_recovery':True})
    write('mongo_security',{'focused_server_tests':26,'focused_total_including_facet_and_preflight':30,'all_pass':True,'host':read('host_audit')['mongo'],'command_derived_roles':len(roles['services']),'revocation':'Fresh login denied in each scoped service role and secret rotation fixture',
        'actual_deployment_auth_changed':False,'anonymous_fallback':False,'production_telemetry_enabled':False})
    write('security',{'private_isolation':stack['isolation'],'native_JWT_checks':success['security'],'browser_authorization':browser['steps'],
        'operator':read('operator_fixture'),'restricted_writer_actual_denials':'Frozen N assertions replayed on O server; forbidden native/global writes denied13',
        'secret_access':read('secret_fixture'),'production_security_ready':False})
    # Executable preflight positive/negative fixture; no invented real approval.
    from scripts.institution_v2o_migration_preflight import validate
    proof=R/'institution_v2o_backup_fixture.json'
    plan={k:'SYNTHETIC_FIXTURE_OWNER' for k in ['installation_owner','dba_owner','application_owner','windows_secret_owner','backup_owner','incident_owner','maintenance_window','approval_reference']}
    plan.update(deployment_class='DEVELOPMENT',mongo_version='8.3.4',minimum_roles_reviewed=True,service_identity_DPAPI_verified=True,cross_store_restore_approved=True,write_freeze_confirmed=True,restore_evidence_path=str(proof),restore_evidence_sha256=sha(proof))
    assert validate(plan)['ready_for_operator_review'] and not validate({})['ready_for_operator_review']
    write('preflight_validation',{'synthetic_complete_manifest':validate(plan),'missing_manifest':validate({}),'real_installation_approval':False,'cutover_executed':False})
    qa={'PART_2O_RESULT':'PARTIAL','STAFF_INTELLIGENCE_FRONTEND':'PASS','SEARCH_PROGRESS':'PASS','KG_PROGRESS':'PASS','WORKER_HEALTH_FABRICATED':'NO',
        'MONGO_CLIENT_INVENTORY_COMPLETE':'NO','AUTHENTICATED_MODE_FAIL_CLOSED':'YES','AUTHENTICATED_FULLSTACK':'PARTIAL','MINIMUM_ROLE_QUALIFIED':'PARTIAL','NATIVE_WORKER_AUTH':'PASS',
        'OPERATOR_READ_ONLY':'YES','TELEMETRY_WRITER_RESTRICTED':'YES','SECRET_ACL_FIXTURE':'PASS','NETWORK_EXPOSURE':'UNKNOWN','BACKUP_RESTORE':'FIXTURE_PASS','MIGRATION_RUNBOOK':'PARTIAL',
        'RAG_HASH_DRIFT':'REQUIRES_APPROVAL','LEXICAL_FALLBACK':'FIXED','PRODUCTION_SECURITY_READY':'NO','PRODUCTION_AUTH_CUTOVER':'NO','PRODUCTION_CREDENTIAL_CREATED':'NO','PRODUCTION_TELEMETRY_ENABLED':'NO',
        'GLOBAL_HNSW_REBUILT':'NO','GLOBAL_KG_REBUILT':'NO','NEW_BACKEND_FAILURES':1,'PREEXISTING_BACKEND_FAILURES':1,
        'BACKEND_TESTS':f"{totals(checks)['passed']} passed / {totals(checks)['failed']} failed / {totals(checks)['skipped']} skipped",'FRONTEND_TESTS':'959 passed / 0 failed / 0 skipped',
        'REAL_BROWSER_QA':'PASS','PRODUCTION_BUILD':'PASS','NEXT_RECOMMENDED_SCOPE':'Resolve frozen J page-hash and protected RAG contract reviews, then owner-led deployment/minimum-role/representative-stack qualification before any separately approved cutover.'}
    write('qa_summary',qa)
    statuses={'PART_2O_TECHNICAL_RESULT':'PARTIAL','PART_2N_SHORTCOMINGS_CLOSED':'PARTIAL','PRODUCTION_SECURITY_READINESS':'NOT_READY','FULL_BACKEND_REGRESSION_RESULT':'FAIL',
        'detail':'Requested UI and immutable J whole-page hash are incompatible without an explicit reviewed contract change. One new guard failure remains visible; one old RAG hash failure remains. No tests/hashes altered.'}
    write('result_classification',statuses)
    titles=['FINAL PASS / PARTIAL / FAIL','EXECUTIVE SUMMARY','EXISTING UX AUDIT','SEARCH PROGRESS','KG PROGRESS','SAFE WORKER ACTIVITY PRESENTATION','POLLING AND LIBRARY SWITCHING','RESPONSIVE AND ACCESSIBILITY',
        'PART 2N SHORTCOMINGS BEFORE/AFTER','MONGODB CLIENT INVENTORY','AUTHENTICATED-MODE FIXES','MINIMUM PERMISSION CONTRACT','FULL-STACK AUTHENTICATED REHEARSAL','NATIVE WORKER AUTHENTICATION','OPERATOR / TELEMETRY SECURITY',
        'DEPLOYMENT OWNERSHIP','SECRET AND ACL FINDINGS','NETWORK EXPOSURE REVIEW','BACKUP/RESTORE','MIGRATION/ROLLBACK','PROTECTED RAG REGRESSION','LEXICAL FALLBACK REGRESSION','PRIVATE LIBRARY ISOLATION','REAL BROWSER QA',
        'BACKEND TESTS','FRONTEND TESTS','GLOBAL PRESERVATION','EXACT FILES CHANGED','REPORTS CREATED','REMAINING BLOCKERS','IMPROVEMENT REVIEW','RECOMMENDED NEXT PHASE']
    bodies=[
        'PARTIAL. UX/functionality and isolated security improvements pass tested scope; two contract failures remain (one new J guard, one old RAG hash). Full backend FAIL; production security NOT_READY.',
        'Existing page refined; config/CLI gaps repaired; runtime/lookup/cold-warm role tracing and subtraction, actual models/APIs/browser, protected secrets and cross-store restore exercised. No live cutover/deploy.',
        'Existing2H page/cards/dialog/roles/polling audited before edits; missing attempt history, progress validation and lifecycle handling fixed. See existing_ux_audit.md.',
        'Real stage counters, eligible/indexed counts, publication/last-success and latest attempt distinct; invalid counters indeterminate and stage100 is not completion. search_status.json/progress.json.',
        'Same existing KG card exposes eligible/represented/node/edge/generation/stage/history safely; no graph extraction/schema change. kg_status.json.',
        'Worker activity Not available; durable job timestamps/states only. No raw worker IDs/fences/URIs/operator record or browser diagnostic proxy.',
        '3s active polling,10s request deadline, hidden-tab abort/resume, terminal stop, role/session/library remount and foreign-response rejection. Unit and real delayed library-switch evidence; backend Part2I source unchanged.',
        'Real Chromium six requested sizes, keyboard dialog/focus/escape, no horizontal overflow, focused axe zero violations. Source styling retained; browser.json and screenshots.',
        'N lower-bound-only roles improved to exact tested-command roles/removal evidence; six-collection restore extended45 with artifact hashes/APIs. Actual Core/Search/Recommendation and real Qwen/RAG requests run. Owner/full5M/profile/exact all-path role gaps remain.',
        'Whole source scan plus actual constructor PID/stack/teardown and command coverage; actual deployed/historical/dynamic owners still unverified. Complete NO, remaining cells explicit.',
        'Selected DB now comes from the same validated Search/maintenance settings. Three active lexical Mongo CLIs now honor fail-closed mode; four real missing-secret CLI probes pass. No current deployment settings changed.',
        'Four tested service operation sets pass command-derived named-resource roles and every action-group removal fails. Native lookup sources/cold-warm initialization/upsert rights captured. Overall PARTIAL beyond tested paths; no broad admin runtime grants.',
        'Actual authenticated entrypoints/models, private document and Knowledge Tools; empty owned global snapshot and ASGI dependency bridge explicitly limited. Separate real RAG/Qwen health/private/summary requests200; zero cited sources does not establish answer quality. Full representative deployment PARTIAL.',
        'PASS actual cached MiniLM/FAISS/KG, claim/renewal/progress/publication/ack, genuine crash/restart/last-good hash/manual recovery.90s/10s/2s/serial/fences unchanged.',
        'Independent read-only CLI calls, denied writes and restricted writer/native/global denials on actual auth servers. Production telemetry off; no new tenant infrastructure projection.',
        'MongoDB service NetworkService observed. App supervisor/account/native ownership and installation class remain UNKNOWN; concise real owner checklist in deployment_ownership.md.',
        'Broad local .env/code/log/artifact/storage grants audited including bounded child ACLs. Same-owner DPAPI and real restricted-token denial5/rotation/revocation/missing-secret/rollback pass. Actual named service profile/cross-account hardening pending.',
        'Loopback/config/profile/interface/named-rule observations only; effective remote forwarding/reachability UNKNOWN. No firewall change or public-exposure inference from anonymous localhost reads.',
        'FIXTURE_PASS45 collections/BSON/counts/indexes/validators/options, copied cross-store artifact hashes, restored real Core/private/inventory/asset APIs, READY verified Search/KG pointers and unique constraint. Real production restore NOT_VERIFIED.',
        'Executable review-manifest validator plus staged downtime/provision/secret/auth/startup/abort/rollback runbook; synthetic valid/missing evidence checks pass. No actual owner approval or cutover. Never automatically disable security or restore older writes.',
        'REQUIRES_APPROVAL. qa.py exact expected/actual hashes and committed grounding diff recorded; exact initial hash drift timing not established. Protected source/test/hash untouched.',
        'FIXED. Optional facets failed for find-only provider before semantic path; targeted compatibility fix preserves Mongo authorization errors and normal ranking/schema. Frozen lexical test and full Search suite pass.',
        'Actual JWT/Staff/private2UUID/approved-platform outsider checks preserved; library Admin vs Patron actions distinct. Mongo infrastructure identity does not mint membership/JWT.',
        'PASS tested Chromium paths: actual API queue/build/failure/recovery/retained generation, delayed scope switch, membership revocation, six layouts, keyboard/axe and logout/relogin. Controlled counter stages identified separately from native build observations.',
        qa['BACKEND_TESTS']+'. One preexisting RAG failure, one NEW J whole-page hash guard. Initial J fixture setup failure retained and rerun; no frozen changes/suppression.',
        '959 passed,0 failed,0 skipped including16 new cases; production build/lint pass; no new lint warnings. UX changes still conflict with unchanged J byte guard.',
        'Preservation PASS: current TEST151/150/5, estimated global5M,32 Mongo index contracts, pointers/artifacts/private logical state and1104 prior reports unchanged. Global metadata vs bounded hashes limitation explicit.',
        'Nine existing product/config/test-runner files listed in changed_files.json, plus new O tests/harnesses/reports. Original user work, protected RAG, native worker/store/I optimization/J auth/L observer/N gate preserved. No commit.',
        'All32 requested reports plus raw runtime/role/native/browser/backup/ACL/regression/QA/acceptance evidence and verified task-only package.',
        'Frozen frontend SHA conflict, protected RAG hash review, UNKNOWN deployed owners/class, full representative all-path minimum roles/5M/network/service-profile readiness, approved real restore and cutover.',
        'Meaningful source and executed-fixture improvements, with exact limitations and new guard failure visible. No fake worker health, blanket grant/ACL policy, automatic maintenance or production approval claim.',
        qa['NEXT_RECOMMENDED_SCOPE']+' Stop after O; no later phase begun.'
    ]
    letters=[chr(65+i) for i in range(26)]+['AA','AB','AC','AD','AE','AF']
    md('completion','\n\n'.join(f'## {letter}. {title}\n\n{body}' for letter,title,body in zip(letters,titles,bodies))+'\n\n## Independent result classifications\n\n```text\n'+'\n'.join(f'{k}: {v}' for k,v in statuses.items())+'\n```\n\n## FINAL QA SUMMARY\n\n```text\n'+'\n'.join(f'{k}: {v}' for k,v in qa.items())+'\n```')
    request=Path('C:/Users/balak/.codex/attachments/b91beec6-bcb7-4b5a-a116-4a92f85cea91/Pasted text.txt').read_text()
    block=request.split('PART AB\nACCEPTANCE CRITERIA')[1].split('Overall result')[0]
    criteria=re.findall(r'(\d+)\.\s+(.*?)(?=\n\s*\d+\.|\Z)',block,re.S);assert len(criteria)==38
    write('acceptance',{'overall':'PARTIAL','criteria':[{'number':int(n),'requirement':' '.join(v.split()),'status':'FAIL_FROZEN_PAGE_CONTRACT' if int(n)==34 else 'PARTIAL_TESTED_SCOPE_OR_OWNER_REVIEW' if int(n) in {13,14,23} else 'PASS','evidence':'Completion A–AF and linked raw reports; no production deployment implication.'} for n,v in criteria]})
    paths=sorted({p for p in [*R.glob('institution_v2o_*'),*(ROOT/'scripts').glob('*institution_v2o*'),*(ROOT/'tests/institution_v2o').rglob('*.py'),
        ROOT/'frontend/tests/institution-v2o-intelligence.test.tsx',*(ROOT/n for n in PRODUCT),*(ROOT/'.scratch/institution-v2o').rglob('*.py'),*(ROOT/'.scratch/institution-v2o').rglob('*.tsx')]
        if p.is_file() and p.suffix!='.zip' and '__pycache__' not in p.parts and p.name not in {'institution_v2o_changed_files.json','institution_v2o_package_manifest.json'}})
    write('changed_files',{'existing_product_paths':PRODUCT,'baseline_changed_paths':changed,'unexpected_previous_source_changes':unexpected,
        'files':[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in paths],
        'source_test_hash_expectations_modified':False,'commit_deploy_or_live_security_changes':False,'delivery_files':['institution_v2o_changed_files.json','institution_v2o_package.zip','institution_v2o_package_manifest.json']})
    paths.append(R/'institution_v2o_changed_files.json');package=R/'institution_v2o_package.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        for p in paths:z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(package) as z:assert z.testzip() is None;count=len(z.namelist())
    write('package_manifest',{'package':package.name,'bytes':package.stat().st_size,'sha256':sha(package),'entries':count,'scope':'Only O source/tests/runbooks/evidence/owned before snapshots. No credential/tool YAML/DPAPI ciphertext/Mongo dump/model/private source artifact payload.'})
    print(json.dumps({'result':'PARTIAL','backend':totals(checks),'frontend':ft,'new_failure':NEW,'preservation':preservation['result'],'package_entries':count}))


if __name__=='__main__':documents() if '--docs' in sys.argv else finalize()
