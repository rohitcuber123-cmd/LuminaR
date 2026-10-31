"""Build reviewable 2K evidence from measured files; never modify product/runtime state."""
import hashlib,json,re,subprocess,sys,xml.etree.ElementTree as ET,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
R=ROOT/'reports'


def read(name):return json.loads((R/('institution_v2k_'+name+'.json')).read_text(encoding='utf8'))
def write(name,data):(R/('institution_v2k_'+name+'.json')).write_text(json.dumps(data,indent=2,default=str),encoding='utf8')
def md(name,text):(R/('institution_v2k_'+name+'.md')).write_text(text.strip()+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def design_reports():
    md('architecture','''# Part 2K architecture — isolated prototype only

Decision: no production runtime integration. The native worker has no per-instance lifecycle observer seam, its `close()` does not join an in-flight build, and deployment writer ownership/supervisor proof is unqualified. Process-global laboratory wrapping is unsuitable for production. Existing Part 2G–2J files, routes, indexes, job schemas and privileges stay byte-for-byte preserved; see preservation.json.

## Actual call graph

`search/api.py → search.library_intelligence_api.install(app, engine) → TenantIntelligence(encoder, reranker, model_version)`. Install registers startup `service.start` only when resident embedding model and reranker both exist; shutdown calls `service.close`. No lexical-only build capability is added. `TenantIntelligence.start → store.initialize → daemon loop → run_one → store.claim(worker_id)`. Claim chooses oldest effective-active QUEUED job, enters `intelligence_barrier → institution_repository.library_mutation`, atomically sets RUNNING/DATASET, worker_id, fresh fence, started/heartbeat and 90-second lease, then target fence.

`run_one → separate renewal thread → store.heartbeat(lease_query)` every ten seconds. `store.dataset → native Library Admin guard + lease + canonical local/enriched source + immutable source fingerprint/snapshot/generation`. Search uses model lock, bounded32 embedding batches, tenant SQLite vector cache, normalized384 vectors and FAISS HNSW; KG uses canonical metadata terms and deterministic nodes/edges. Native `store.progress` checks lease and acknowledges job stage/state/counters before target display update.

`run_one → checksums → manifest durable write → progress VALIDATING/VALIDATION → artifacts.validate → rename .building to immutable final → heartbeat-loss check → progress PUBLISHING/PUBLISH → intelligence_barrier → lease/Admin/source-fingerprint recheck → fenced target pointer → ACKNOWLEDGEMENT_LOSS hook → audit → SUCCEEDED acknowledgement → clear target active job/fence`. Known failed/unpublished errors yield FAILED; publication uncertainty, fencing/crash/heartbeat-loss yield RECOVERY_REQUIRED. Unknown crash may leave RUNNING/VALIDATING/PUBLISHING durable state until existing status/reconciliation/explicit recovery handles it. Telemetry does not rewrite these states.

`close → stop.set + cache.clear`; no native join. Loop is serial with two-second idle waits and swallowed outer errors; no scheduler or automatic recovery. `backend.routes.library_intelligence` retains JWT/member authorization and explicit Admin build/recovery controls. Native status may record source staleness; it is not used by the read-only telemetry writer/CLI.

## Prototype path

Only `scripts/institution_v2k_native_child.py` enables `scratch/institution_v2k_telemetry/adapter.py`, after fixture prefix/explicit child guards. The adapter wraps claim AFTER native acknowledgement and run_one completion, queues canonical internal claim context, and starts a separate Agent thread. No callback performs network I/O. Agent uses its own restricted Actor Mongo connection. Actor reads native claim-bound durable state and writes only a preallocated auxiliary singleton. No production module imports this prototype.

The new fixture-only diagnostic supplement imports unchanged Part 2J authentication. It reads exactly one named auxiliary collection and reuses bounded native job/target reads. Original J CLI/allowlist remain unchanged. No HTTP endpoint, Staff card, frontend polling, process health animation or supervisor implementation is added.
''')
    md('worker_identity','''# Worker instance identity — PROTOTYPE_ONLY

Each Actor constructs a fresh canonical UUID4, independently of native `tenant-UUID` worker_id, plus a random32-byte boot nonce digest. Singleton epoch CAS rotates current to previous on successful start. Filters for pulse/progress include epoch + instance UUID + private boot digest, so a late old instance matches no current record. Native worker reference is a one-way digest, never a PID. Output returns a shortened digest of instance identity, without boot digest, native worker_id or fence.

Actual authenticated tests cover restart, two simultaneous starts, duplicate UUID/different boot rejection, old late pulse, and retained native lease. This is a single-slot laboratory identity, not distributed coordination. Two fresh concurrent boots may both succeed in sequence; only the final epoch remains current. Neither acquires native job ownership. Only current and immediate previous instance are retained; older history becomes unavailable. There is no durable unbounded uniqueness registry, so collisions with older evicted history are not exhaustively detectable; UUID4 plus boot nonce and epoch prevents accidental takeover under tested races. Deployment credential possession still cannot attest executable code identity. OS/service ownership is not qualified.
''')
    md('liveness_contract','''# Independent self-report channel

Agent is separate from the native job lease renewal thread. Candidate pulse interval10s, idle and active; monotonic process scheduling and bounded500ms Mongo calls. It continues while embedding/validating/publishing, with no native lease update. Labels: RECENTLY_OBSERVED for a valid last server-written pulse within30s; STALE beyond30s; STOPPED_REPORTED only for coherent best-effort shutdown; UNKNOWN for missing/malformed/future/rollback evidence. IDLE/ACTIVE are explicitly the most recent self-report. Active self-report is not a present ownership guarantee.

A durable pulse proves only successful writing at its recorded time. It never proves the process still executes. process_independently_verified is always false. No HEALTHY or PROCESS_VERIFIED_ALIVE classification exists. Stale/no-progress never asserts death or a stall; stalled stays NOT_DETERMINED. No ETA, CPU/RAM/GPU attribution is offered by the operator command. Harness-owned child PID measurements are controlled experiment measurements, not production identity verification.

Native lifecycle evidence and actual CLI output are in native_validation.json and native_lifecycle.json; idle/return-to-idle and idle crash supplement are separately identified. A crash has no fabricated shutdown. STOPPED is attempted only after native thread join has ended; incomplete join produces no STOPPED. Native close behavior itself remains unchanged.
''')
    md('telemetry_authentication','''# Authentication and ownership qualification

Only an auth-enabled, task-owned loopback mongod is provisioned. Fixture admin creates a fixed singleton and strict validator, then a DB-local SCRAM user with exactly: find/update on institution_worker_telemetry_v2k, find on institution_intelligence_jobs and institution_intelligence_targets. No insert/delete/create/index/TTL or native write grant. Actor verifies real connectionStatus(showPrivileges=true), one DB-local principal and the exact effective action/resource set. It rejects root, the J read principal, anonymous credentials, missing credentials and non-fixture database names.

Unchanged Part 2J reader still requires explicit loopback SCRAM URI, database=authSource and only built-in DB-local read role. Original J four-collection allowlist is untouched. Prototype supplement is local CLI only, read-only, fixture-prefix restricted and accepts the operator URI only through LUMINAR_OPERATOR_MONGO_URI. It cannot provision accounts or act on jobs.

Actual server tests deny operator update(code13), telemetry writes to jobs/targets/locks/catalogue/global collections(code13), and telemetry insert/delete/create(code13). Writer role revocation produces PERMISSION_DENIED; failCommand on the owned mongod produces real timeout and closed connection. App JWTs, GENERAL_USER, LIBRARIAN, tenant ADMIN, outsider and platform-only ADMIN are not operator credentials. Native HTTP fixture builds use the actual JWT decoder and current Mongo identity, no dependency override.

No production account, secret, role, collection or index is provisioned; no public mutation endpoint exists. Credentials are short-lived in parent/child environment and task temp storage only, never serialized in reports. Permission proves credential enforcement, not executable attestation: any code holding this credential could forge auxiliary content. Native job/pointer revalidation and information-only use reduce impact, but secure deployment secret ownership and per-worker code-path integration remain unqualified. Production integration is therefore gated.
''')
    md('storage_design','''# Bounded auxiliary storage

One separate collection institution_worker_telemetry_v2k, one administrator-preallocated _id resident-tenant-worker-v1, built-in unique _id index only. Schema1 stores epoch, current and previous instance. Each holds at most8 recent claim-bound progress records; max whole-document BSON16384 bytes enforced server-side with $bsonSize and JSON schema maxItems. Writer has update but no insert/delete, so it cannot increase document count or run retention deletes. No catalogue/job schema changes, TTL, append-only journal or artifact cleanup.

Rotation retains one prior lifecycle and evicts older auxiliary evidence, never jobs/generations/audit/artifacts. Progress array replaces one claim key and caps to8. Both current and previous at capacity are tested together. Size rejection degrades telemetry only. Readers reject oversized/malformed records and expose at most8 tenant-filtered entries. Singleton lookup examines one indexed document independently of job history; measured full native reader plans are in performance.json.

Candidate idle six pulse writes/minute plus one start and best-effort stop. Active poll1s performs bounded native/auxiliary reads and coalesces identical tuples: at most one active progress write per poll, plus terminal queued contexts (deque8), plus pulse. Active polling can miss short transitions; timestamps are observations, not an audit trail. No startup schema provisioning is attempted by Actor. Startup uses auth check, fixed read and CAS write. Mongo failures stop initial observer startup or are bounded per-loop retries; no retry queue/log/document growth. Native worker continues independently. No retention or telemetry scale SLO is claimed.
''')
    md('progress_contract','''# Durable progress observation contract — PROTOTYPE_ONLY

Authoritative native tuple: state, stage, progress_current, progress_total. Internal context comes only from an acknowledged claim; Actor reads by canonical job/library/fence/native worker identity and checks target, active ownership and unexpired native lease. It accepts only native stages DATASET, EMBEDDING, KG_METADATA, VALIDATION, PUBLISH, COMPLETE, FAILED, RECOVERY_REQUIRED, RECOVERED and bounded integer counters.

First observed accepted active tuple, forward native state phase, stage change or counter increase counts as progress. Changed total without stage/phase/current advance does not. Identical tuples and heartbeat/lease updates cause no progress write and no timestamp advance. FAILED/RECOVERY_REQUIRED are outcomes, never invented successful progress. SUCCEEDED counts only with matching native published_by_job_id, artifact generation and requested source generation. Completed counters alone do not prove publication. Repeated unknown terminal tuples are not optimistically upgraded; a later verified reader remains conservative.

last_progress_observed_at uses Mongo $$NOW in the auxiliary update AFTER reading accepted native state. It is a post-read observation timestamp, not exact time of native state commit. No timestamp is written before the accepted tuple is read. A one-second poll may coalesce intermediate transitions. A delayed first observation may be much later than the real change. There is no retroactive backfill. It is unsuitable for exact progress SLAs or an authoritative transition journal.

Reader independently joins library/job/target, native worker digest, fence digest, exact tuple fingerprint, lease and pointer acknowledgement; changed identity/sequence or lag produces UNKNOWN. Its multi-read view is BEST_EFFORT_REVALIDATED, not a transaction. Native job can change immediately after a recheck; this is one unresolved production causal/race qualification gate. last_progress_at is not added to frozen native jobs. Native stage/counters and job heartbeat remain authoritative and separately displayed; no state or ownership is derived from telemetry.
''')
    md('clock_semantics','''# Clock semantics

Auxiliary started/seen/stopped/progress/outcome timestamps use Mongo server $$NOW. Pulse scheduling uses local monotonic time. The observer's bound native lease check uses UTC wall time, matching the existing native lease model without changing it; skew can suppress evidence. It does not extend a lease. Reader captures server $$NOW and rejects future progress/pulse, started-after-seen and malformed dates. Comparing current server time below last_seen sets a sticky per-instance clock_rollback bit; all recency for that instance becomes UNKNOWN. A restart may establish a new instance but does not rewrite past native timestamps.

Future timestamps, simulated backward last_seen and missing timestamps are tested. The real-crash stale threshold is explicitly evaluated at logical observer now+31s for prompt controlled validation; it is not described as a31-second wall-clock wait. No NTP discipline, multi-host clock proof, suspension or supervisor monotonic clock source is deployment-qualified. A forward server clock jump can temporarily make evidence look stale; no automatic corrective action follows.
''')
    md('worker_restart','''# Restart and shutdown

Native worker start installs no telemetry hook. The child-only adapter starts Agent, then actual native start/serial loop. New Agent gets a new UUID/epoch, old record rotates to previous, and old pulse/progress CAS fails. Restart never transfers a native lease or rewrites ownership. Native claim still considers only existing manually queued jobs; an abandoned active job remains unresolved. Existing explicit recovery alone may fence/repair it.

Native close does not join. Laboratory adapter requests close and joins at most5s; only if native thread ended does Agent attempt STOPPED, then Agent has at most3s join and500ms individual Mongo deadlines. This is best-effort, not a production lifecycle guarantee. Crash uses actual os._exit(77), so no Python finally/shutdown path runs. Six native crash stages and repeated fresh-process restarts are recorded in native_validation.json; idle crash, return to idle, last-good retention, A/B/C queue and explicit native recovery are in native_supplement.json. Explicit expiry injection/recovery is isolated fixture work and is never triggered by a telemetry reader.
''')
    md('fencing_safety','''# Native correctness remains authoritative

All original 2G–2J source hashes are compared with the task-start1590-file baseline. Native lease90s, renewal10s, serial daemon, claim barrier, lease_query, fence token, Admin/source rechecks, artifact validation, atomic rename, pointer fence, last-good and acknowledgement order are unmodified. Actor privilege enforcement denies native collection writes. Telemetry CAS protects only auxiliary current-instance evidence; it cannot confer a job fence.

Actual tests reject stale context/fence and expired lease; readers invalidate mismatches. Late old-instance pulse fails epoch/UUID/boot filter. Concurrent starts leave only the final epoch current. Genuine child crashes leave native active state and publication pointer unchanged on restart, including pointer-published-before-ack. Separate explicit native recovery fixture experiments retain existing semantics: unpublished→FAILED, matching validated published pointer→SUCCEEDED. These actions use the existing Library Admin endpoint, never diagnostic code.

No telemetry path imports native job mutation helpers. It cannot claim, renew, recover, retry, cancel, publish, unlock barriers or create jobs. Observer failure cannot turn an unacknowledged native job into successful publication. Source preservation and server denied-write tests are stronger evidence than a function-name-only test; see focused.xml, native_validation.json and preservation.json.
''')
    md('legacy_compatibility','''# Legacy compatibility

No migration/backfill of native jobs, targets or generations. Missing singleton, absent instance, malformed identity/timestamps, unknown old state and absent progress entry remain UNKNOWN/NOT_AVAILABLE. Old READY, FAILED and RECOVERY_REQUIRED objects continue to be interpreted by native 2G/J code. The new supplement returns an empty progress list for legacy jobs, never guessed timestamps or health. Old active lease survives worker instance rotation unchanged.

Prototype writer requires explicit preprovisioned schema1 fixture record and exact DB-local privileges. A missing record does not cause an upsert, collection creation or repair. Original J CLI works independently with its frozen four-collection allowlist; its existing no-progress-time limitation remains true. Ordinary Staff routes receive no raw process/instance/fence or infrastructure fields. Frontend library switching and access rules remain protected by the frozen regression suites, with no new UI flow.
''')
    md('operator_integration','''# Operator integration decision

The accepted Part 2J command scripts/diagnose_library_intelligence.py, authentication module and four-collection reader allowlist are unchanged. No production operator integration is enabled. A separate scripts/diagnose_institution_v2k_prototype.py command is an isolated read-only supplement; it rejects database names outside luminar_v2k_fixture_, requires the same real read-only principal, reads one fixed auxiliary singleton, scopes all progress to canonical library/job and bounds output to8 entries. No general collection selector, arbitrary URI argument, action/retry/recovery flag, remote endpoint or frontend route exists.

Example invocation for an already owned fixture only: `.venv/Scripts/python.exe scripts/diagnose_institution_v2k_prototype.py --database <fixture-db> --library-id <canonical-uuid> --format json`. Supply separately authenticated reader URI through LUMINAR_OPERATOR_MONGO_URI. Never supply credentials on the command line. Fixture scripts own provisioning and cleanup; operator commands do neither.

Actual JSON/text invocations and code13 rejected operator write are retained in native_validation.json; focused tests exercise current bounded/redacted CLI output and auth/read failure. Output says prototype_only, read_only, BEST_EFFORT_REVALIDATED, process_independently_verified=false and stalled=NOT_DETERMINED. Self-reported ACTIVE/IDLE is qualified as observed, not verified current job ownership or process health. Infrastructure-wide queue context remains available only through unchanged authenticated J tooling.
''')
    md('implementation_decision','''# Implementation and qualification decision

PARTIAL. Delivered an isolated authenticated prototype and evidence, with no production integration, activation, secrets or commit. Existing runtime sources remain unchanged. New code lives under scratch/institution_v2k_telemetry and task-specific scripts/tests only.

Gates passed in fixtures: server authorization enforcement; UUID/epoch late-write fencing; bounded storage/current+previous capacity; independent idle pulse and observed progress separation; native Search/KG publication; genuine crashes/restarts; read-only operator CLI; frozen regressions without new failures; frontend/build/lint and preservation.

Gates not passed for production: reviewed native per-instance observer/lifecycle seam; code-bound secret ownership/deployment principal provisioning; OS/supervisor identity and monitoring; exact causal timestamp/event capture rather than sampled post-read observations; all simultaneous native publication/observer race interleavings; representative production workload/resource qualification; real physical disk exhaustion and deployment outage/clock/suspension tests. Two preexisting frozen backend failures remain. No gate is weakened to claim PASS.

This is neither a production-disabled hook in native code nor a feature waiting on one environment flag. No native module imports this prototype. A later approved phase must review and implement the seam before any deployment. Stop after2K; no scheduler, maintenance, cancellation, distribution, auto-recovery or artifact deletion is implemented.
''')
    md('improvement_review','''# Improvement review

Evidence now separates native lease renewal, recent worker self-report, accepted durable progress observation and publication acknowledgement. Real Mongo roles restrict the auxiliary writer and preserve the independent read-only operator boundary. Singleton bounds prevent telemetry event/history growth; old-instance CAS prevents stale identity replacement. Native failures remain native failures.

Measured costs include one indexed auxiliary document, two extra singleton reads per supplement plus at most8 bounded job/pointer joins, six candidate idle writes/minute, coalesced active observations and500ms deadlines. performance.json gives equivalent indexed history scenarios and resource_overhead.json gives actual native idle/build pairs. Small single-pair runtime differences are noisy and establish no production speedup or SLO.

The principal weakness is sampled observation: native transitions can be missed and observation age is not exact commit age. A safe per-instance observer interface should receive trusted acknowledged transition data without blocking native work, support coalescing/backpressure and join-aware lifecycle, and undergo native race/failure qualification. Deployment secret ownership remains separate from operator authentication. No OS verification or CPU/RAM/GPU assignment should be marketed before a real supervisor identity is proven.
''')
    md('next_scope','''# Recommended next phase — explicit approval required to begin

Review and qualify a minimal per-instance native worker observer seam and join-aware lifecycle, using this isolated prototype as evidence. Require trusted accepted-transition callbacks, bounded nonblocking dispatch, startup/shutdown/restart tests, publish/ack/fence races, and a deployment-owned restricted writer principal with secret ownership review. Decide whether sampled progress observations satisfy product needs or exact acknowledged transition events are required. Retain truthful UNKNOWN without OS/supervisor proof.

Separately track the two known frozen backend failures; do not silence protected hashes or change lexical behavior during telemetry work. Do not combine the observer qualification with scheduling, automatic rebuilding/recovery, incremental indices, cancellation, distributed workers, global administration, artifact deletion or router/recommendation/RAG research. Part2K stops here.
''')


def totals(groups):return {k:sum(g.get(k,0) for g in groups) for k in ['tests','passed','failed','skipped']}
def failed_cases(tag):
    return sorted(t.attrib.get('classname','')+'::'+t.attrib.get('name','') for p in R.glob('institution_v2k_'+tag+'_*.xml')
        for t in ET.parse(p).iter('testcase') if any(c.tag in ['failure','error'] for c in t))


def finalize():
    from scripts.institution_v2i_baseline import capture_state
    # Older raw child captures may precede the explicit fence redaction in the
    # harness. Redact only this task's owned snapshots, retaining stable digests.
    from scratch.institution_v2k_telemetry.telemetry import digest
    def sanitize(value):
        if isinstance(value,list):return [sanitize(v) for v in value]
        if not isinstance(value,dict):return value
        return {(k+'_digest' if k in ['fence_token','worker_id','boot_hash'] else k):
                digest(v) if k in ['fence_token','worker_id','boot_hash'] else sanitize(v) for k,v in value.items()}
    for p in R.glob('institution_v2k_native_*.json'):
        value=json.loads(p.read_text(encoding='utf8'));clean=sanitize(value)
        if clean!=value:
            clean['snapshot_redaction']='Raw native fence/worker/boot values replaced by SHA256 digests; measurements unchanged.'
            p.write_text(json.dumps(clean,indent=2),encoding='utf8')
    baseline=read('baseline');bg=read('baseline_backend');fg=read('final_backend')
    assert fg[-1]['group']=='events' and any(g['group']=='institution_v2k' for g in fg),'Final backend still running'
    front=read('final_frontend');assert len(front)==3 and all(c['exit']==0 for c in front)
    native=read('native_validation');supp=read('native_supplement');perf=read('performance');native_faults=read('native_faults')
    assert len(native_faults['cases'])==2 and all(c.get('native_outcomes') and sum(c.get('agent_errors',{}).values())>0 for c in native_faults['cases'])
    native['qualification_scope']='Actual TenantIntelligence.start/loop with cached real encoder and native builders; existing native backend router mounted with real JWT decoding. Full Search/global engine/backend-main deployment processes were not launched. Frozen application suites remain separate.'
    native['native_fault_isolation_evidence']='institution_v2k_native_faults.json'
    write('native_validation',native)
    assert len(native['real_process_crashes'])==6 and len(supp['recovery'])==2 and supp.get('owned_fixture_removed')
    assert all(c['exit']==c['expected_exit'] for c in native['cases'])
    bfail,ffail=failed_cases('baseline'),failed_cases('final');new=sorted(set(ffail)-set(bfail))
    assert len(bfail)==len(ffail)==2 and not new
    write('backend_tests',{'baseline':totals(bg),'final':totals(fg),'groups':fg,'preexisting_failures':bfail,
        'new_failures':new,'focused_tests':next(g for g in fg if g['group']=='institution_v2k'),
        'method':'Separate subprocesses per frozen product group, all through2J plus new2K; both known failures remain enabled.'})
    log=(R/'institution_v2k_final_frontend.log').read_text(encoding='utf8')
    ft={k:sum(map(int,re.findall(r'^.*?\b'+k+r' (\d+)\s*$',log,re.M))) for k in ['tests','pass','fail','skipped']}
    warnings=[x for x in (R/'institution_v2k_final_lint.log').read_text(encoding='utf8').splitlines() if ': warning ' in x]
    bwarnings=[x for x in (R/'institution_v2k_baseline_lint.log').read_text(encoding='utf8').splitlines() if ': warning ' in x]
    write('frontend_tests',{'totals':ft,'checks':front,'existing_lint_warning_count':len(warnings),'new_lint_warnings':sorted(set(warnings)-set(bwarnings)),
        'no_frontend_changes':True,'build_warnings':'Existing dynamic/static RAG import and chunk size advisories; build exit0.'})
    state=capture_state();state['global_KG_metadata']={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in (ROOT/'knowledge_graph/data').glob('*') if p.is_file()}
    # Normalize datetimes/ObjectIds exactly as the frozen capture was serialized.
    state=json.loads(json.dumps(state,default=str))
    source_bad=[name for name,h in baseline['source_sha256'].items() if not (ROOT/name).exists() or sha(ROOT/name)!=h]
    report_bad=[name for name,h in baseline['frozen_reports_sha256'].items() if not (ROOT/name).exists() or sha(ROOT/name)!=h]
    state_bad=[k for k in baseline['state'] if baseline['state'][k]!=state.get(k)]
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    preserved={'result':'PASS' if not source_bad and not report_bad and not state_bad and head==baseline['head'] else 'FAIL',
        'baseline_sources_checked':len(baseline['source_sha256']),'source_differences':source_bad,
        'frozen_I_J_reports_checked':len(baseline['frozen_reports_sha256']),'frozen_report_differences':report_bad,
        'state_differences':state_bad,'state_after':state,'git_head_unchanged':head==baseline['head'],
        'part_2i_status_sha256':sha(ROOT/'backend/services/library_intelligence_service.py'),
        'production_telemetry_collection_created':False,'production_secrets_provisioned':False,
        'global_artifact_method':'Compare task-start size/mtime metadata; no global5M index scan or rebuild. Tenant artifacts additionally hash files below256MiB. Global catalogue uses estimated count; no full document digest.',
        'protected_temp':'Preexisting Part2I temp directory was not touched. New fixture cleanup belongs to owned mongod TemporaryDirectory only.'}
    write('preservation',preserved);assert preserved['result']=='PASS',preserved
    write('regression',{'result':'PARTIAL','baseline':totals(bg),'final':totals(fg),'preexisting_backend_failures':bfail,'new_backend_failures':new,
        'frontend':ft,'build':'PASS','lint_exit':0,'new_lint_errors':0,'new_lint_warnings':sorted(set(warnings)-set(bwarnings)),
        'preservation':'PASS','frozen_2G_2H_manual_build_and_recovery_tests':'Passed unmodified in final product groups.'})
    failure=[{'case':c['name'],'kind':'Actual native process termination','evidence':c,'result':'Native job/pointer unchanged by restart; no telemetry recovery.'} for c in native['real_process_crashes']]
    failure.extend([{'case':c,'kind':kind,'evidence':'tests/institution_v2k/test_telemetry.py; focused.xml; final institution_v2k XML','result':status} for c,kind,status in [
        ('telemetry_timeout','Actual auth-enabled mongod failCommand blockConnection1200ms vs500ms client deadline','PASS'),
        ('permission_loss','Actual revokeRolesFromUser then pulse; server code13','PASS'),
        ('expired_connection','Actual failCommand closeConnection','PASS'),
        ('duplicate_instance','Actual UUID collision/different boot against Mongo CAS','PASS'),
        ('invalid_document','Actual strict validator oversized BSON and9-entry array rejection code121','PASS'),
        ('old_late_pulse','Actual old epoch pulse matched_count0 after restart','PASS'),
        ('clock_skew','Controlled future/rollback record and observer clock test; no OS clock mutation','PASS_FIXTURE'),
        ('heartbeat_without_progress','Actual native ten-second renewal during held real Search embedding','PASS'),
        ('ownership_and_expiry','Actual Mongo claim-context mismatch; expired lease; no auxiliary progress accepted','PASS_FIXTURE'),
        ('missing_malformed_legacy','Actual missing/malformed auxiliary records remain UNKNOWN/unavailable','PASS'),
        ('operator_read_failure','Actual wrong password CLI; sanitized error and nonzero exit','PASS'),
        ('unexpected_and_disk_error','Injected Python exception/OSError at auxiliary call boundary, not physical disk exhaustion','PASS_SIMULATED_ONLY'),
        ('physical_disk_exhaustion','No physical volume exhaustion performed','NOT_QUALIFIED'),
        ('whole_database_outage','Connection failure/timeout tested; no production outage or mandatory native DB failure masked','NOT_QUALIFIED_DEPLOYMENT')]])
    write('failure_injection',{'cases':failure,'supplement':supp,'actual_auxiliary_failure_during_native_builds':native_faults,'no_production_faults':True})
    life=read('native_lifecycle');before=read('native_paired_false');after=read('native_paired_true')
    emb=[e for e in life['events'] if e['stage']=='EMBEDDING' and e.get('progress')]
    separation=any(x['heartbeat_at']!=y['heartbeat_at'] and x['progress_seq']==y['progress_seq'] and x['progress'][0]['last_progress_observed_at']==y['progress'][0]['last_progress_observed_at'] for x in emb for y in emb)
    assert separation
    overhead={'qualification':'Single equivalent local native pair; no production performance conclusion. Cached real MiniLM and fresh private tenant fixtures.',
        'candidate_pulse_seconds':10,'candidate_idle_writes_per_minute':6,'active_poll_seconds':1,'max_document_bytes':16384,'max_progress_per_instance':8,
        'idle_before':before['idle'],'idle_after':after['idle'],
        'idle_cpu_delta_ms':after['idle']['cpu_ms']-before['idle']['cpu_ms'],
        'idle_cpu_delta_one_core_percent':(after['idle']['cpu_ms']-before['idle']['cpu_ms'])/(after['idle']['seconds']*1000)*100,
        'baseline_auxiliary_note':'Before worker has no telemetry Agent; any previous stopped auxiliary record visible in its idle snapshot is retained history, not a baseline pulse.',
        'idle_rss_delta_difference_bytes':after['idle']['rss_increase_bytes']-before['idle']['rss_increase_bytes'],
        'build_pairs':[{'target':b['target'],'before':b,'after':a} for b,a in zip(before['builds'],after['builds'])],
        'observed_actor_counts':after.get('telemetry_metrics',{}),'observed_actor_latencies_ms':{kind:__import__('scripts.institution_v2k_performance',fromlist=['stats']).stats([l['ms'] for l in after.get('latencies',[]) if l['kind']==kind]) for kind in {l['kind'] for l in after.get('latencies',[])}},
        'counts_scope':'Native child metrics sampled before adapter shutdown; best-effort stop write is additional. Startup CAS and immediate pulse are explicit lifecycle overhead, separate from steady periodic rate.',
        'idle_native_32s':life['idle'],'native_heartbeat_separation':separation,
        'diagnostic_scenarios':[{'scenario':s['scenario'],'before_median_ms':s['pairs'][0]['read_ms']['median'],'after_median_ms':s['pairs'][1]['read_ms']['median'],
                               'before_p95_ms':s['pairs'][0]['read_ms']['p95'],'after_p95_ms':s['pairs'][1]['read_ms']['p95'],
                               'bson_bytes':s['auxiliary_storage_bson_bytes'],'native_reader_documents_examined':s['native_reader_documents_examined'],
                               'auxiliary_documents_examined':s['auxiliary_documents_examined'],'after_max_output_bytes':s['pairs'][1]['max_output_bytes']} for s in perf['scenarios']],
        'write_latency_ms':perf['auxiliary_write_ms'],'limits':['RSS deltas are snapshots, not guaranteed allocation peaks.','Harness-owned process CPU/RSS includes native model and monitoring.','No GPU used.','No long-run disk, network, DB CPU or production workload SLO.','20 read samples per side per scenario; one native build pair per target.']}
    write('resource_overhead',overhead)
    write('private_library_security',{'result':'PASS_FIXTURES_AND_PRESERVATION','private_modes':['PRIVATE_INSTITUTION','PRIVATE_CODE'],
        'actual_native_http_checks':life['security'],'operator_roles_independent':True,'actual_operator_write_denied_code':native['operator_write_denied_code'],
        'focused_auth_role_matrix':['OUTSIDER','GENERAL_USER','LIBRARIAN','LIBRARY_ADMIN','PLATFORM_ADMIN'],
        'telemetry_catalogue_content_fields':[],'no_new_Staff_or_Platform_privilege':True,'frozen_source_preservation':preserved['result'],
        'limitations':'No new tenant telemetry API exists. CLI requires infrastructure read principal. Production credentials/code attestation unqualified.'})
    write('multi_tenant_isolation',{'result':'PASS_FIXTURES_AND_PRESERVATION','actual_A_Search_B_KG_C_queued_restart':[c for c in supp['recovery'] if 'library_c_before' in c],
        'cross_library_progress_query_test':'Current job/fence/target/library exact matching, canonical IDs; foreign output absent.',
        'Staff_switching':'Frozen frontend library/intelligence and workspace tests passed; no new browser/UI infrastructure display.',
        'legacy_stale_recovery_safety':'Focused stale/recovery/old lease cases plus unmodified native recovery suites.',
        'serial_execution':'Actual resident native workers; source unchanged. No distributed claim or concurrent model execution introduced.'})
    design_reports()
    qa={'PART_2K_RESULT':'PARTIAL','PART_2J_PRESERVED':'YES','WORKER_INSTANCE_IDENTITY_IMPLEMENTED':'PROTOTYPE_ONLY',
        'IDLE_WORKER_TELEMETRY':'PASS','ACTIVE_WORKER_TELEMETRY':'PASS','RESTART_IDENTITY':'PASS','INDEPENDENT_PROCESS_VERIFICATION':'NO',
        'HEARTBEAT_PROGRESS_SEPARATED':'YES','LAST_PROGRESS_TIMESTAMP':'PROTOTYPE_ONLY','LEGACY_JOBS_SAFE':'YES','OLD_INSTANCE_FENCED':'YES',
        'TELEMETRY_FAILURE_ISOLATED':'YES','OPERATOR_AUTHENTICATION_PRESERVED':'YES','OPERATOR_READ_ONLY':'YES','PRIVATE_LIBRARY_ISOLATION':'PASS',
        'CROSS_TENANT_TELEMETRY_LEAK':'NO','TELEMETRY_STORAGE_BOUNDED':'YES','NATIVE_WORKER_TEST':'PASS',
        'TELEMETRY_PERFORMANCE':f"6 idle writes/min candidate; write median {perf['auxiliary_write_ms']['median']:.2f}ms/p95 {perf['auxiliary_write_ms']['p95']:.2f}ms; 6 paired history scenarios,240 reads; native pairs measured; no production SLO.",
        'PRODUCTION_TELEMETRY_ENABLED':'NO','AUTOMATIC_REBUILD_IMPLEMENTED':'NO','AUTOMATIC_RECOVERY_IMPLEMENTED':'NO','JOB_CANCELLATION_IMPLEMENTED':'NO',
        'DISTRIBUTED_WORKERS_IMPLEMENTED':'NO','GLOBAL_HNSW_REBUILT':'NO','GLOBAL_KG_REBUILT':'NO','SEARCH_RANKING_CHANGED':'NO',
        'RECOMMENDATION_RANKING_CHANGED':'NO','QWEN_CHANGED':'NO','ASSISTANT_ROUTER_CHANGED':'NO',
        'BACKEND_TESTS':f"{totals(fg)['passed']} passed / {totals(fg)['failed']} failed / {totals(fg)['skipped']} skipped",
        'PREEXISTING_BACKEND_FAILURES':2,'NEW_BACKEND_FAILURES':0,'FRONTEND_TESTS':f"{ft['pass']} passed / {ft['fail']} failed / {ft['skipped']} skipped",
        'PRODUCTION_BUILD':'PASS','FINAL_RECOMMENDED_NEXT_PHASE':'Review and qualify a per-instance native observer seam and deployment-owned restricted writer principal.'}
    write('qa_summary',qa)
    sections=[('A','FINAL PASS / PARTIAL / FAIL','PARTIAL. Isolated prototype validated; production integration remains gated; two preexisting backend failures remain.'),
      ('B','PART 2K EXECUTIVE SUMMARY','Independent self-report identity/pulse, durable post-read progress observation, bounded authenticated storage and a fixture-only operator supplement. No product/runtime/UI source edits.'),
      ('C','BASELINE',f"{len(baseline['source_sha256'])} existing sources and {len(baseline['frozen_reports_sha256'])} frozen I/J reports captured; TEST151 books/150 holdings/5 assets; global estimated5,000,000. See baseline.json."),
      ('D','EXISTING WORKER LIFECYCLE','Exact native call graph in architecture.md. Serial daemon; two-second idle wait;90-second lease; ten-second renewal; close does not join.'),
      ('E','WORKER IDENTITY DESIGN','UUID4, boot nonce digest and epoch CAS; no PID identity. See worker_identity.md.'),
      ('F','INDEPENDENT HEARTBEAT ARCHITECTURE','Separate bounded Agent connection/thread; six candidate idle pulse writes/minute. Never renews native job lease.'),
      ('G','IDLE WORKER OBSERVATION','Actual32-second idle interval produced four pulses; supplement verified return to idle and genuine idle crash/restart.'),
      ('H','ACTIVE WORKER OBSERVATION','Actual cached offline MiniLM/FAISS Search and native KG completed with publication acknowledgement; stage holds disclosed.'),
      ('I','PROGRESS TIMESTAMP SEMANTICS','Accepted state is read first; server observation time follows. Identical tuple and native heartbeat do not advance progress. Not exact commit time. See progress_contract.md.'),
      ('J','TELEMETRY STORAGE','One preallocated document, current/previous, eight entries each,16384-byte server cap; no insertion/deletion grants. See storage_design.md.'),
      ('K','TELEMETRY AUTHENTICATION','Actual auth-enabled Mongo enforces separate custom writer and unchanged DB-local read operator. No production provisioning.'),
      ('L','FENCING AND RACE SAFETY','Late instance rejected; native owner/fence/tuple revalidated. Native correctness byte-preserved. Multi-read races remain a production qualification limit.'),
      ('M','LEGACY COMPATIBILITY','Missing/legacy/malformed observations stay UNKNOWN; no backfill or migration.'),
      ('N','WORKER RESTART','Fresh identity/epoch; old native lease persists; repeated actual child restarts do not recover or rewrite old jobs.'),
      ('O','CRASH / FAILURE INJECTION','Six primary process crash boundaries plus idle and last-good supplements; real Mongo timeout/permission/connection loss. Physical disk exhaustion not qualified. See failure_injection.json.'),
      ('P','OPERATOR CLI INTEGRATION','Original J CLI unchanged. New separate prototype supplement is authenticated, scoped, bounded and read-only.'),
      ('Q','HEALTH CLASSIFICATION','RECENTLY_OBSERVED / STALE / UNKNOWN / STOPPED_REPORTED. No HEALTHY or PROCESS_VERIFIED_ALIVE. Stalled=NOT_DETERMINED.'),
      ('R','PRIVATE LIBRARY SECURITY','Actual private library fixtures and JWT identities, independent infrastructure auth, no catalogue/content/member data in telemetry. See private_library_security.json.'),
      ('S','MULTI-TENANT ISOLATION','Actual A Search, B KG crash and C queued Search; restart executes only previously requested C while B remains unresolved. Scoped output excludes B from A/C. Frozen Staff switching preserved.'),
      ('T','RESOURCE OVERHEAD',f"Native idle CPU delta {overhead['idle_cpu_delta_ms']:.2f}ms over22s; RSS-delta difference {overhead['idle_rss_delta_difference_bytes']}bytes, snapshot limitation. Singleton lookup examines1 document."),
      ('U','PERFORMANCE MEASUREMENTS','240 paired bounded read samples across0/1queued/1active/10/100/1000history;20 auxiliary writes; native idle/Search/KG pairs. See performance.json and resource_overhead.json.'),
      ('V','NATIVE LIFECYCLE QUALIFICATION','PASS in isolated fixtures; not deployment-qualified. Native models/builders, actual resident thread, real JWT routes, os._exit and authenticated CLI executed.'),
      ('W','BACKEND TESTS',qa['BACKEND_TESTS']+'; '+str(next(g for g in fg if g['group']=='institution_v2k')['passed'])+' focused prototype tests passed.'),
      ('X','FRONTEND TESTS',qa['FRONTEND_TESTS']+'; production build and lint exit0; existing warnings retained.'),
      ('Y','REGRESSION','Exactly two preexisting failures, zero new failures. Protected RAG hash and lexical fallback tests remain enabled/unmodified. See regression.json.'),
      ('Z','GLOBAL PRESERVATION','PASS: baseline source/report hashes, tenant collection digests, TEST data/pointers, tenant artifact hashes and personal logical state unchanged. Large global artifacts and protected filesystem entries match baseline size/mtime metadata; global catalogue estimated count unchanged, no full scan. See preservation.json.'),
      ('AA','EXACT FILES CHANGED','All Part2K additions with SHA256 and categories are in changed_files.json. Existing1590 source files unchanged. No Git commit.'),
      ('AB','REPORTS CREATED','All27 requested reports plus raw logs/XML/native snapshots, QA/acceptance and a task-only review package. See changed_files.json/package manifest.'),
      ('AC','IMPLEMENTATION / QUALIFICATION DECISION','PROTOTYPE_ONLY. Native lifecycle seam, deployment secret ownership, exact transition/race semantics and representative operational gates are incomplete. See implementation_decision.md.'),
      ('AD','REMAINING LIMITATIONS','No OS/supervisor proof, no trusted production CPU/RAM/GPU attribution, sampled progress can miss events, two retained instances only, one build pair per target, no physical disk exhaustion/deployment SLO.'),
      ('AE','IMPROVEMENT REVIEW','Evidence distinguishes pulses, lease renewals, progress observations and publication; remaining observer/deployment gates are explicit. See improvement_review.md.'),
      ('AF','RECOMMENDED NEXT PHASE',qa['FINAL_RECOMMENDED_NEXT_PHASE']+' Stop after2K; no later phase implemented.')]
    md('completion','\n\n'.join('## '+a+'. '+title+'\n\n'+body for a,title,body in sections)+'\n\n## FINAL QA SUMMARY\n\n```text\n'+'\n'.join(f'{k}: {v}' for k,v in qa.items())+'\n```\n\nKnown failures:\n\n'+'\n'.join('- '+s for s in ffail))
    attachment=Path('C:/Users/balak/.codex/attachments/c3fa18c7-4e44-4395-bd5a-623cf45f651d/Pasted text.txt').read_text(encoding='utf8')
    criteria=attachment.split('PART AF — ACCEPTANCE CRITERIA')[1].split('FINAL CODEX RESPONSE')[0]
    items=re.findall(r'(\d+)\.\s+(.*?)(?=\n\s*\d+\.|\nIf telemetry)',criteria,re.S)
    prototype={3,4,5,6,7,9,10,11,12,13,15,16,17,27,28,29,30,53,54}
    acceptance=[{'criterion':int(n),'requirement':' '.join(t.split()),'status':'PROTOTYPE_ONLY' if int(n) in prototype else 'PASS',
         'evidence':'completion.md corresponding A–AF section; focused/final XML, native_validation.json, native_supplement.json, performance.json and preservation.json. Production gates remain unqualified.'} for n,t in items]
    assert len(acceptance)==56
    write('acceptance',{'overall':'PARTIAL','criteria':acceptance,'production_integration':'NOT_QUALIFIED; not enabled'})
    paths=sorted({p for p in [*R.glob('institution_v2k_*'),*(ROOT/'scripts').glob('*institution_v2k*.py'),
        *(ROOT/'tests/institution_v2k').rglob('*.py'),*(ROOT/'scratch/institution_v2k_telemetry').rglob('*.py')]
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.zip'})
    # Avoid scanning/packaging any historical user work; paths must be task-specific.
    inventory=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p),
                'category':'report/evidence' if p.parent==R else 'isolated prototype' if 'scratch' in p.parts else 'focused test' if 'tests' in p.parts else 'task harness'} for p in paths if p.name not in ['institution_v2k_changed_files.json','institution_v2k_package_manifest.json']]
    write('changed_files',{'existing_source_modifications':source_bad,'new_2K_files':inventory,'preexisting_2I_change_preserved':True,
        'self_and_delivery_files':[{'path':'reports/institution_v2k_changed_files.json','note':'Self hash omitted to avoid recursion.'},
            {'path':'reports/institution_v2k_package.zip','note':'Delivery archive hash in package_manifest.json; archive does not include itself.'},
            {'path':'reports/institution_v2k_package_manifest.json','note':'External delivery checksum manifest, written after archive; no self hash.'}],
        'scope':'Only Part2K paths; preexisting untracked/user work is excluded. Compiler caches/dist build output are generated/ignored.'})
    package=R/'institution_v2k_package.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            if p.exists() and p.name!='institution_v2k_package_manifest.json':z.write(p,p.relative_to(ROOT).as_posix())
        z.write(R/'institution_v2k_changed_files.json','reports/institution_v2k_changed_files.json') if R/'institution_v2k_changed_files.json' not in paths else None
    write('package_manifest',{'package':package.name,'bytes':package.stat().st_size,'sha256':sha(package),
        'entries':len(zipfile.ZipFile(package).namelist()),'scope':'2K-only review sources/tests/harness/reports. No credentials, models, catalogue data or artifacts.'})
    print(json.dumps({'result':'PARTIAL','backend':totals(fg),'frontend':ft,'preservation':preserved['result'],'reports':len(list(R.glob('institution_v2k_*'))),'package_bytes':package.stat().st_size}))


if __name__=='__main__':
    if '--design' in sys.argv:design_reports()
    else:finalize()
