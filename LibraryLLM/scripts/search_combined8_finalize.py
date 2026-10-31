"""Consolidate actual Combined V8 outcome, immutable failed primary and preservation."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import json,hashlib,re,subprocess,psutil,xml.etree.ElementTree as ET

R=Path('reports');P='search_combined8_'
PROMPT=Path(r'C:\Users\balak\.codex\attachments\c91fcb7f-cdcc-4c97-a782-94710b9cc056\Pasted text.txt')
def load(n):return json.loads((R/(P+n+'.json')).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(n,d):
    with (R/(P+n+'.json')).open('x',encoding='utf-8') as f:json.dump(d,f,indent=2,ensure_ascii=False)
def verify(files):
    bad=[p for p,h in files.items() if not Path(p).is_file() or sha(p)!=h]
    return dict(entries=len(files),verified=not bad,failures=bad)
def metric(m,pop):return dict(m,population=pop)
def rate(n,d,pop):return dict(numerator=n,denominator=d,percent=100*n/d if d else None,population=pop)


def main():
    fresh=load('independent_metrics');s=fresh['summary'];failure=load('error_analysis')
    assert not fresh['parser_acceptance_passed'] and s['contexts']==205
    assert load('independent_scoring_complete')['primary_attempts']==1
    selected=load('source_freeze');freeze=load('acceptance_freeze')
    old=load('protected_inventory');model=json.loads((R/'search_proof7_model_audit_verified.json').read_text())
    preservation=dict(at_utc=datetime.now(timezone.utc).isoformat(),historical=verify(old['files']),selected_source=verify(selected['files']),
                      primary_freeze=verify(freeze['files']),cached_model=verify({str(Path(model['path'])/p):v['sha256'] for p,v in model['files'].items()}),
                      tracked_diff=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines(),
                      staged_diff=subprocess.check_output(['git','diff','--cached','--name-only'],text=True).splitlines(),
                      Mongo_mutations=0,production_activation=False,heldout_evaluations=0,
                      primary_predictions_sha256=sha(R/(P+'independent_predictions.jsonl')),implementation_prompt_sha256=sha(PROMPT))
    assert all(preservation[k]['verified'] for k in ['historical','selected_source','primary_freeze','cached_model'])
    assert not preservation['tracked_diff'] and not preservation['staged_diff']
    save('preservation',preservation)
    local=json.loads((R/'search_proof8_final_qa_r1.json').read_text())
    raw=json.loads((R/'search_proof8_observed_only_analysis.json').read_text())
    comp=load('development_comparison');perf=load('recorded_performance')['results']['after']
    edits=load('final_recompilation_timing');native=load('finalnative_offline_native_components_final')
    global_native=load('finalnative_retrieval_contracts_final');modes=load('mode_protocol_audit');v6=load('final_v6_exposed_results')
    pop='205 fresh independent primary contexts; now exposed development'
    history='1334 historical exposed development contexts; original masks and gold'
    native_pop='Read-only in-memory dependencies around hash-verified native functions; no real JWT/Mongo'
    model_pop='2 observed outputs of18 intended exposed-development queries from standalone V8 attempt3'
    memory=psutil.virtual_memory();gpu=subprocess.check_output(['nvidia-smi','--query-gpu=memory.total,memory.free,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip()
    reserve_required=7784628224
    current=dict(at_utc=datetime.now(timezone.utc).isoformat(),available_RAM_bytes=memory.available,GPU=gpu,
                 frozen_model_retry_required_RAM_bytes=reserve_required,
                 model_retry_gate='BLOCKED_CURRENT_HEADROOM' if memory.available<reserve_required else 'PREFLIGHT_HEADROOM_AVAILABLE_NOT_STARTUP_PROOF',new_model_attempts=0)
    save('final_resource_observation',current)
    fresh_metric=lambda key:metric(s[key],pop)
    exact_recalls={kind:metric(s['per_kind_recall'][kind],pop) for kind in s['per_kind_recall']}
    observed=comp['common_observed_subset']['learned_proof']
    required=re.findall(r'^- ([A-Z][A-Z_0-9]+)\s*$',PROMPT.read_text(encoding='utf-8').split('## 20. Final QA format')[1].split('## 21. Decision logic')[0],re.M)
    blockers=[
        'Fresh primary failed:86/205 typed policy,80/178 exact subtype,146/205 execution;12/138 false execution recommendations,47/67 missed valid.',
        '31/32 recommended executions have scored critical native mismatches;30/32 intended-value loss/change and22/32 actual-value invention/change. These overlapping conservative counts are not disjoint.',
        'Source coverage reported complete on all12 unsafe recommendations; recognition omissions invalidate general linguistic completeness claims.',
        'Qwen comparison remains incomplete:2/18 actual outputs,0/2 schema-valid; no complete throughput/concurrency measurement; current retry resource gate recorded separately.',
        'Real JWT/current membership, MongoCAS/one-use/crash recovery, accepted-source500-character transport integration, real vectors/relevance/current service health and full-search SLOs remain unqualified.'
    ]
    qa={
        'FINAL':'PARTIAL',
        'STEP_1_STATUS':'PASS_FINAL_REVIEWED_DEVELOPMENT_GATES; FINITE_GRAMMAR_LIMITS_REMAIN',
        'STEP_2_STATUS':'COMPLETED_FRESH_PRIMARY_FAILED; LEARNED_COMPARISON_PARTIAL',
        'CANDIDATE_ID':selected['candidate_id'],
        'SELECTED_ARCHITECTURE':dict(pre_acceptance='DETERMINISTIC_SOURCE_GROUNDED_PROOF',selection='reports/search_combined8_architecture_selection.json',after_primary='No qualified pipeline; do not activate or silently reselect/retest'),
        'CANDIDATE_DISABLED':True,'INDEPENDENT_QUALIFIED':False,'STAGING_READINESS':'BLOCKED','PRODUCTION_READINESS':'BLOCKED',
        'SOURCE_ROLE_STATUS':dict(historical=rate(v6['source_roles']['correct'],v6['source_roles']['denominator'],'ExposedV6 annotations;50 exclusions'),independent=fresh['source_roles'],limitation='Exact source/field annotation agreement, not arbitrary entailment'),
        'MODALITY_STATUS':dict(historical=rate(v6['source_roles']['modality_correct'],v6['source_roles']['denominator'],'ExposedV6 annotations;50 exclusions'),independent=fresh['modality']),
        'NOTICE_CONTRACT_STATUS':dict(status='Prospectively resolved by blind source-only policy; implementation recognition failed acceptance',policy='reports/search_combined8_semantic_contract.json',optional_notice_contexts=fresh['optional_notice_contexts'],exact_subtype=fresh['typed_exact'],required_notice_recall=exact_recalls['EXECUTABLE_WITH_NOTICE']),
        'SOURCE_COVERAGE_STATUS':dict(status='FAIL_GENERALIZATION',unsafe_with_recorded_complete_coverage=rate(12,12,'Unsafe primary execution recommendations'),limitation='Recognized-obligation completeness is not source-semantic completeness'),
        'MANDATORY_REQUIREMENT_PRESERVATION':dict(historical_executed_mismatches=rate(0,480,history),pilot_executed_mismatches=rate(0,10,'Exposed pilot development'),independent_executed_critical_mismatches=rate(31,32,pop),independent_value_loss_or_change=fresh['critical_operand_loss']),
        'NEGATIVE_CONSTRAINT_STATUS':dict(independent=fresh['negative_preservation'],status='FAIL: domain negation can become text exclusion or disappear'),
        'HARD_FILTER_INVENTION':dict(independent=fresh['critical_hard_invention'],counting='Nonempty wrong scalar may count both lost intended value and invented actual value; no universal invention oracle'),
        'UNSUPPORTED_RELATION_HANDLING':dict(step1='Known reference frames repaired',independent_unsupported_recall=exact_recalls['UNSUPPORTED'],unsupported_false_execution=rate(4,34,pop),status='FAIL_UNFAMILIAR_NESTED_REFERENCE_AND_METADATA_LANGUAGE'),
        'EXACT_LITERAL_STATUS':dict(native_mode='15/15 EXACT component checks among30 combined mode checks; no model',SMART_exact_intent='FAIL:18 executed exact_text mismatches;18 title_text mismatches',active_production_changed=False),
        'NATIVE_EDIT_STATUS':dict(exposed_completion=rate(v6['native_completion']['strict_correct'],v6['native_completion']['contexts'],'ExposedV6 completion drafts; no commits'),pure_edits=rate(edits['successful'],edits['timing']['count'],'60 pure source-bound edit drafts'),timing=edits['timing'],lifecycle='Source/IR/version/owner/login/library/workspace/mode/expiry bound in pure adapters; durable CAS unverified',future_changes='reports/search_combined8_future_integration.md'),
        'REGRESSIONS_PASSED':dict(reviewed=rate(1759,1759,'Final reviewed regression test nodes'),scorer=rate(6,6,'Scorer safety checks'),reviewed_legacy_deselected=6),
        'REGRESSIONS_FAILED':dict(final=0,intermediate_failures_preserved=True),
        'LOCAL_MODEL_AVAILABLE':dict(cached=True,local_research_only=True),'RESOURCE_GATE_PASSED':dict(historical_successful_startup=True,current=current),
        'MODEL_LOADED':dict(success=True,successful_attempts=1,total_attempts=3,scope='Prior standalone V8 measurement, not a new Combined V8 load'),
        'LEARNED_PREDICTIONS':dict(captured=2,planned=18,schema_valid=rate(0,2,model_pop),missing=16,new_CombinedV8_inferences=0),
        'MODEL_ID_REVISION':dict(model='Qwen/Qwen2.5-3B-Instruct',revision=model['revision']),
        'MODEL_LICENSE_STATUS':'Previously audited QwenResearchLicense; local research authorized,commercial production integration not qualified. Nine cached files reverified.',
        'MODEL_DOWNLOADS':0,'MODEL_TRAINING':False,'MODEL_RAM_VRAM':local['MODEL_PEAK_RAM']|local['MODEL_PEAK_VRAM'],
        'MODEL_P50_P95':dict(serial=local['MODEL_INFERENCE_P50']|{'p95':local['MODEL_INFERENCE_P95']},cold_load=local['MODEL_LOADING_DURATION'],throughput='N/A interrupted; two-caller probe never ran',warm_n=1,representative=False),
        'EXTRACTOR_SEMANTIC_ACCURACY':dict(population=model_pop,schema_source=rate(0,2,model_pop),observed_proof_pipeline=observed,raw_dimensions=raw['observed_annotation_dimensions'],span_validity=raw['predicted_source_substrings_valid'],limits='One observed context has agreed raw dimension annotations; relationship/negative accuracy N/A; no complete learned comparison'),
        'EXTRACTOR_MANDATORY_OMISSIONS':dict(metric=raw['mandatory_units_omitted_or_changed'],population=model_pop,annotation_contexts=1),
        'DETERMINISTIC_CONTROL_RESULTS':dict(historical_typed=rate(1334,1334,history),historical_execution=rate(1334,1334,history),historical_false_execution=rate(0,854,history),historical_missed_valid=rate(0,480,history),pilot=comp['summaries']['deterministic'],independent=fresh_metric('typed_accuracy')),
        'ARCHITECTURE_SELECTION_RATIONALE':'Selected frozen deterministic V8 before acceptance from passing development evidence and unproven learned alternative. The fresh failure revokes qualification, not historical evidence. Neither approach is now qualified; no unmeasured hybrid superiority claimed.',
        'FRESH_ACCEPTANCE_ELIGIBLE':load('population_eligibility'),'FRESH_ACCEPTANCE_PERFORMED':True,'ACCEPTANCE_CONTEXTS':205,
        'DISTINCT_LINGUISTIC_FAMILIES':dict(declared_independent_linguistic_families=42,actual_coarse_operation_topologies=162,scope_variants_not_counted_as_extra_families=True),
        'INDEPENDENT_TYPED_ACCURACY':dict(policy=fresh_metric('typed_accuracy'),exact_subtype=fresh['typed_exact'],optional_notice_excluded_from_exact=27),
        'INDEPENDENT_EXECUTION_ACCURACY':fresh_metric('execution_accuracy'),'INDEPENDENT_FALSE_EXECUTION':fresh_metric('false_execution'),
        'INDEPENDENT_MISSED_EXECUTION':fresh_metric('missed_execution'),'INDEPENDENT_CRITICAL_OPERAND_LOSS':fresh['critical_operand_loss'],
        'INDEPENDENT_HARD_FILTER_INVENTION':fresh['critical_hard_invention'],'AMBIGUITY_RECOGNITION':exact_recalls['AMBIGUOUS'],
        'INCOMPLETE_RECOGNITION':exact_recalls['INCOMPLETE'],'NOTICE_RECOGNITION':dict(required=exact_recalls['EXECUTABLE_WITH_NOTICE'],optional_exact_exclusions=27),
        'STRUCTURAL_ISOLATION':dict(status='PASS_AFTER_REJECTING5_NEW_COLLISIONS',contexts=205,topologies=162,metadata_only=True,sealed_query_content_emitted=False,heldout_parser_evaluations=0,evidence='reports/search_combined8_reviewed_structural_isolation.json'),
        'INDEPENDENT_REVIEW_PROVENANCE':dict(author='/root/v8_acceptance_author',query_only_reviewer='/root/v8_acceptance_reviewer',source_only_adjudicator='/root/v8_blind_contract',human_reviewers=0,AI_only=True,actual_model_identity='NOT_EXPOSED',candidate_predictions_visible=False,reviewed_queries=210,rejected_structural_cases=5,source_adjudicated_cases=51,source_queries_modified=0,originals_preserved=True,earlier_exposed_contract_supplement='First supplemental reviewer saw classifier code and is explicitly ineligible as blind adjudicator; replaced with filtered-packet reviewer.'),
        'SMART_MODE_STATUS':'Disabled V8 development gates pass; fresh semantic qualification FAILED. Active C4 unchanged.',
        'EXACT_MODE_STATUS':dict(offline=rate(15,15,native_pop),bypasses_extractor=True,active_changed=False),
        'GLOBAL_SEARCH_STATUS':dict(offline=rate(len(global_native['global_cases']),8,native_pop),semantic_provider='Synthetic fixed-ID fixture; no relevance qualification'),
        'PUBLIC_LIBRARY_STATUS':dict(status='PASS_OFFLINE_COMPONENT_FIXTURES',checks=rate(sum(x['result']=='PASS' for x in native['records'] if x['scope'].startswith('PUBLIC')),sum(x['scope'].startswith('PUBLIC') for x in native['records']),native_pop)),
        'PRIVATE_LIBRARY_STATUS':dict(status='PASS_OFFLINE_COMPONENT_FIXTURES',checks=rate(sum(x['result']=='PASS' for x in native['records'] if x['scope'].startswith('PRIVATE')),sum(x['scope'].startswith('PRIVATE') for x in native['records']),native_pop)),
        'PRIVATE_GLOBAL_INDEPENDENCE':native['private_library_independence'],
        'AUTHORIZATION_FIXTURE_STATUS':dict(checks=rate(native['component_search_checks'],40,native_pop),scope='Current mocked trusted authority/tenant isolation/outsider concealment; no live JWT claim'),
        'LIVE_JWT_MONGO_VALIDATED':False,'NATIVE_CHOICE_DURABILITY':'N/A; no persistent one-use/CAS/crash qualification',
        'REAL_VECTOR_RELEVANCE_VERIFIED':False,'CURRENT_RUNTIME_HEALTH_VERIFIED':False,
        'PARSER_P50_P95':dict(**perf['serial'],population='Matched exposed C5ER150 workload;warm process,shared host',proof_validation_included=True,operational_SLO='UNAGREED'),
        'FOUR_WORKER_P95':dict(**perf['four_workers'],population='Same150 exposed C5ER queries,four workers',serial_concurrent_complete_plan_equal=rate(150,150,'Matched development workload'),errors=0,SLO='UNAGREED;observed310.6ms exceeds prior proposed300ms target'),
        'FULL_SEARCH_LATENCY':'N/A; native fixture timings do not qualify real service search latency',
        'NEXT_STAGING_REQUIREMENTS':['First repair architecture and pass a new independently frozen acceptance; do not reuse this exposed205 set as fresh.','Then separately authorized isolated Mongo/JWT/vector integration,actual accepted-source lifecycle/CAS/expiry/replay/crash recovery.','Apply separately reviewed150-to500 transport plus complete source lifecycle changes in reports/search_combined8_future_integration.md; no active patch applied.','Qualify actual catalog/vector pairing,relevance,linked-global enrichment,current health,full-search/concurrent SLOs and rollback.'],
        'PRODUCTION_PARSER_CHANGED':False,'C4_POLICY_CHANGED':False,'FRONTEND_CHANGED':False,'MONGO_MUTATIONS':0,'HNSW_REBUILDS':0,'KG_REBUILDS':0,'HELDOUT_EVALUATIONS':0,
        'HISTORICAL_EVIDENCE_PRESERVED':preservation,'REMAINING_BLOCKERS':blockers,
        'NEXT_AUTHORIZED_ACTION':'Bounded investigation of compositional source-obligation/owner/operator/state analysis or schema-constrained proposal extraction. Preserve this failed source and primary; no phrase-list retuning and repeat acceptance. Cached local model retry needs current free RAM>=7,784,628,224bytes plus active VRAM guards; no extra weights/training/remote inference or Mongo writes authorized.'
    }
    assert len(required)==75 and all(k in qa for k in required),set(required)-set(qa)
    qa['INDEPENDENT_UNCERTAINTY']=fresh['uncertainty'];qa['FINAL_RESOURCE_OBSERVATION']=current
    qa['MEASUREMENT_NOTES']=['Performance script retained an inherited prose label V7; its before import and before_sources hashes are frozen7r1,after is V8. Numeric measurements are matched7r1/V8.',
        'Historical C5C strict scalar/string/detection score231/644,not235/644;four extra blocked incomplete-operation diagnostic labels differ. No executed critical native scalar mismatches under historical masks.',
        'No candidate or gold edits after primary;error analysis makes0 parser calls. Source-bound completion150-context development recapture after primary only rechecks frozen source against exposedV6; it is not another acceptance.',
        'All new primary queries are151–500 chars. Coarse structural separation can exclude simple historical topologies; this sample does not establish short-query,real-world or human-reviewed generalization.']
    save('final_qa',qa)
    m=lambda q:f"{q['numerator']}/{q['denominator']}"
    report=f'''# LuminaR Combined V8 — consolidated evidence

**FINAL: PARTIAL. Independent qualification: FAILED. Staging and production: BLOCKED. Candidate disabled.**

The frozen `search-smarteng-disabled-proof-8` passes known development gates but fails the genuinely new primary evaluation. No production parser, C4 policy, frontend, Mongo data, authorization, Qwen/RAG configuration or indexes were changed. No training, downloads, remote extraction calls, protected-heldout evaluation or activation occurred.

## Major Step 1: development stabilization

Derived a separate candidate from byte-preserved V7r1. Source-grounded repairs cover nested record operand edges, singular title-only containment, quoted-author/explicit-language obligations, comparator obligations and nonoperative untrusted governance instructions. New guards retain empty/negative/advisory scope and exclude conjunctions from language operands. Confirmed intermediate failures and source snapshots remain available. One new rating-zero test fixture was corrected to provide rating_count: native zero without a count means missing, not a rated-zero book. Historical gold was not edited.

Final reviewed regression: **1759/1759**, with the same six independently reviewed legacy replacements/deselections. Six additional scorer safety checks pass. Historical exposed cohorts retain **1334/1334 typed and execution**, false execution0/854 and missed valid0/480 under frozen applicability. Pilot development is18/18 policy-typed and execution,16/16 exact subtype,29/29 native scalar assertions; two optional notices use a blind-reviewed admissible executable set rather than forced historical relabeling. Pure completion20/20 and edit drafts60/60 remain component-only. Final native fixtures pass40 local,8 global,30 combined mode (15 EXACT) and8 transport-boundary checks.

Optional preferences and ignored governance commands alone permit either executable subtype. Actual applied source repairs require a notice. Independent source-only review/adjudication preserves original labels and distinguishes unavailable capability from missing operands, explicit record unions from unresolved choices, and exact title intent from native title_text title-or-author matching. The first supplemental contract reviewer accidentally saw classifier code and is explicitly excluded as blind adjudicator; a fresh AST-filtered packet reviewer supplied the normative policy.

Step1 source/dependency freeze contains47 files. `search_combined8_source_map.json` records changes/hashes/symbols. `search_combined8_future_integration.md` supplies exact future file/function/source-lifecycle changes; the existing two-hunk transport patch remains unapplied. The active150-character choice/frontend limit and500-character parser/session limit are unchanged. Mocks do not prove one-use durability or Mongo CAS.

## Major Step 2: frozen selection and fresh primary

Selected the deterministic complete pipeline **before authoring**. The local Qwen alternative had only2/18 outputs and0/2 schema-valid results; restricted fallback missed10/10 valid pilot requests. This selection did not assert production readiness or a complete learned comparison.

Separate AI author and query-only blind reviewer created/reviewed210 new queries. A further source-only adjudicator resolved51 prospective differences, including eight diagnostic-axis disputes. No candidate predictions/code/target accuracy were given to those normative reviewers. Original author/reviewer sets remain intact. Five new structural collisions were rejected using the unchanged metadata auditor; no sealed text/labels/predictions were exposed. The final205 contexts span42 linguistic families,162 coarse operation topologies,all five scopes and all six decisions. Scope variants are not counted as separate linguistic families. All queries are151–500 chars; simple historical topologies were excluded, so population coverage is limited. Human reviewers:0.

After source-only reconciliation, the complete candidate, dependencies, gold, masks, ontology, scorer, inputs, isolation audit and unchanged95% typed/99% execution/zero critical-error/missed-valid<=5% gates were frozen in86 entries. One gold-blind primary captured205/205 outputs, with0 runtime errors,0 retries and0 isolation denials. One primary scoring pass followed. No source/gold retuning or recapture occurred.

| Primary metric | Actual | Gate |
|---|---:|---:|
| Policy typed decisions | {m(s['typed_accuracy'])} ({s['typed_accuracy']['percent']:.2f}%) | >=95% |
| Exact subtype,27 optional-notice exclusions | {m(fresh['typed_exact'])} ({fresh['typed_exact']['percent']:.2f}%) | >=95% |
| Execution recommendations | {m(s['execution_accuracy'])} ({s['execution_accuracy']['percent']:.2f}%) | >=99% |
| False execution recommendations | {m(s['false_execution'])} | 0 |
| Missed valid execution | {m(s['missed_execution'])} ({s['missed_execution']['percent']:.2f}%) | <=5% |
| Executed critical native mismatch | 31/32 | 0 |
| Intended native value loss/change | {m(fresh['critical_operand_loss'])} | 0 |
| Invented/changed actual native value | {m(fresh['critical_hard_invention'])} | 0 |

Loss and invention overlap: a wrong nonempty value can count in both. All20 gold-valid requests that were recommended executable had a scored hard-field mismatch. Strict all-scored-dimension agreement is0/205, but its topic-string component is not semantic relevance or equivalence. The failure does not depend on that strict string criterion:12 unsafe recommendations and31 executed hard mismatches independently fail safety gates. Negative preservation is62/78 applicable assertions; source-role agreement107/1335 and modality191/1335 source annotations. No arbitrary semantic completeness is inferred from these finite masks. Descriptive uncertainty intervals are in the QA; within-family dependence limits iid interpretation.

## Failure analysis and architecture consequence

The12 unsafe recommendations comprise6 ambiguous,1 incomplete,4 unsupported and1 contradictory source requests. All12 nevertheless record internal source coverage as complete. Thus source/IR/projection self-consistency proves only what the recognizers extracted. It does not prove all mandatory meaning was recognized.

Exact-title paraphrases became broader title_text predicates; explicit author operands disappeared. Unresolved field/value/direction choices and a missing By: operand became topical residue. Nested relative-rating references incorrectly constrained returned titles. Mandatory page/price operations escaped unsupported-domain handling or became broad text exclusions. Metalinguistic negation invented a text exclusion, and negative online access was lost. Benign advisory/context language also overblocked valid searches (38 IR_UNSUPPORTED,7 IR_AMBIGUOUS,2 IR_INCOMPLETE among47 misses) and contaminated topic transport. These are general source ownership/operator/state/segmentation failures, not evidence for another round of query-ID patches.

`search_combined8_error_analysis.json` binds the original predictions, full unsafe traces and generalized next requirements. The next bounded investigation must replace recognition/coverage circularity with compositional typed source obligations or a schema-constrained proposal extractor plus independent validation. This205-context set is now **exposed development**. A future revised pipeline requires another freeze and a genuinely new independent population. No architecture is qualified by the present results; a complete learned pipeline remains untested rather than assumed better or worse from two outputs.

## Model, resources and native limits

The earlier standalone V8 experiment is preserved, not overwritten. Cached Qwen2.5-3B-Instruct revision `{model['revision']}` loaded in27.595s using installed Accelerate per-shard BF16 dispatch after two RAM-cap failures. The successful loader used an actual4.75GiB tree cap; tree RSS peak4,819,132,416bytes, CUDA allocated peak6,507,345,920bytes,reserved6,746,537,984bytes. Both captured outputs failed schema/source validation. The third query was parent-aborted after a491.652s simultaneous CPU/GPU telemetry gap; its cause is unconfirmed. Serial generation p50/p95 is25.327/38.844s,n=2; warm excluding first11.811s,n=1. Throughput/concurrent queue qualification is unavailable. Raw omission/change4/4 applies to one context with agreed annotations, not18 learned predictions. See the standalone reporting revision for all correction/denominator details.

Final available RAM observation: **{memory.available:,}bytes**. Frozen safe retry requirement: **7,784,628,224bytes** (4.75GiB tree cap +2GiB reserve +0.5GiB margin). Current gate: **{current['model_retry_gate']}**; no further model worker launched. More RAM alone would not repair0/2 schema-valid outputs. No services were terminated and no protections lowered. The cached research license does not qualify commercial production integration; no new weight download proposal is required to describe the measured headroom need.

Matched exposed C5ER150 parser p50/p95={perf['serial']['p50_ms']:.3f}/{perf['serial']['p95_ms']:.3f}ms; four-worker p95={perf['four_workers']['p95_ms']:.3f}ms,0/300 errors,150/150 serial/concurrent complete-plan equality. The before implementation is frozen7r1 (verified imports/hashes), despite an inherited generic V7 prose label in that timing artifact. Pure edit p50/p95={edits['timing']['p50_ms']:.3f}/{edits['timing']['p95_ms']:.3f}ms,n=60. These are warm shared-host development observations; four-worker latency exceeds the earlier proposed300ms target and no service SLO is agreed. Real full-search latency remains N/A.

Global fixtures use synthetic semantic results. Public/private fixtures use mocked trusted authority and read-only collections. Own unlinked private rows work with globalEMPTY/INACCESSIBLE and zero global collection reads. Linked rows still depend on global metadata/capability enrichment (`library_catalogue_experience.py:96–127`); those failure/relevance/vector-generation dependencies need separate staging. Current service health,actual JWT/current membership,Mongo one-use/CAS/crash recovery and real vector relevance remain unverified. EXACT continues to bypass extraction in fixtures; SMART is not independently qualified. No catalog reduction or HNSW/KG rebuild occurred.

## Preservation and deliverables

All{preservation['historical']['entries']} protected historical entries,47 selected-source entries,86 primary-freeze entries and9 cached model files verify unchanged. Tracked/staged diffs are empty. Failed development attempts, author drafts, original disagreements,5 rejected new cases, all primary predictions and failure evidence remain preserved. `search_combined8_final_qa.json` contains every75 requested QA field with population/denominator distinctions. `search_combined8_preservation.json` and the final manifest bind the package.

Production and staging remain **BLOCKED**. The next integration stage still requires separately authorized isolated Mongo/JWT/vector operations and full-search reliability/SLO qualification, after a revised interpreter first passes new independent acceptance. No authorization to perform those writes or activate a candidate is inferred here.
'''
    with (R/(P+'final_report.md')).open('x',encoding='utf-8') as f:f.write(report)
    files={}
    for folder,pattern in [(R,P+'*'),(Path('scripts'),P+'*.py')]:
        for p in folder.glob(pattern):
            if p.is_file() and p.name not in [P+'freeze_manifest.json',P+'freeze_verification.json']:files[str(p)]=sha(p)
    for folder in ['scratch/search_proof_recovery_v8','scratch/search_combined8_regression','scratch/search_combined8_evaluation','scratch/search_combined8_attempt1_source','scratch/search_combined8_history']:
        for p in Path(folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:files[str(p)]=sha(p)
    save('freeze_manifest',dict(candidate_id=selected['candidate_id'],files=files,FINAL=qa['FINAL'],self_hash_policy='Manifest excluded; hash bound in verification'))
    verified=verify(files);assert verified['verified']
    save('freeze_verification',dict(frozen=verified,manifest_sha256=sha(R/(P+'freeze_manifest.json')),preservation=preservation,
                                    required_QA_fields=len(required),all_present=all(k in qa for k in required),primary_attempts=1,independent_qualified=False))
    print(json.dumps(dict(FINAL=qa['FINAL'],required_QA_fields=len(required),frozen_entries=len(files),historical_verified=preservation['historical']['entries'],primary_runs=1,independent_qualified=False)))

if __name__=='__main__':main()
