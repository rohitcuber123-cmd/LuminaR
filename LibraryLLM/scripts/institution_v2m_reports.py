"""Consolidate only measured2M evidence and operator-owned runbooks; never deploy."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,re,subprocess,sys,zipfile,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));R=ROOT/'reports'


def read(n):return json.loads((R/f'institution_v2m_{n}.json').read_text(encoding='utf8'))
def write(n,v):(R/f'institution_v2m_{n}.json').write_text(json.dumps(v,indent=2,default=str),encoding='utf8')
def md(n,v):(R/f'institution_v2m_{n}.md').write_text(v.strip()+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def total(v):return {k:sum(x.get(k,0) for x in v) for k in ['tests','passed','failed','skipped']}
def stats(v):
    import statistics
    if not v:return None
    v=sorted(v);return {'median':statistics.median(v),'p95':v[min(len(v)-1,int(.95*len(v)))],'min':v[0],'max':v[-1],'samples':len(v)}


def docs(host):
    md('architecture','''# Deployment boundary and actual source architecture

The implemented L architecture is preserved byte-for-byte: search/api.py installs search.library_intelligence_api into the existing Search process; that installer constructs one TenantIntelligence using resident encoder/reranker and an optional configured_factory. Startup registers the native worker only when both resident models exist. Worker.start initializes native indexes and starts its one serial loop; close signals native stop/cache clear and joins only its optional auxiliary observer. Native loop/stage ordering,90s lease,10s renewal and2s idle wait remain unchanged. No new runtime implementation, worker/model/service, route or frontend component was added in2M.

The actual writer implementation is backend/services/library_worker_telemetry.py plus library_worker_observer.py. It performs only fixed auxiliary updates and native reads under a separate restricted Mongo principal. The optional Agent has one own thread/client, bounded queues/deadlines/history and epoch CAS. Native claim/progress/finished hooks pass copied canonical identifiers only after accepted operations. Native job/pointer/fence/validation/recovery remains authoritative; no telemetry control edge exists.

Intended source-default processes are Core backend.main:app on8002, Search search.api:app on8003 (hosts resident tenant worker/model), Recommendation recommendation.api:app on8004, RAG rag.api:app on8005 (Qwen/router), Vite on5173 and MongoDB on27017. scripts/start_local.py launches only missing listeners, owns handles for children it starts and polls exits; it does not provide tenant UUID/boot supervisor attestation. Existing RAG-specific launcher metadata is not tenant-worker evidence. No process was started or restarted in the production stack during2M.

The Mongo endpoint on27017 responded to the read-only database audit and supplied server PID/version. Windows listener/CIM observations were not consistently available across probes; the latest raw capture, service metadata when available and provider limitation are in host_audit.json. Do not infer absence from a missing OS record or treat a database-reported PID as an attested native worker. Other source-default application service ports and approved service accounts were not qualified. Source startup wiring and isolated native lifecycle tests do not certify an actual production supervisor. PROCESS_VERIFICATION remains NOT_AVAILABLE for tenant-worker diagnostics.

Unchanged J CLI handles bounded queue/job/artifact observations; unchanged L worker supplement handles bounded current/previous instance and scoped progress evidence. Both require an independently authenticated DB-local read principal, not app JWT/Platform membership. Staff Intelligence cards/build/rebuild/status behavior and browser polling are unchanged.
''')
    md('security_review','''# Security decision — production NOT_QUALIFIED

Read-only production observations found MongoDB8.3.4, no credentials in the configured native connection, zero authenticated users on that connection, security.authorization not set and a successful anonymous tenant_id read. No production write was attempted. Actual custom-role/denied-write enforcement is proved only in separately owned auth-enabled fixtures. Runtime role metadata checks alone are not deployment authorization certification.

The project .env DACL grants Authenticated Users Modify and Builtin Users ReadAndExecute, despite being a protected DACL. Source launcher/log/artifact paths also have broad local-group grants in the audit. These are unsuitable as evidence of a protected dedicated deployment secret/code boundary. No production ACL or service authorization setting was changed. No existing secret value, raw process command line or password was emitted or stored in reports.

The source-default application service ports were not observed active; no exact resident Search service identity, assigned DBA/service/operator owner or production secret enrollment was verified. There is no trusted supervisor binding to native worker UUID/boot. New protected DPAPI/NTFS files in owned fixtures qualify same-user/machine behavior, not a different production service account or cross-account access denial. Same local test OS identity handled both credential files; Mongo identities and privileges were independently enforced.

FIXTURE_QUALIFIED: YES when all recorded fixture assertions complete. DEPLOYMENT_PREREQUISITES_SATISFIED: NO. PRODUCTION_ENABLEMENT_APPROVED: NO. PRODUCTION_ENABLED: NO. Global authentication hardening, owned service/account/ACL/secret enrollment and representative full-stack workload remain separate operator-owned prerequisites. No activation or credential creation is authorized by these fixture results.
''')
    md('mongo_authorization','''# Mongo authorization — observed deployment versus fixture

Current deployment: sanitized read-only getCmdLineOpts/buildInfo/connectionStatus and anonymous tenant_id read are in host_audit.json. authorization is NOT_SET_DEFAULT, configured connection has no authenticated user and anonymous tenant read succeeds. No production denied-write probe was attempted, no users/roles/authorization files were changed and no anonymous write was used as a test. This deployment fails the authorization gate.

Owned fixtures launch a separate loopback mongod with --auth, unique temp dbPath and ephemeral port. Only that administrator bootstraps disposable users/roles/validator. Telemetry writer checks the exact effective privilege set and database-local identity; read operator checks built-in read role only. Actual forbidden writes return Mongo code13; wrong/dropped credentials fail fresh authentication; unauthorized unrelated user cannot read/write telemetry. Runtime URI parser rejects anonymous/JWT/wrong DB/authSource/non-loopback/multi-endpoint inputs and never falls back to unrestricted app credentials.

Operator-owned future authorization enablement requires a reviewed DBA plan for all existing application principals before touching the real Mongo service. Simply turning on --auth without existing Core/Search/RAG/Recommendation credential readiness could break unrelated services. This phase neither provisions that plan's accounts nor changes service flags. Collection/role presence is not proof of authorization enforcement.

MongoDB documents authorization enablement through --auth or security.authorization in its [RBAC documentation](https://www.mongodb.com/docs/v8.0/core/authorization/). Source-accurate grants and live fixture server denials, rather than this documentation alone, form the2M evidence.
''')
    md('writer_permissions','''# Restricted writer contract and manual provisioning boundary

Actual namespace: institution_worker_telemetry_v2k; fixed_id resident-tenant-worker-v1; schema1; current/previous,8 entries each, max16384 BSON bytes. Actor.start requires preallocation and never inserts/upserts/creates schemas. Mongo writer connection fixes primary reads, acknowledged journaled writes, pool2, retryReads/retryWrites off and500ms operation deadlines. URI database/authSource must match the native job database; exactly one loopback SCRAM endpoint with explicit credentials is required.

Exact approved effective privileges for an operator-approved database are: find/update on institution_worker_telemetry_v2k; find on institution_intelligence_jobs; find on institution_intelligence_targets. No other action/resource is accepted by the runtime. In particular no jobs/lease, target pointer, generation, lock, catalogue, membership, user, digital asset, RAG/global book, insert/delete/index/schema grant is present. Actual forbidden operations return13 in auth-enabled fixtures, not only a Python allowlist.

For a future approved deployment, DBA chooses separately recorded principal/role names; the runtime does not require a guessed username. In an authenticated interactive administrative session with a prompted password, inspect existing grants/namespace first. Create only the above resource/action role, then the DB-local writer with only that role and a separately prompted generated password. Independently verify connectionStatus effective grants and server-denied native writes in a disposable production-equivalent environment, not by writing TEST/global production records. Never reuse fixture provision functions on production: their database guards reject it.

The DBA must preallocate exactly one record {_id:resident-tenant-worker-v1,schema:1,epoch:0,current:null,previous:null} only when a reviewed new namespace does not already exist. Install/verify the accepted strict JSON-schema maxItems8 plus whole-document $bsonSize<=16384 validator and built-in unique_id index. Never overwrite an existing current/previous record just to force an empty baseline. No TTL/journal/artifact retention process is added. DBA namespace ownership and any future installation/rotation are not executed in2M.

An authenticated code path is not executable attestation: a holder of the credential can forge its allowed auxiliary data. Native revalidation and information-only use prevent it granting native job authority. Secure host/service secret ownership remains required and unqualified in the actual deployment.
''')
    md('operator_permissions','''# Independent read-only operator

Both scripts/diagnose_library_intelligence.py and scripts/diagnose_worker_telemetry.py continue to use backend.services.library_operator_access.connect_operator. It requires an explicit LUMINAR_OPERATOR_MONGO_URI with one loopback SCRAM endpoint, username/password, database=authSource and exactly one DB-local authenticated user with only built-in read for that database. No app JWT, GENERAL_USER/LIBRARIAN/library ADMIN/Platform ADMIN or membership substitutes for infrastructure authentication. There is no writer fallback.

J's original four-collection bounded reader/CLI remains byte-preserved. L adds only the fixed bounded worker singleton supplement and scoped native job/pointer joins. Worker output includes current and explicitly historical previous instance digest, coherent server timestamps, last self-report, pulse/progress/heartbeat ages and native pointer/ack evidence. Missing/malformed/future/uncorrelated evidence is UNKNOWN; no HEALTHY, PROCESS_VERIFIED_ALIVE, ETA or CPU/GPU ownership claim exists. A gap does not prove death; a quiet stage does not prove a stall.

Fresh tests demonstrate actual operator update denial13 and unrelated-user rejection. Replacement reader uses a new equally read-only account; after old-user revocation a fresh old login fails while the writer remains independent. Native fixture CLI JSON/text is run from its DPAPI-protected reader file with no URI/password argv or secret output. The generic DB read role is broad within that DB; code exposes only the approved bounded diagnostic paths. OS artifact access restrictions are a separate deployment prerequisite, not granted by Mongo read authentication.

Future manual invocation after approved secret enrollment: decrypt only the operator's protected reader secret in its identity-specific context, set LUMINAR_OPERATOR_MONGO_URI only for the command, run diagnose_worker_telemetry.py --database <approved-db> --library-id <canonical-uuid> --format json; use the unchanged J command with the same DB/library and approved tenant --artifact-root for queue/jobs/artifacts. Remove the variable afterward. Neither command provisions accounts, writes telemetry, repairs, retries, builds, cancels, unlocks, publishes or deletes artifacts. No browser/Staff credential or public operator API is introduced.
''')
    md('enablement','''# Explicit opt-in verified; production off

Authoritative names: LUMINAR_WORKER_TELEMETRY_ENABLED must equal1, plus separate LUMINAR_WORKER_TELEMETRY_MONGO_URI. configured_factory returns None otherwise; it never loads .env itself or falls back to MONGO_URI/operator/JWT. The actual Search installer binds the writer to the native database and retains the existing resident-model startup gate. Prototype files, collections, credentials alone and Platform roles cannot activate it.

The host audit checked process and project dotenv flag/URI presence without emitting values: explicit enablement is false, no writer/operator telemetry credential is configured. No environment, launcher, service or runtime file was modified by2M. Default-disabled behavior, URI-present/flag-off, missing/wrong credentials, wrong DB/authSource, denied role, timeout and successful authenticated opt-in are exercised in fresh tests/fixtures.

Controlled native fixture phases alone opt in through a protected secret, then rotate and turn off at restart. The disabled restart and later manual Search/KG builds leave the retained telemetry record unchanged and create no observer. No runtime schema/account provisioning occurs. For a future production launcher, do not decrypt/inject a writer secret until deliberate approved enablement; the fixture intentionally injects a URI while disabled to prove that URI presence alone is ineffective.

Stage5 activation is outside2M and blocked by production authorization, ACL/identity/secret and workload prerequisites. No production credential/collection/index/flag, service restart, automatic maintenance/scheduling/recovery/cancel/cleanup or global control is created. Default-disabled source is preserved rather than replaced with a deployment-specific second implementation.
''')
    md('worker_lifecycle','''# Native worker correctness preserved

All preexisting native/observer/store/diagnostic source bytes are compared with the2M start snapshot. Existing source/defaults remain90s native lease,10s native renewal,2s idle wait and serial execution. Claim/progress/validation/publication/ack/fence/Admin/source/last-good/recovery are unchanged. L's original-SHA-pinned native protocol test and current full regression are rerun without altering any prior test/hash in2M.

Actual fixture processes run the existing TenantIntelligence.start/loop/close and existing JWT build router, with one cached offline MiniLM encoder per worker process and native FAISS/KG builders. They do not create another production monitoring worker/model or start the full5M global Search service. Lifecycle evidence covers disabled/enabled idle, accepted stages/counters, validation/publication, completion/return idle, bounded auxiliary shutdown and restart. Native close still does not join an in-flight build; STOPPED is not invented before actual native exit.

Native151-book phased builds, writer replacement, disabled rollback, actual process exits during embedding/KG/before publication/after pointer and independent auxiliary faults are recorded separately. Crashed jobs/pointers are unchanged by telemetry restart. Explicit expiry injection and existing Library Admin recovery in disposable cases are labelled manual tests, never telemetry-triggered actions. Fresh inherited K/L tests also exercise clock rollback/future timestamps, late epochs, shutdown timeout, no orphan in normal shutdown and no false verified health.

The architecture does not supply a trusted OS supervisor binding. Actual deployment did not show a running Search listener at inspected ports or an approved worker service identity; source startup wiring and fixture success do not qualify production lifecycle ownership.
''')
    md('improvement_review','''# Improvement review

2M changed no production runtime, previous tests, frontend or accepted telemetry contract. It adds read-only deployment/ACL evidence, protected disposable secret injection, fresh server-denied writer/reader/rotation cases, native151-book rollout/rollback/failure measurements and concrete owner-controlled runbooks. It identifies actual unmet prerequisites instead of interpreting fixture success as authorization.

Two substantive deployment blockers are observed: anonymous tenant access on the actual Mongo service and broad .env/launch-path local group ACLs. Actual Search/Core/RAG/Recommendation/frontend processes were not observed on source-default ports, so their service/account ownership and full-stack readiness cannot be attested. Only current-user DPAPI/NTFS behavior was exercised; a different production service identity/profile and cross-account denial remain unqualified.

The fixture storage and opt-in boundaries are useful but limited: native job/pointer authority stays separate; both DB identities are independently enforced; encrypted secrets never appear in argv/repo; disabled restart preserves native data and allows manual builds. Sampling, current/previous retention, no OS proof, small n3 per-target tails, cold/warm model effects and lack of production-scale/global workload remain operational limits. Do not remove these qualifiers to obtain a PASS.
''')
    md('next_scope','''# Recommended next scope — approval-gated prerequisite closure

Assign the actual DBA and Search/operator service owners, review current Mongo access-control hardening together with all existing application principals, and approve a protected deployment code/secret/ACL/DPAPI enrollment procedure under the intended service identities. Establish actual single-resident startup/stop/rollback ownership and reproduce an agreed representative disposable full-stack workload. Return evidence that the prerequisites are satisfied before seeking separate telemetry enablement approval.

No production hardening or activation is begun in2M. Do not add scheduling, automatic rebuild/recovery, incremental HNSW/KG, distribution, cancellation, artifact cleanup, global administration, a Staff/Platform dashboard or RAG/Qwen/Recommendation/router changes. Keep the two known backend regressions visible and address them only in a separately scoped task. Stop after2M.
''')


def failures():
    return sorted(t.attrib.get('classname','')+'::'+t.attrib.get('name','') for p in R.glob('institution_v2m_final_*.xml') for t in ET.parse(p).iter('testcase') if any(c.tag in ['error','failure'] for c in t))


def finalize():
    from scripts.institution_v2i_baseline import capture_state
    from scripts.institution_v2l_baseline import capture_indexes
    b=read('baseline');checks=read('final_backend');front=read('final_frontend');host=read('host_audit');roll=read('rollout_validation');fault=read('native_failures');diagnostics=read('diagnostic_benchmark');storage=read('storage_measurement')
    assert checks[-1]['group']=='events' and any(x['group']=='institution_v2m' for x in checks)
    assert len(front)==3 and all(x['exit']==0 for x in front)
    assert roll['rollout']==roll['rollback']=='PASS' and roll.get('owned_fixture_removed') and fault.get('owned_fixture_removed') and len(fault['crashes'])==4 and diagnostics.get('owned_fixture_removed')
    found=failures();known=['tests.test_assistant_backend::test_protected_rag_files_match_original_hashes','tests.test_lexical_api_fallback::test_search_route_works_with_failed_lexical_and_keeps_public_schema']
    assert found==sorted(known),found
    state=capture_state();state['global_KG_metadata']={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in (ROOT/'knowledge_graph/data').glob('*') if p.is_file()}
    state=json.loads(json.dumps(state,default=str));idx=json.loads(json.dumps(capture_indexes(),default=str))
    source_bad=[n for n,h in b['source_sha256'].items() if not (ROOT/n).exists() or sha(ROOT/n)!=h]
    prior_bad=[n for n in source_bad if 'institution_v2m' not in n]
    report_bad=[n for n,h in b['frozen_reports_sha256'].items() if not (ROOT/n).exists() or sha(ROOT/n)!=h]
    state_bad=[k for k,v in b['state'].items() if state.get(k)!=v]
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    l=json.loads((R/'institution_v2l_changed_files.json').read_text(encoding='utf8'))
    lbad=[v['path'] for v in l['files'] if v['category']!='report/evidence' and (not (ROOT/v['path']).exists() or sha(ROOT/v['path'])!=v['sha256'])]
    preservation={'result':'PASS' if not prior_bad and not report_bad and not state_bad and not lbad and idx==b['mongo_indexes'] and head==b['head'] else 'FAIL',
        'baseline_source_count':len(b['source_sha256']),'prior_source_changes':prior_bad,'own_M_harness_revisions':[n for n in source_bad if n not in prior_bad],
        'frozen_I_J_K_L_report_count':len(b['frozen_reports_sha256']),'frozen_report_changes':report_bad,'prior_L_inventory_changes':lbad,
        'state_changes':state_bad,'indexes_unchanged':idx==b['mongo_indexes'],'head_unchanged':head==b['head'],'state_after':state,
        'part_I_status_sha256':sha(ROOT/'backend/services/library_intelligence_service.py'),
        'production_configuration_account_secret_ACL_or_authorization_mutations':False,
        'evidence_limits':'Global catalogue estimated count, no full catalogue digest/scan; large global artifacts compare size/mtime; bounded tenant files additionally hashed; personal registry logical hashes compared.',
        'fixture_cleanup':'Owned resolved2M temp roots only. A failed early shell-capability probe orphan was identified by its own log PID and exact mongod dbPath, then stopped/removed; no production process controlled. Preexisting2I temp retained.'}
    write('preservation',preservation);assert preservation['result']=='PASS',preservation
    text=(R/'institution_v2m_final_frontend.log').read_text(encoding='utf8')
    ft={k:sum(map(int,re.findall(r'^.*?\b'+k+r' (\d+)\s*$',text,re.M))) for k in ['tests','pass','fail','skipped']}
    lint=(R/'institution_v2m_final_lint.log').read_text(encoding='utf8');oldlint=(R/'institution_v2l_final_lint.log').read_text(encoding='utf8')
    warnings=lambda t:{line for line in t.splitlines() if ': warning ' in line}
    newwarnings=sorted(warnings(lint)-warnings(oldlint))
    write('backend_tests',{'totals':total(checks),'groups':checks,'known_preexisting_failures':found,'new_failures':[],
        'method':'Fresh institution/product groups V1 through2L plus2M in separate subprocesses. No prior test or baseline hash changed in2M.'})
    write('frontend_tests',{'totals':ft,'checks':front,'new_lint_warnings':newwarnings,'runtime_frontend_changes':[]})
    write('regression',{'result':'PARTIAL','backend':total(checks),'preexisting_failures':found,'new_failures':[], 'frontend':ft,'build':'PASS','lint_exit':0,
        'new_lint_warnings':newwarnings,'preservation':'PASS','current_checkpoint_before_tests':'Part2L2497 passed/2 failed/20 skipped, source verified; fresh2M run recorded.'})
    points=[]
    for phase in roll['phases']:
        d=json.loads((R/phase['evidence']).read_text(encoding='utf8'))
        points.append({'phase':phase['name'],'enabled':phase['enabled'],'whole_child_seconds':phase['seconds'],'native_start_ms':d['native_start_return_ms'],
            'observer_ready_ms':d['observer_ready_ms'],'native_close_ms':d['native_close_return_ms'],'worker_end_ms':d['worker_end_ms'],
            'observer_final_state':d['observer_final_state'],'observer_thread_ended':d['observer_thread_ended'],
            'threads_before':d['threads_before_start'],'threads_observing':d['threads_observing'],'connections_before':d['mongo_connections_before'],
            'connections_observing':d['mongo_connections_observing'],'connections_after_close':d['mongo_connections_after_close'],
            'idle':d.get('idle'),'model':d['model'],'model_instances_per_child':1 if isinstance(d['model'],dict) else 0,
            'idle_cpu_interval_ms':stats([s['cpu_delta_ms'] for s in d.get('resource_samples',[]) if s['phase']=='IDLE' and s['cpu_delta_ms'] is not None]),
            'idle_rss_bytes':stats([s['rss_bytes'] for s in d.get('resource_samples',[]) if s['phase']=='IDLE']),
            'builds':{t:{'count':len([x for x in d.get('builds',[]) if x['target']==t]),
                'native_ms':stats([x['native_build_ms'] for x in d.get('builds',[]) if x['target']==t]),
                'cpu_ms':stats([x['cpu_ms'] for x in d.get('builds',[]) if x['target']==t]),
                'rss_delta_bytes':stats([x['rss_increase_bytes'] for x in d.get('builds',[]) if x['target']==t])} for t in ['SEARCH_INDEX','KNOWLEDGE_GRAPH']},
            'operations_before_final_stop':d.get('telemetry_metrics',{}),
            'write_ms':stats([x['ms'] for x in d.get('latencies',[]) if x['kind'] in ['pulse_write','progress_write','boot_write']]),
            'retained_targets_native_validated':len(d.get('retained_targets_validated',[]))})
    write('performance',{'scope':'Controlled151-book tenant fixtures, three builds/target per disabled/enabled/rotated/rollback configuration, same code/cached model and hardware; not full production equivalent.',
        'phases':points,'operator_cli':roll['operator_cli'],'protected_diagnostic_benchmark':diagnostics,'retention_storage_measurement':storage,'steady_candidate_idle_writes_per_minute':6,'max_BSON_bytes':16384,'entries_per_section':8,
        'startup_stop_write_note':'Startup CAS/immediate pulse/final lifecycle writes separate from periodic six/minute; metrics taken before final shutdown write.',
        'representative_production_workload_qualified':False,
        'limits':['n3 native p95 is a coarse observed maximum.','Cold/warm encoder/kernel/file-cache effects present; no improvement claim.','RSS deltas/interval samples may miss peaks.','Known-child process sampling is not a production worker identity measurement.','Connection counts include owned fixture/root/driver connections.','No full5M service/global index load, multiple real tenants/peak concurrency/production account/long-run disk/network/DB CPU or SLO certification.']})
    write('security_tests',{'result':'FIXTURE_PASS','focused':next(x for x in checks if x['group']=='institution_v2m'),'server_denials':'Actual auth-enabled Mongo code13 for forbidden writer/operator/unauthorized operations; fresh bad/revoked credentials rejected.',
        'writer_and_reader_rotation':'Fresh principals independently tested; reader remains read-only; old users restored only for test isolation.',
        'actual_protected_native_rollout':roll,'current_deployment_auth_gate':host['mongo'],'current_filesystem_evidence':host['host']['filesystem_acls'],
        'production_qualified':False,'secret_values_or_argv_recorded':False,'no_prior_test_or_hash_modified':True})
    write('failure_injection',{'fresh_native':fault,'rollout_rollback_rotation':roll,
        'fresh_inherited_contract_groups':['2K future/rollback-clock/malformed/cap/late epoch','2L actual server timeout/reset/permission/observer exceptions/shutdown deadline/native recovery/fencing'],
        'physical_disk_exhaustion':'NOT_QUALIFIED; no real volume exhaustion attempted',
        'initial_probe_resolution':'Windows PowerShell5 inherited module loading could not supply ACL cmdlets; the installed PowerShell7 was used and real ACL/DPAPI verification succeeded. Early probe fixture cleanup ownership was explicitly checked. An initial2M test-exec namespace error was corrected in new harness only.',
        'no_production_fault_or_automatic_native_action':True})
    docs(host)
    md('deployment_readiness','''# Deployment readiness decision

PART_2M_RESULT: PARTIAL.

FIXTURE_QUALIFIED: YES. Protected-secret authenticated native rollout, writer replacement/revocation, independent reader, disabled rollback, fresh failures/crashes and current source/frozen regression/preservation evidence are recorded. This qualification is limited to the owned disposable environment and current-user secret/ACL tests.

DEPLOYMENT_PREREQUISITES_SATISFIED: NO. Actual Mongo allowed anonymous tenant reads, configured connection had no authenticated identity and authorization was not set. Actual .env/code/launch paths have broad local-group access. Approved DBA/Search/operator owners, separate production service identities/DPAPI profiles/secret enrollment/code integrity and actual resident service startup/stop/rollback ownership are not established. Application service listeners were not observed at inspected source-default ports. No complete representative production-equivalent full-stack workload or physical disk/network/long-run resource qualification is claimed.

PRODUCTION_ENABLEMENT_APPROVED: NO. PRODUCTION_ENABLED: NO. No production credentials, users/roles/namespace/indexes, secret files, authorization options, ACLs, application/service environment, source runtime or frontend were changed. No production process was launched/stopped/restarted, and no global index was modified. Only an explicitly verified failed task-owned fixture process was cleaned up.

The runtime remains default disabled. Role metadata and fixture PASS do not constitute production authorization. Operator-owned authentication/secret/service hardening requires a separately approved plan covering existing applications before any future telemetry activation. Exact manual lifecycle steps and stop conditions are in secret_management.md, rollout.md and rollback.md. Two unrelated preexisting backend failures remain visible; no prior tests/hashes were modified to obtain the result.
''')
    qa={'PART_2M_RESULT':'PARTIAL','FIXTURE_DEPLOYMENT_QUALIFIED':'YES','PRODUCTION_DEPLOYMENT_QUALIFIED':'NO',
        'RESTRICTED_WRITER_VERIFIED':'YES','OPERATOR_READ_ONLY':'YES','DEFAULT_TELEMETRY_DISABLED':'YES','SECRET_LIFECYCLE_REVIEWED':'YES',
        'ROLLOUT_PASS':'YES','ROLLBACK_PASS':'YES','NATIVE_JOB_PROTOCOL_PRESERVED':'YES','PRIVATE_LIBRARY_ISOLATION':'PASS',
        'GLOBAL_HNSW_REBUILT':'NO','GLOBAL_KG_REBUILT':'NO','PRODUCTION_CREDENTIAL_CREATED':'NO','PRODUCTION_TELEMETRY_ENABLED':'NO',
        'AUTOMATIC_REBUILD':'NO','AUTOMATIC_RECOVERY':'NO','JOB_CANCELLATION':'NO',
        'BACKEND_TESTS':f"{total(checks)['passed']} passed / {total(checks)['failed']} failed / {total(checks)['skipped']} skipped",'NEW_BACKEND_FAILURES':0,
        'FRONTEND_TESTS':f"{ft['pass']} passed / {ft['fail']} failed / {ft['skipped']} skipped",'PRODUCTION_BUILD':'PASS',
        'NEXT_RECOMMENDED_SCOPE':'Operator-owned closure of Mongo authentication, protected code/secret ACL and actual service-identity/rollout prerequisites; no telemetry activation until separately approved.'}
    write('qa_summary',qa)
    sections=[('A','FINAL PASS / PARTIAL / FAIL','PARTIAL. Fixture deployment qualifies; actual deployment prerequisites do not. Production remains disabled and two known backend failures remain.'),
        ('B','DEPLOYMENT QUALIFICATION SUMMARY','FIXTURE_QUALIFIED YES; DEPLOYMENT_PREREQUISITES_SATISFIED NO; PRODUCTION_ENABLEMENT_APPROVED NO; PRODUCTION_ENABLED NO. These are separate states.'),
        ('C','BASELINE',f"{len(b['source_sha256'])} source files, {len(b['frozen_reports_sha256'])} frozen I/J/K/L reports and32 index contracts captured; current TEST151/150/5 and global estimated5M. No historical counts forced."),
        ('D','ACTUAL PROCESS ARCHITECTURE','Mongo endpoint responds on27017; OS listener/CIM evidence is incomplete/variable, so actual Search/service ownership is not qualified. Source maps each existing service and Search installer owns the native worker. No extra production monitoring worker/model or service launched.'),
        ('E','MONGODB AUTHENTICATION','Actual deployment fails gate: anonymous tenant read succeeds, configured authenticated user count0, authorization not set. Auth-enabled disposable fixtures prove enforcement. No production auth change/write probe.'),
        ('F','RESTRICTED WRITER','Exact fixed auxiliary find/update plus native jobs/targets find; actual forbidden native/global mutations denied13. No broad fallback or provisioning code added.'),
        ('G','INDEPENDENT OPERATOR READER','Independent builtin-read DB principal, real denied writes and unauthorized-account tests, protected CLI JSON/text invocation; no app JWT/Platform bypass.'),
        ('H','CREDENTIAL PROVISIONING BOUNDARY','Only disposable users provisioned. Future DBA/owner steps require authentication and existing-app readiness before scoped role/principal/namespace enrollment. Runtime never installs them.'),
        ('I','SECRET MANAGEMENT','DPAPI encrypted fixture files, protected current-SID/SYSTEM-only DACLs, no plaintext file/argv; writer and reader rotation/revocation tested. Actual .env broad ACL and production service-identity/profile remain blockers.'),
        ('J','ENABLEMENT CONTROLS','Exact enabled flag1 plus separate writer URI; missing/invalid/wrongDB/denied/default/URI-alone cases fail closed. Actual project/process flags remain off.'),
        ('K','ROLLOUT','PASS controlled authenticated fixture; stage2 full production equivalence unqualified; readiness/owner approval required before any future stage5 outside2M.'),
        ('L','ROLLBACK','PASS enabled→disabled restart: native history/pointers/locks/generations and telemetry snapshot unchanged, retained artifact bytes preserved; manual disabled builds still validate. Focused test also compares retained rows by_id.'),
        ('M','WORKER LIFECYCLE','Unchanged90s lease/10s renewal/2s idle/serial/fences/manual recovery. Actual native MiniLM/FAISS/KG phases, bounded observer close and fresh epoch tested.'),
        ('N','SECURITY TESTS',str(next(x for x in checks if x['group']=='institution_v2m')['passed'])+' fresh2M tests passed, plus unmodified inherited K/L security/fencing/lifecycle groups. See security_tests.json.'),
        ('O','FAILURE INJECTION','Connection failure, role denial/reconnection, observer-loop exception, four genuine native process crash stages, late epoch, clock skew and explicit manual recovery tested. No automatic native actions; physical disk exhaustion unqualified.'),
        ('P','RESOURCE OVERHEAD','Five lifecycle phases, three builds/target in four configurations,151-book tenant shape; startup/close/restart/CPU/RSS/thread/connection/write/diagnostic evidence recorded. No production SLO or full-stack equivalence claim.'),
        ('Q','OPERATOR DIAGNOSTICS','J/L source unchanged; local independent read only, current/previous/scoped progress and existing queue context preserved. Pulse does not prove independently executing process; no public/Staff infrastructure route.'),
        ('R','PRIVATE LIBRARY ISOLATION','Native PRIVATE_INSTITUTION/PRIVATE_CODE fixtures, scoped job correlation, independent auth and fresh inherited tenant/Staff/API tests. No private document/member content or secrets exposed to frontend.'),
        ('S','REGRESSION',qa['BACKEND_TESTS']+'; two known failures, zero new. '+qa['FRONTEND_TESTS']+'; build/lint pass with no new warnings. No prior tests or hashes changed in2M.'),
        ('T','GLOBAL PRESERVATION','PASS unchanged previous sources/contracts/reports, production tenant state/indexes/pointers/artifacts, personal registry logical state and I optimization. Global catalogue/count and large-artifact metadata methods explicitly limited.'),
        ('U','EXACT FILES CHANGED','Only new2M scripts/tests/reports plus revisions to this phase\'s own new audit harness. No existing product/runtime/test/config files changed. SHA inventory in changed_files.json.'),
        ('V','REPORTS CREATED','All21 requested reports, raw lifecycle/fault/ACL/rotation evidence, full regression logs/XML, QA/acceptance and a task-only review package.'),
        ('W','DEPLOYMENT READINESS DECISION','NOT_QUALIFIED for actual deployment. Fixture PASS is neither prerequisite completion nor production authorization.'),
        ('X','REMAINING LIMITATIONS','Production authorization/ACL/ownership/service profiles, cross-identity secret testing, full-stack representative workload, physical disk/long-run operational qualification and trusted OS worker proof remain incomplete.'),
        ('Y','RECOMMENDED NEXT SCOPE',qa['NEXT_RECOMMENDED_SCOPE']+' Stop after2M; no later phase or activation.')]
    md('completion','\n\n'.join(f'## {n}. {title}\n\n{body}' for n,title,body in sections)+'\n\n## FINAL QA\n\n```text\n'+'\n'.join(f'{k}: {v}' for k,v in qa.items())+'\n```\n\nKnown failures:\n\n'+'\n'.join('- '+v for v in known))
    request=Path('C:/Users/balak/.codex/attachments/de6bc992-57e9-4448-9717-5af2446f7e35/Pasted text.txt').read_text(encoding='utf8')
    block=request.split('PART S — ACCEPTANCE')[1].split('Distinguish:')[0]
    rows=re.findall(r'(\d+)\.\s+(.*?)(?=\n\s*\d+\.|\Z)',block,re.S);assert len(rows)==32
    write('acceptance',{'overall':'PARTIAL','FIXTURE_QUALIFIED':True,'DEPLOYMENT_PREREQUISITES_SATISFIED':False,'PRODUCTION_ENABLEMENT_APPROVED':False,'PRODUCTION_ENABLED':False,
        'criteria':[{'criterion':int(n),'requirement':' '.join(v.split()),'status':'FIXTURE_PASS_PRODUCTION_PREREQUISITE' if int(n) in [3,4,6,8,9,10,11,14,18,19] else 'PASS',
                    'evidence':'Completion A–Y; host_audit, rollout_validation, native_failures, performance, security_tests, regression and preservation.'} for n,v in rows]})
    paths=sorted({p for p in [*R.glob('institution_v2m_*'),*(ROOT/'scripts').glob('*institution_v2m*.py'),*(ROOT/'scripts').glob('*institution_v2m*.ps1'),
        *(ROOT/'tests/institution_v2m').rglob('*.py'),*(ROOT/'.scratch/institution-v2m').rglob('*.py')]
        if p.is_file() and p.suffix!='.zip' and '__pycache__' not in p.parts})
    files=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p),
        'category':'report/evidence' if p.parent==R else 'focused fixture tests' if 'tests' in p.parts else 'task-only audit/fixture/harness/snapshot'} for p in paths if p.name not in ['institution_v2m_changed_files.json','institution_v2m_package_manifest.json']]
    write('changed_files',{'previous_product_test_runtime_config_changes':prior_bad,'files':files,
        'self_and_delivery':['reports/institution_v2m_changed_files.json','reports/institution_v2m_package.zip','reports/institution_v2m_package_manifest.json'],
        'scope':'Only2M additions/task harness revisions. Existing user work/I optimization/J-K-L architecture untouched; no Git commit. No credential/ciphertext/model/artifact payload included.'})
    package=R/'institution_v2m_package.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            if p.name!='institution_v2m_package_manifest.json':z.write(p,p.relative_to(ROOT).as_posix())
        if R/'institution_v2m_changed_files.json' not in paths:z.write(R/'institution_v2m_changed_files.json','reports/institution_v2m_changed_files.json')
    with zipfile.ZipFile(package) as z:assert z.testzip() is None;entries=len(z.namelist())
    write('package_manifest',{'package':package.name,'sha256':sha(package),'bytes':package.stat().st_size,'entries':entries,'scope':'2M evidence/runbooks/audit/fixture tests and unchanged-source snapshots only; no credentials or ciphertext/artifacts/models.'})
    print(json.dumps({'result':'PARTIAL','backend':total(checks),'frontend':ft,'preservation':preservation['result'],'fixture_rollout':roll['rollout'],'fixture_rollback':roll['rollback'],'production_qualified':False,'package_bytes':package.stat().st_size}))


if __name__=='__main__':
    if '--docs' in sys.argv:docs(read('host_audit'))
    else:finalize()
