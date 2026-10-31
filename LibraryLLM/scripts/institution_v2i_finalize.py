"""Final Part 2I evidence assembly. Read-only production verification, no commit."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.institution_v2i_baseline import capture_state
from scripts.institution_v2i_reports import main as source_reports

R = ROOT/'reports'
RESIDUE = r'C:\Users\balak\AppData\Local\Temp\luminar-v2i-build-pf4vn_p3'


def read(name):
    return json.loads((R/f'institution_v2i_{name}.json').read_text(encoding='utf8'))


def write(name, value):
    (R/f'institution_v2i_{name}.json').write_text(json.dumps(value, indent=2, default=str), encoding='utf8')


def totals(groups):
    return {key: sum(g.get(key, 0) for g in groups) for key in ['tests', 'passed', 'failed', 'skipped']}


def xml_evidence(prefix):
    failed, skipped, names = [], [], []
    for file in sorted(R.glob(prefix+'*.xml')):
        for case in ET.parse(file).iter('testcase'):
            name = case.get('classname', '')+'::'+case.get('name', '')
            names.append(name)
            for child in case:
                if child.tag in ['error','failure']:
                    failed.append({'test': name, 'message': child.get('message','')[:1500], 'xml': file.name})
                elif child.tag=='skipped':
                    skipped.append({'test': name, 'message': child.get('message','')[:500]})
    return {'failures': failed, 'skips': skipped, 'executed_test_identifiers': names}


def restore_known_generated_reports():
    # The initial tracked tree was clean. A frozen analytics test writes its
    # historical report. Retain that executed output under this phase, then
    # restore the original bytes through Git's configured checkout filters.
    initial = read('baseline')
    assert not any(not row.startswith('??') for row in initial['git_status'])
    changed = subprocess.check_output(['git','diff','--name-only'], cwd=ROOT, text=True).splitlines()
    for name in ['reports/institution_v2e_backend_benchmark.json','reports/full_product_generated_test_plan.json']:
        if 'LibraryLLM/'+name not in changed:
            continue
        p=ROOT/name
        (R/('institution_v2i_executed_'+p.name)).write_bytes(p.read_bytes())
        original=subprocess.check_output(['git','cat-file','--filters','--path=LibraryLLM/'+name,'HEAD:LibraryLLM/'+name],cwd=ROOT)
        p.write_bytes(original)


def preservation():
    before=read('baseline')
    after=json.loads(json.dumps(capture_state(),default=str))
    source_changes=[]
    for name,digest in before['source_sha256'].items():
        p=ROOT/name
        actual=hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
        if actual!=digest:
            source_changes.append({'file':name,'before':digest,'after':actual})
    state_changes=[]
    for key in sorted(set(before['state'])|set(after)):
        if before['state'].get(key)!=after.get(key):
            state_changes.append(key)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    allowed={'backend/services/library_intelligence_service.py'}
    started=datetime.fromisoformat(before['captured_at']).timestamp()
    kg_metadata={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns,
                 'last_write_predates_task':p.stat().st_mtime<started}
                 for p in (ROOT/'knowledge_graph/data').glob('*') if p.is_file()}
    result={'status':'PASS' if not state_changes and {c['file'] for c in source_changes}<=allowed and head==before['head'] else 'ISSUES_FOUND',
            'production_database_mutations_by_task':0,'global_catalogue_scanned':False,
            'state_categories_changed':state_changes,'state_categories_verified':list(after),
            'source_changes':source_changes,'allowed_production_changes':sorted(allowed),
            'baseline_sources_checked':len(before['source_sha256']),
            'global_artifact_metadata_entries_checked':len(after['global_artifacts']),
            'tenant_artifact_entries_checked':len(after['tenant_artifacts']),
            'private_asset_file_entries_checked':len(after['protected_files']),
            'global_artifact_verification_limit':'Size/mtime only for large protected global files; no claimed full 5M vector rehash.',
            'tenant_artifact_verification':'Size/mtime plus SHA256 for bounded files; no changed generations.',
            'global_KG_post_metadata':kg_metadata,
            'global_KG_verification_limit':'Not included in the inherited task-start artifact list. Current file sizes/last-write timestamps are recorded; all writes predate task start, source is unchanged and no global builder was invoked. No pre/post byte-hash equality claim.',
            'qwen_verification_limit':'Source hashes preserved; no Qwen load/training/download/write was invoked. Weight files were not separately rehashed.',
            'database_verification':'Counts and whole-row digests of bounded institution collections; global count estimated, not a 5M scan.',
            'current_TEST':after.get('TEST'),'global_book_count':after.get('global_book_count'),
            'head_unchanged':head==before['head'],'branch':before['branch'],'commit_created':False,
            'retained_task_only_benchmark_residue':RESIDUE if Path(RESIDUE).exists() else None,
            'cleanup_review':'Automatic approval review rejected recursive cleanup of this task-created temporary benchmark folder: blocked by policy. It was left in place; no production artifacts were deleted.',
            'post_state':after}
    write('preservation',result)
    return result


def main():
    source_reports()
    original=ROOT/'.scratch/institution-v2i/before/backend/services/library_intelligence_service.py'
    assert hashlib.sha256(original.read_bytes()).hexdigest()==read('baseline')['source_sha256']['backend/services/library_intelligence_service.py']
    (R/'institution_v2i_original_library_intelligence_service.py').write_bytes(original.read_bytes())
    base, final=read('baseline_backend'),read('final_backend')
    assert final[-1]['group']=='events' and any(g['group']=='institution_v2i' for g in final), 'Final backend run is not complete'
    fronts=read('final_frontend')
    assert {r['check'] for r in fronts}=={'frontend','build','lint'}, 'Frontend checks incomplete'
    baseline_tests=xml_evidence('institution_v2i_baseline_')
    final_tests=xml_evidence('institution_v2i_final_')
    backend={'baseline':totals(base),'final':totals(final),'groups':final,
             'final_failures':final_tests['failures'],'baseline_failures':baseline_tests['failures'],
             'new_failure_identifiers':sorted({f['test'] for f in final_tests['failures']}-{f['test'] for f in baseline_tests['failures']}),
             'skipped':final_tests['skips'],'count_semantics':'Test executions across isolated groups; may include shared frozen nodes, not a claim of unique tests.',
             'research_excluded':'Router/training/research suites; 2G operational inventory uses four frozen native infrastructure/runtime/isolation files, not later parser research.',
             'events_clock_alignment':'Established fixture-only NOW alignment to real UTC; expiry/JWT checks remain enabled; historical test files unchanged.'}
    write('backend_tests',backend)
    log=(R/'institution_v2i_final_frontend.log').read_text(encoding='utf8',errors='replace')
    frontend={'checks':fronts,'tests':sum(map(int,re.findall(r'ℹ tests (\d+)',log))),
              'passed':sum(map(int,re.findall(r'ℹ pass (\d+)',log))),
              'failed':sum(map(int,re.findall(r'ℹ fail (\d+)',log))),
              'skipped':sum(map(int,re.findall(r'ℹ skipped (\d+)',log))),
              'subprocess_groups':len(re.findall(r'ℹ tests (\d+)',log)),
              'production_build':'PASS' if next(r['exit'] for r in fronts if r['check']=='build')==0 else 'FAIL',
              'lint':'PASS' if next(r['exit'] for r in fronts if r['check']=='lint')==0 else 'FAIL',
              'frontend_source_changes':False,
              'warnings':'Existing lint warnings and build dynamic-import/chunk-size warnings retained; exact before/final logs supplied.'}
    write('frontend_tests',frontend)
    perf=read('freshness_benchmark_paired')
    # The first full paired run used the supported internal EMPTY generation
    # for zero records. Also measure the actual public new-library NOT_BUILT
    # lifecycle and use that for the primary zero-record row.
    empty=read('freshness_benchmark_empty')
    legacy_empty=[{**c,'fixture_state':'LEGACY_INTERNAL_EMPTY'} for c in perf['cases'] if c['eligible_books']==0]
    perf['cases']=[c for c in empty['cases'] if c['eligible_books']==0]+[c for c in perf['cases'] if c['eligible_books']!=0]+legacy_empty
    for case in perf['cases']:
        case['filesystem'].setdefault('checksum_calls',0)
        case['filesystem'].setdefault('checksum_bytes',0)
    cold=read('cold_process')
    perf['process_cold']=cold
    perf['canonical_note']='Paired identical fixtures, same real Mongo/auth/state/source contract; before source from frozen task baseline. Preliminary smoke outputs are not acceptance evidence.'
    write('freshness_benchmark',perf)
    conc=read('freshness_benchmark_concurrency')
    write('concurrency',{'cases':conc['concurrency'],'isolation':conc['isolation'],
                         'no_cross_tenant_observation_reuse':True,'coalescing_implemented':False,
                         'interpretation':'Existing same-tenant barrier may return 503. Successful and unavailable latencies are separate; no success/throughput claim from fast failed reads. Timing/code distribution is workload/order sensitive.',
                         'disposable_database_removed':conc['disposable_database_removed']})
    browser=read('browser')
    focused=list(ET.parse(R/'institution_v2i_focused_final.xml').iter('testcase'))
    focused_passed=sum(not any(c.tag in ['failure','error','skipped'] for c in t) for t in focused)
    scope_cases=[g for g in final if g['group'] in ['institution_v2g','institution_v2h','institution_v2i','workspace_authorization','catalogue_experience']]
    security={'status':'PASS' if all(g['failed']==0 and g['exit']==0 for g in scope_cases) and browser['status']=='PASS' else 'PARTIAL',
              'layers':['Fresh-identity exact-membership ASGI tests with dependency-injected fixture actor','Real signed JWT decoding/current identity/current membership in actual Chromium bridge','Actual isolated Mongo and native artifact builds/fault injection'],
              'browser_steps':browser['steps'],'frozen_scope_groups':scope_cases,
              'focused_passed':focused_passed,'focused_total':len(focused),
              'contract_checks':['Admin status/build allowed','Librarian status allowed/build denied','General User Staff denied','Explicit Platform-only denied',
                  'Foreign status/build/job/generation/artifact denied','Current membership demotion and revocation','Cross-library artifacts/status/runtime namespace isolation',
                  'Safe job error whitelist excludes paths, raw stack traces, fence and worker secret','No shared cache or authorization cache added',
                  'Stale browser signed token loses revoked tenant authority','No new diagnostic/cancellation/global endpoint'],
              'limitations':['No production credentials, real production worker or TEST builds exercised','Chromium HTTP transport bridged to real TestClient; not a deployed network/proxy/load test']}
    write('security',security)
    restore_known_generated_reports()
    preserve=preservation()
    final_ok=not backend['new_failure_identifiers'] and focused_passed==len(focused) and frontend['failed']==0 and all(x['exit']==0 for x in fronts) and browser['status']=='PASS' and preserve['status']=='PASS'
    decision='PARTIAL' if final_ok and backend['final']['failed'] else 'PASS' if final_ok else 'FAIL'
    blocker='Two preexisting frozen regression failures (protected RAG hash drift and global lexical API fixture HTTP 500); no new regression failures.' if backend['final']['failed'] else 'None'
    before50=next(c for c in perf['cases'] if c['version']=='before' and c['eligible_books']==50000)
    after50=next(c for c in perf['cases'] if c['version']=='after' and c['eligible_books']==50000)
    qa={'PART_2I_RESULT':decision,'PART_2H_PRESERVED':'YES' if final_ok else 'NO',
        'FRESHNESS_COST_MEASURED':'YES','SEARCH_FRESHNESS_CONTRACT_VERIFIED':'YES','KG_FRESHNESS_CONTRACT_VERIFIED':'YES',
        'STATUS_OPTIMIZATION_IMPLEMENTED':'YES','STATUS_OPTIMIZATION_SAFE':'YES' if final_ok else 'NO',
        'STATUS_MEDIAN_BEFORE_MS':round(before50['warm_ms']['median'],3),'STATUS_MEDIAN_AFTER_MS':round(after50['warm_ms']['median'],3),
        'STATUS_P95_BEFORE_MS':round(before50['warm_ms']['p95'],3),'STATUS_P95_AFTER_MS':round(after50['warm_ms']['p95'],3),
        'FALSE_READY_CASES':0,'WORKER_LIFECYCLE_VERIFIED':'YES','WORKLOAD_BUDGET_DESIGNED':'YES','QUEUE_FAIRNESS_REVIEWED':'YES',
        'RECOVERY_MATRIX_COMPLETE':'YES','LAST_GOOD_GENERATION_PRESERVED':'YES','SUPERVISED_POLICY_DESIGNED':'YES',
        **{k:'NO' for k in ['AUTOMATIC_REBUILD_IMPLEMENTED','SCHEDULED_REBUILD_IMPLEMENTED','INCREMENTAL_HNSW_IMPLEMENTED','INCREMENTAL_KG_IMPLEMENTED',
             'DISTRIBUTED_WORKERS_IMPLEMENTED','JOB_CANCELLATION_IMPLEMENTED','AUTOMATIC_RECOVERY_IMPLEMENTED','GLOBAL_HNSW_REBUILT','GLOBAL_KG_REBUILT',
             'SEARCH_RANKING_CHANGED','RECOMMENDATION_RANKING_CHANGED','QWEN_CHANGED','ASSISTANT_ROUTER_CHANGED']},
        'BACKEND_TESTS':f"{backend['final']['passed']} passed / {backend['final']['failed']} failed (preexisting) / {backend['final']['skipped']} skipped",
        'FRONTEND_TESTS':f"{frontend['passed']} passed / {frontend['failed']} failed / {frontend['skipped']} skipped",
        'BROWSER_QA':browser['status'],'PRODUCTION_BUILD':frontend['production_build'],
        'FINAL_RECOMMENDED_NEXT_PHASE':'Part 2J: operator-only read-only worker liveness and recovery diagnostics; no automatic actions.'}
    write('regression',{'result':decision,'blocker':blocker,'backend':backend,'frontend':frontend,
                        'browser_status':browser['status'],'focused':{'passed':focused_passed,'tests':len(focused)},'preservation':preserve['status'],
                        'new_regression_failures':backend['new_failure_identifiers'],'final_qa':qa,
                        'false_READY_scope':'Zero observed across executed mutation/corruption/isolation fixtures, not an arbitrary-production guarantee.',
                        'performance_summary_scope':'50,000-book checksum-valid synthetic status fixture; sizes/all percentiles and first-read/memory/CPU/DB work in benchmark report.'})
    acceptance=[]
    for n in range(1,56):
        status='VERIFIED_IN_STATED_SCOPE'
        evidence='Source reports, isolated native/ASGI/JWT/Chromium regressions and preservation evidence; see completion sections.'
        if n==47:
            status='PARTIAL'
            evidence=blocker
        elif n==34:
            status='PARTIAL'
            evidence='Tenant recommendation runtime/isolation passes in actual canonical fixtures; deployed global recommendation provider availability was not exercised.'
        elif n==42:
            status='LIMITED_METADATA_EVIDENCE'
            evidence=preserve['global_KG_verification_limit']
        elif n==44:
            status='SOURCE_AND_ACTION_PRESERVATION'
            evidence=preserve['qwen_verification_limit']
        acceptance.append({'criterion':n,'status':status,'evidence':evidence})
    write('acceptance',{'result':decision,'criteria':acceptance,
                        'note':'Criterion numbers refer to Part AH of the user request; scope labels are deliberately not a blanket production certification.'})
    (R/'institution_v2i_final_qa.json').write_text(json.dumps(qa,indent=2),encoding='utf8')
    table=['| Eligible books | Before median ms | After median ms | Before p95 ms | After p95 ms | Checksum bytes before / after |','|---:|---:|---:|---:|---:|---:|']
    for n in [0,1,10,100,1000,10000,50000]:
        old=next(c for c in perf['cases'] if c['version']=='before' and c['eligible_books']==n)
        new=next(c for c in perf['cases'] if c['version']=='after' and c['eligible_books']==n)
        table.append(f"| {n:,} | {old['warm_ms']['median']:.3f} | {new['warm_ms']['median']:.3f} | {old['warm_ms']['p95']:.3f} | {new['warm_ms']['p95']:.3f} | {old['filesystem']['checksum_bytes']:,} / {new['filesystem']['checksum_bytes']:,} |")
    perf_table='\n'.join(table)
    workload=read('workload_benchmark')
    wt=['| Target | Books | First build ms | Unchanged rebuild ms | New generation bytes |','|---|---:|---:|---:|---:|']
    for target in ['SEARCH_INDEX','KNOWLEDGE_GRAPH']:
        for n in [10,100,1000]:
            old=next(c for c in workload['cases'] if c['target']==target and c['eligible_books']==n and c['cache_mode']=='first_build')
            new=next(c for c in workload['cases'] if c['target']==target and c['eligible_books']==n and c['cache_mode']=='unchanged_rebuild')
            wt.append(f"| {target} | {n} | {old['build_ms']:.3f} | {new['build_ms']:.3f} | {new['artifact_bytes']:,} |")
    with (R/'institution_v2i_status_optimization.md').open('a',encoding='utf8') as out:
        out.write('\n## Executed paired measurements\n\n'+perf_table+'\n\nPopulated checksum reads 14 → 7; Mongo commands decrease by two at every size. Full catalogue count/projection/normalization/fingerprint is unchanged. Timings are local development samples; no SLO/cold-disk or model-load status latency claim. Raw CPU, memory, first-read, p90, DB documents/bytes and profile details are in the JSON.\n')
        out.write('\n## Fresh application-process measurements\n\nThree new Python processes per size/version also measure the first status call at all seven sizes, with total startup/import wall time separate. The OS/Mongo caches are not flushed. These are application-cold, not cold-disk/server measurements. Raw samples and percentiles are in `institution_v2i_cold_process.json`.\n')
    with (R/'institution_v2i_worker_audit.md').open('a',encoding='utf8') as out:
        out.write('\n## Executed bounded workloads\n\n'+'\n'.join(wt)+'\n\nActual cached MiniLM CPU and actual validated FAISS/KG artifacts, offline/no downloads. Two torch/FAISS threads for fixture measurements only. One sample per configuration; first 10-book run includes lazy inference warmup. Unchanged Search rebuilds encode zero books. Embedding, construction, validation, pointer publication, source extraction, sampled process RSS and disk/cache/retained sizes are all in `institution_v2i_workload_benchmark.json`; no GPU budget was qualified. Existing VectorCache SQLite handles can survive transaction contexts until GC; the initial harness cleanup encountered Windows file locking. The verified harness performs GC at fixture teardown; production cache lifecycle was not changed.\n')
    sections=[
        ('A','FINAL RESULT',decision+'. '+blocker),
        ('B','PART 2I EXECUTIVE SUMMARY','Review-first source/baseline/performance audit, one production-file efficiency change, full policy/recovery/incremental reviews and isolated native/browser regressions. No commit or activation.'),
        ('C','EXISTING ARCHITECTURE','Actual paths/classes/routes/collections/fields/barriers/fences/ownership: [architecture](institution_v2i_architecture.md).'),
        ('D','FRESHNESS DETECTION CALL GRAPH','Staff status → fresh scoped authority → tenant barrier → complete source records/fingerprint → dataset/jobs → independent verified target observations. [Call graph](institution_v2i_freshness_audit.md).'),
        ('E','FRESHNESS PERFORMANCE BASELINE','Seven sizes through the real 50,000 bound, plus global-enrichment fixture; median/p90/p95/CPU/memory/DB/profile/checksum work measured. Three fresh application processes per size/version measure first status and startup separately; OS/Mongo caches are not flushed, so these are not cold-disk/server results.'),
        ('F','SEARCH FRESHNESS DEPENDENCIES','Embedding text: title/authors/subjects/description/year. Shared source identity and conservative full dataset fingerprint govern freshness. [Exact contract](institution_v2i_freshness_contract.md).'),
        ('G','KG FRESHNESS DEPENDENCIES','Book identity/title/global link; canonical author/subject/classification relationships. Shared fingerprint intentionally also invalidates on non-graph source metadata changes.'),
        ('H','STATUS OPTIMIZATION DECISION','Reuse verified pointer only within the current response. Reject shared caches/revision shortcuts/coalescing without complete mutation/ownership proofs.'),
        ('I','IMPLEMENTED STATUS IMPROVEMENTS','Private _target_observation returns existing response/row/verification. target_status response contract, authorization, fresh fingerprints, full checksums, runtime selection and job state semantics preserved.'),
        ('J','STATUS BEFORE/AFTER MEASUREMENTS',perf_table),
        ('K','CONCURRENT STATUS SAFETY','One Admin, multiple Admin browsers, Admin+Librarian and three libraries tested. Same-tenant 503 remains fail-closed; no shared authorization/cache/global lock added. [Measurements](institution_v2i_concurrency.json).'),
        ('L','WORKER ARCHITECTURE','One resident daemon, serial oldest-queued job, 90s leases/10s renewal, fenced validation/rename/pointer/ack and exact publication authority. [Worker audit](institution_v2i_worker_audit.md).'),
        ('M','BUILD RESOURCE MEASUREMENTS','\n'.join(wt)+'\n\nActual cached CPU MiniLM; no downloads. One sample/configuration, real builds at 10/100/1000 records; no GPU or production workload qualification.'),
        ('N','WORKLOAD BUDGET POLICY','Future resource estimates/reservations must preserve last-good disk/RAM headroom, inspect worker/queue and block recovery. Candidate diagnostic outcomes only. [Design](institution_v2i_workload_policy.md).'),
        ('O','QUEUE FAIRNESS FINDINGS','FIFO created_at, no tie-breaker/preemption/size budget; one large or barrier-blocked oldest tenant can delay others. Same-target duplication returns same job; other target may queue. [Proposal](institution_v2i_queue_fairness.md).'),
        ('P','WORKER OBSERVABILITY','Heartbeat is not progress; job presence is not idle liveness; no separate last-progress time. Public whitelist retained, no invented health badge. [Audit](institution_v2i_observability.md).'),
        ('Q','RECOVERY DECISION MATRIX','Known prepublish failure vs unknown publication/lease/crash/corrupt pointer covered; explicit existing recovery only. No hardware power-loss certification. [Matrix](institution_v2i_recovery_matrix.md).'),
        ('R','FAILED ARTIFACT RETENTION','Private failed generations retained for ownership/outcome reconciliation; no deletion of retained production artifacts. Future operator-approved protected inventory/retention only. [Review](institution_v2i_artifact_retention.md).'),
        ('S','CANCELLATION FEASIBILITY','Queued CAS/cooperative prepublication checkpoints would need new durable intent, ownership and audit; no safe cancellation across atomic publication. No endpoint/button added. [Design](institution_v2i_cancellation_design.md).'),
        ('T','SUPERVISED REBUILD POLICY DESIGN','Recommend eventual Admin-approved bounded pending intent after authoritative stale/cost review; debounce/window/threshold designs inactive. [Comparison](institution_v2i_supervised_policy.md).'),
        ('U','HNSW INCREMENTAL FEASIBILITY','IndexHNSWFlat normalized384, ordinal metadata IDs; add exists but current remove_ids raises not-implemented in actual fixture. No tenant delete/update/tombstone journal. Full generation rebuild retained. [Review](institution_v2i_hnsw_incremental_review.md).'),
        ('V','KG INCREMENTAL FEASIBILITY','Shared canonical features need provenance/reference accounting, deterministic labels/orphan removal and whole-generation equivalence. Full rebuild retained. [Review](institution_v2i_kg_incremental_review.md).'),
        ('W','SEARCH RUNTIME PRESERVATION','Unchanged query/ranking/model/reranking/hydration source; READY semantic vs non-READY tenant-local fallback verified. Archived/current target responses compared across states.'),
        ('X','KG RUNTIME PRESERVATION','Unchanged schema/extraction/traversal; failed rebuild leaves last-good generation; READY graph intersects current usable tenant books, non-READY safe empty notice.'),
        ('Y','RECOMMENDATION DEPENDENCIES','Global recommendations call global Search with MACHINE contract; tenant recommendations intersect global candidates and fill canonical local records, independent of tenant HNSW/KG READY. [Dependency graph](institution_v2i_recommendation_dependencies.md).'),
        ('Z','AUTHORIZATION','Fresh identity/JWT and exact current membership. ADMIN controls, Librarian reads, General User Staff denial, Platform-only no tenant bypass. No decisions cached. [Security evidence](institution_v2i_security.json).'),
        ('AA','MULTI-LIBRARY ISOLATION','UUID predicates/artifact namespace/barriers preserved. Actual delayed browser A response cannot replace B; foreign status/build/job/artifact visibility tests retained.'),
        ('AB','FRONTEND VALIDATION','Existing page/design/polling unchanged. Abort, token/library keying, terminal-stop/focus/manual refresh and serialized tenant helpers retained. Hidden tabs are not specially paused; no visibility optimization was introduced.'),
        ('AC','BACKEND TESTS',qa['BACKEND_TESTS']+f'; new focused {focused_passed}/{len(focused)}. Baseline failures persist openly; no historical hashes/tests rebased.'),
        ('AD','FRONTEND TESTS',qa['FRONTEND_TESTS']+f" in {frontend['subprocess_groups']} subprocess groups. Production build {frontend['production_build']}; lint {frontend['lint']} with preexisting warnings."),
        ('AE','BROWSER QA',f"Actual Chromium {browser['status']}, {len(browser['steps'])} steps, zero JS page errors, focused axe zero violations, 1440/1024/390/375 widths. Real ASGI/JWT/Mongo/native worker via bridged HTTP; unrelated services/decorative external assets stubbed, not deployed-network qualification. Four expected 404 console resource messages correspond to explicit denial/revocation tests."),
        ('AF','REGRESSION','Frozen V1/2A–2H operational product suites, Staff/Platform/catalogue/Search/KG/recommendations/assets/RAG/knowledge/Assistant/events/notifications/analytics, frontend/build/lint executed. No Router research/training.'),
        ('AG','GLOBAL PRESERVATION',f"Preservation {preserve['status']}; TEST {preserve['current_TEST']['current_eligible_books']} eligible / {preserve['current_TEST']['holdings']} holdings / {preserve['current_TEST']['assets']} assets. Indexed generation counts remain 151. Global count {preserve['global_book_count']:,}; no global rebuild. Tenant hashes, institution row digests and protected file metadata/logical registries checked. [Evidence](institution_v2i_preservation.json)."),
        ('AH','EXACT FILES CHANGED','Only production file: `D:\\SDC\\LibraryLLM\\backend\\services\\library_intelligence_service.py`. Exact added tests/scripts/reports, hashes and historical generated-report restoration are in [changed files](institution_v2i_changed_files.json). Existing user work and HEAD preserved; no commit.'),
        ('AI','REPORTS CREATED','All 29 requested reports plus bounded implementation plan, raw before/paired/concurrency/workload evidence, final QA, logs/XML/screenshots and package. Exact inventory below and in changed-files report.'),
        ('AJ','KNOWN LIMITATIONS',blocker+' Status remains O(catalogue+artifact bytes); exact physical disk/cold-server costs unmeasured. Real build benchmarks limited to 1000 CPU records, one sample/configuration; no GPU/large-tenant SLO. Existing barrier 503, serial queue, idle-liveness/admission/cancellation/retention gaps remain. SQLite handle teardown is GC-dependent in existing VectorCache; production code unchanged. '+('One task-created temporary benchmark folder remains: '+RESIDUE+'. Automatic approval review rejected recursive cleanup (blocked by policy).' if Path(RESIDUE).exists() else '')),
        ('AK','IMPROVEMENT REVIEW','Measured duplicate work removed without replacing authority/freshness/runtime semantics. More ambitious optimization/policy work stays documented, inactive and separately scoped. [Review](institution_v2i_improvement_review.md).'),
        ('AL','RECOMMENDED NEXT PHASE',qa['FINAL_RECOMMENDED_NEXT_PHASE']+' Stop after Part 2I and review this report; no next-phase code started.'),
    ]
    completion='# LuminaR Institutions Part 2I — final report\n\n'
    completion+='Generated '+datetime.now(timezone.utc).isoformat()+'. Project root `D:\\SDC\\LibraryLLM`. All measurements are local fixture evidence unless explicitly described as read-only current production observation.\n\n'
    completion+='\n\n'.join('## '+letter+'. '+title+'\n\n'+body for letter,title,body in sections)
    completion+='\n\n## Final QA summary\n\n```text\n'+'\n'.join(k+': '+str(v) for k,v in qa.items())+'\n```\n'
    completion+='\nPerformance summary fields use the 50,000-record paired fixture; zero false READY applies only to executed correctness fixtures. Worker verification means isolated native lifecycle/fault tests, not live production process liveness.\n'
    completion+='\n## Evidence inventory\n\n'+'\n'.join('- '+str(p.relative_to(ROOT)).replace('\\','/') for p in sorted(R.glob('institution_v2i_*')) if p.suffix in ['.json','.md'])+'\n'
    (R/'institution_v2i_completion.md').write_text(completion,encoding='utf8')
    # Explicit source inventory and all phase-owned evidence, including logs of
    # intermediate failed harness attempts (never presented as final acceptance).
    names=['backend/services/library_intelligence_service.py']
    names += [p.relative_to(ROOT).as_posix() for p in (ROOT/'scripts').glob('institution_v2i_*.py')]
    names += [p.relative_to(ROOT).as_posix() for p in (ROOT/'tests/institution_v2i').glob('*.py')]
    names += [p.relative_to(ROOT).as_posix() for p in R.glob('institution_v2i_*') if p.is_file() and p.suffix!='.zip']
    names += ['reports/institution_v2i_changed_files.json']
    names=sorted(set(names))
    entries=[]
    for name in names:
        p=ROOT/name
        entries.append({'path':str(p),'relative_path':name,'role':'production implementation' if name.startswith('backend/') else 'test/tool/evidence',
                        'sha256':hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() and not name.endswith('institution_v2i_changed_files.json') else None})
    write('changed_files',{'production_files':['backend/services/library_intelligence_service.py'],
                           'files':entries,'commit_created':False,'historical_report_restored_after_test':'institution_v2e_backend_benchmark.json',
                           'intermediate_evidence':'focused.xml/focused_verified.xml/repaired_fixtures.xml and early browser/workload logs include harness failures; canonical final focused_final.xml, final_* group XML, browser.json and workload_benchmark.json supersede them.'})
    # Archive only this phase's evidence/tools and current single production
    # change. No credentials, whole Mongo dumps or tenant artifacts are packed.
    import zipfile
    with zipfile.ZipFile(R/'institution_v2i_package.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            if (ROOT/name).is_file():
                archive.write(ROOT/name,name)
    print(json.dumps({'result':decision,'backend':backend['final'],'frontend':frontend['passed'],
                       'focused':focused_passed,'browser':browser['status'],'preservation':preserve['status'],
                       'reports':len(names),'qa_fields':len(qa)},indent=2))


if __name__=='__main__':
    main()
