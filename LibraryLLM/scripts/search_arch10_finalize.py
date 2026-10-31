"""Consolidated V10 QA and immutable development checkpoint, not acceptance.

All historical evidence remains in place. No protected source is rewritten.
"""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import json,hashlib,xml.etree.ElementTree as ET,ast,subprocess,sys,statistics,math

ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports';ID='search-smarteng-disabled-proof-10'
def read(name):return json.loads((R/name).read_text(encoding='utf8'))
def lines(name):return [json.loads(x) for x in (R/name).read_text(encoding='utf8').splitlines()]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(name,obj):
    with (R/name).open('x',encoding='utf8') as f:json.dump(obj,f,indent=2,ensure_ascii=False)
def m(n,d,pop,status='MEASURED'):
    return dict(numerator=n,denominator=d,population=pop,status=status,evidence='EXPOSED_DEVELOPMENT')


def main():
    pre=read('search_arch9_preflight.json');v9=read('search_arch9_source_freeze.json')
    bad=[];missing=[]
    for p,h in {**pre['protected_files'],**v9['source_files']}.items():
        f=ROOT/p
        if not f.exists():missing.append(p)
        elif sha(f)!=h:bad.append(p)
    assert not missing and not bad,(missing,bad)
    production=[]
    for folder in ['backend','search','frontend','rag','recommendation','knowledge_graph','chatbot','assistant']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and p.suffix in ('.py','.ts','.tsx','.js','.jsx') and not any(x in p.parts for x in ['node_modules','__pycache__','.venv','models']):
                if b'search_architecture_v10' in p.read_bytes() or b'search_arch10' in p.read_bytes():production.append(str(p.relative_to(ROOT)))
    assert not production,production
    preserve=dict(candidate_id=ID,protected_entries=m(len(pre['protected_files']),len(pre['protected_files']),'V9 authoritative protected manifest'),
        v9_freeze_entries=m(len(v9['source_files']),len(v9['source_files']),'V9 freeze source/dependencies'),
        missing=missing,mismatches=bad,production_imports=production,structural_isolation='PASS',historical_evidence_preserved=True,
        production_source_changed=False,c4_policy_changed=False,frontend_changed=False,mongo_mutations=0,hnsw_rebuilds=0,kg_rebuilds=0,
        heldout_evaluations=0,new_weights_downloaded=0,model_training_runs=0,unrelated_processes_terminated=0,
        exact_active_route='search/query_plan.py PARSER_VERSION search-v2c-c4-deterministic-1 unchanged',
        limitation='Manifests verify their listed files. Untracked historical report files were not rewritten; no git reset/checkout/clean/stash performed.')
    write('search_arch10_preservation.json',preserve)
    test=ET.parse(R/'search_arch10_verified_tests.xml')
    cases=list(test.iter('testcase'));failed=sum(t.find('failure') is not None or t.find('error') is not None for t in cases)
    skipped=sum(t.find('skipped') is not None for t in cases);passed=len(cases)-failed-skipped
    assert not failed
    source_review=read('search_arch10_source_contract_review.json')
    reconcile=dict(original_regression_failures=2,new_reviewed_migrations=1,inherited_reviewed_migrations=6,
        source_only_review='reports/search_arch10_source_contract_review.json',review_sha256=sha(R/'search_arch10_source_contract_review.json'),
        assertions_or_gold_changed=False,old_tests_retained=True,
        title=dict(original='scratch/search_architecture_v9/test_roles_edits.py::test_quoted_filter_words_owned_by_literal_title',
            original_file_sha256=sha(ROOT/'scratch/search_architecture_v9/test_roles_edits.py'),
            candidate_deselected_node='scratch/search_architecture_v10/test_roles_edits.py::test_quoted_filter_words_owned_by_literal_title',
            reason='Title-only containment cannot be enforced by title-or-author substring. Source-only migration approved.',
            replacements=['test_semantic_workflow.py::test_reviewed_title_only_migration (3 parameter cases)',
                'test_semantic_workflow.py::test_native_title_strengths_are_distinct']),
        pages=dict(original='scratch/search_arch9_regression/test_search_v2c_c4_reviewed_legacy.py::test_curated_candidate_plan[gold-088]',
            resolution='IMPLEMENTATION_REPAIR_RETAINS_INCOMPLETE',reason='Missing operand state retained; incomplete-first policy explicitly selected. Supplying any page constraint remains UNSUPPORTED.',migration=False),
        total_deselected=7,additional_silent_deselections=0,
        current_regression_population=dict(passed=passed,failed=failed,skipped=skipped,deselected=7,
            source='reports/search_arch10_verified_tests.xml',development=True,measured=True),
        count_reconciliation='V9 broad run omitted 18 of its 42 separately reported metamorphic cases plus 5 compact-extractor tests. V10 includes all 42 and all 5, repairs pages (+1), replaces title assertion (-1 failed node), and adds 39 workflow cases. Historical 1757 passing +23 newly included inherited tests +1 repaired assertion +39 new tests =1820 passing. Original assertions preserved.')
    write('search_arch10_contract_reconciliation.json',reconcile)
    dev=read('search_arch10_checkpoint_dev72_results.json');v8=read('search_arch10_checkpoint_v8exposed205_results.json')
    realistic=read('search_arch10_checkpoint_realistic_results.json');perf=read('search_arch10_performance_verified.json')
    historical={k:read('search_arch10_verified_'+k+'_results.json') for k in ['c5e90','c5er150','smarteng150','comp3_150']}
    history_summary={}
    for key in ['typed_accuracy','execution_accuracy','false_execution','missed_execution']:
        history_summary[key]=m(sum(x['summary'][key]['numerator'] for x in historical.values()),
            sum(x['summary'][key]['denominator'] for x in historical.values()),'540 historically exposed contexts, matched V10 development replay')
    history_summary['hard_field_mismatch_cases']=m(sum(len(x['critical_operands']) for x in historical.values()),
        sum(1 for k in historical for p in lines('search_arch10_verified_'+k+'_predictions.jsonl') if p['executable']),
        '540 historical contexts currently executed; unchanged legacy masks, ONLY-derived opposite-format projections')
    before=read('search_arch9_dev72_results.json');gold={g['case_id']:g for g in lines('search_arch9_dev_reviewed.jsonl')}
    after={r['case_id']:r for r in dev['results']}
    first_fault={
      'v9_dev_027':('Source-role error','Deferred category alternative was treated as a semantic topic.'),
      'v9_dev_028':('Operator ownership','Explicit minimum/maximum choice did not own the rating.'),
      'v9_dev_062':('Operand extraction','Both implicit publication bounds were retained only as topic.'),
      'v9_dev_063':('Negative requirement loss','Shared category operand did not carry both require/exclude predicates.'),
      'v9_dev_070':('Modality error','No record may offer physical access was softened by modal may.'),
      'v9_dev_005':('Source role / oracle policy','Descriptive canonical-subject wording was retained as semantic text instead of old hard category expectation.'),
      'v9_dev_006':('Planning/projection','Physical borrowing request used generic availability and lost physical-only requirement; availability repaired.'),
      'v9_dev_015':('Source correction','Explicit numeric correction was not owned; unresolved corrections now block instead of executing stale operands.'),
      'v9_dev_018':('Unsupported-domain omission','Explicit misspelled language label was ignored; bounded source-grounded label repair added.'),
      'v9_dev_019':('Source role / oracle policy','Canonical category expectation absent while unauthorized staff/scope text remains nonauthoritative.'),
      'v9_dev_023':('Source-role error','Reported hypothetical colleague preference became mandatory ONLINE; reported-speech ownership repaired.'),
      'v9_dev_004':('Operand extraction','Second rating range operand became unknown number; range now projected with both bounds.'),
      'v9_dev_007':('Negative predicate ownership','Omit-category phrasing and independent searchable-text exclusion need separate recognized ownership.'),
      'v9_dev_009':('Source-role error','Historical group details and current structured noun phrase not reliably separated.'),
      'v9_dev_010':('Quoted-literal handling','Extended exact-title syntax and explanatory note not covered by bounded normalized-title recognizer.'),
      'v9_dev_011':('Sort / entity ownership','Title-or-author alternative and alphabetic sort-by-title were not disambiguated from author introduction.'),
      'v9_dev_012':('Operand extraction / field invention','Long structured noun phrase lost year/language and introduced an exclusion token; remains blocked.'),
      'v9_dev_014':('Source-backed repair','Misspelled rating label requires reliable corrected source mapping; remains blocked.'),
      'v9_dev_020':('Modality error','Optional access sentence and supported language requirements not reliably separated; remains blocked.'),
      'v9_dev_021':('Source correction','Explicit corrected exact-title source not reliably recompiled; remains blocked.'),
      'v9_dev_022':('Source correction','One year endpoint correction with retained lower bound and language not reliably recompiled; remains blocked.'),
      'v9_dev_024':('Source-role / sort error','Background folder name, advisory access, category spelling repair and sort interact; remains blocked.'),
    }
    rows=[]
    ids=set()
    for kind in ['false_executions','critical_executed_operands','missed_executions']:
        ids.update(r['case_id'] for r in before[kind])
    for cid in sorted(ids):
        r=after[cid];kind,reason=first_fault[cid]
        rows.append(dict(case_id=cid,query=gold[cid]['query_text'],first_incorrect_transformation=kind,source_analysis=reason,
            current_decision=r['decision'],current_execution=r['execution'],remaining_mismatches=r['mismatches'],
            critical_executed_fields=r['critical_executed_operand_mismatches']))
    analysis=dict(population='EXPOSED_V9_DEV72_NOT_INDEPENDENT',cases=rows,
        original_false=m(5,48,'V9 dev72 expected nonexecuting'),current_false=dev['summary']['false_execution'],
        original_missed=m(11,24,'V9 dev72 expected executing'),current_missed=dev['summary']['missed_execution'],
        raw_comparison_limit='Six current mismatch cases concern old subject/include_terms hard-category expectations versus semantic retention. One concerns ONLY-derived opposite-format exclusion required by native matches. Raw scores are retained; no oracle migration or score credit claimed.',
        remaining_blockers=['Source corrections and multi-field noun phrases','Explicit category semantics versus descriptive semantic topics need reviewed masks','Varied long requests still miss valid execution'],
        generalized_repairs=['Deferred alternatives','Publication boundary ownership with topical-date protection','Shared contradictory operand','Negative modal access',
          'Reported hypothetical source role','Complete rating range ownership','Physical requestability projection','Bounded language-label repair','ONLY format native complement'])
    write('search_arch10_dev72_analysis.json',analysis)
    embed=read('search_arch10_embedding_probe2.json');probe=next((r for r in embed.get('records',[]) if r.get('event')=='embedding_probe'),None)
    assert probe and probe['status']=='PASS_READ_ONLY_COMPONENT'
    embedding_times=sorted(r['embedding_ms'] for r in probe['observations'])
    embedding=dict(samples=len(embedding_times),p50_ms=statistics.median(embedding_times),p95_ms=embedding_times[math.ceil(.95*len(embedding_times))-1],
        population='12 encodes of 4 exposed development queries, cached CPU MiniLM; includes first cold encode',status='MEASURED',evidence='DEVELOPMENT_COMPONENT_ONLY')
    no_measure=dict(status='NOT_MEASURED',numerator=None,denominator=None,population='No independent acceptance population evaluated')
    blockers=[
      'Exposed V9 complex-query usability remains poor; source correction, explicit category and multi-field ownership families unresolved.',
      'Historical masks and native projection equivalence need independent semantic adjudication; raw hard-field mismatches remain reported.',
      'New realistic cohort was used for development; it has only 47 authored templates and two long templates, with no fresh acceptance credit.',
      'Native global negative-only ONLINE defect is repaired only in disabled adapter; active C4 source remains unchanged.',
      'Real embedding/local 12-vector snapshot probe is not global catalog/service/reranker/relevance qualification.',
      'Real JWT/current membership, Mongo hydration/security, durable one-use CAS and 150/500-character transport alignment unverified.',
      'Full-service latency, runtime/index health, global sort data quality and cross-candidate recall unverified.',
      'Linked institutional hydration can depend on global metadata even though unlinked fixtures are independent.'
    ]
    qa={
      'FINAL':'PARTIAL',
      'STEP_1_STATUS':'IMPLEMENTED_RECONCILIATION_AND_REPAIRS; DEVELOPMENT_GATES_PARTIAL',
      'STEP_2_STATUS':'DISABLED_WORKFLOW_IMPLEMENTED_AND_COMPONENT_TESTED; QUALIFICATION_BLOCKED',
      'CANDIDATE_ID':ID,'CANDIDATE_DISABLED':True,'ARCHITECTURE_SELECTED':'PATH_C_FOR_QUALIFICATION; SEMANTIC_FIRST_DETERMINISTIC_DESIGN_RETAINED',
      'CAPABILITY_REGISTRY_VERSION':'V10-capability-registry-v2','REGISTRY_NATIVE_CONSISTENCY':'SOURCE_AUDITED_WITH_EXPLICIT_NATIVE_DEFECTS_AND_BOUNDED_COMPLETENESS',
      'ORIGINAL_REGRESSION_FAILURES':m(2,1759,'Historical V9 broad collected non-deselected regressions'),
      'REVIEWED_CONTRACT_MIGRATIONS':dict(new=1,inherited=6,implementation_repairs=1,review='reports/search_arch10_contract_reconciliation.json'),
      'REGRESSIONS_PASSED':m(passed,len(cases),'V10 reviewed broad regression nodes'),
      'REGRESSIONS_FAILED':m(failed,len(cases),'V10 reviewed broad regression nodes'),
      'SOURCE_INTERPRETATION_STATUS':'FINITE_SOURCE_GROUNDED_GRAMMAR; ARBITRARY_ENGLISH_COMPLETENESS_UNPROVEN',
      'QUERY_INTENT_IR_STATUS':'IMPLEMENTED_FOUR_CHANNELS_PLUS_NONOPERATIVE_SOURCE; IMMUTABLE_SOURCE_AND_DIGESTS',
      'HARD_FILTER_SOURCE_OWNERSHIP':'PROOF_AND_SOURCE_CHECKED_IN_COMPONENTS; LEGACY_SEMANTIC_MASK_DISAGREEMENTS_UNRESOLVED',
      'MANDATORY_OPERAND_PRESERVATION':dict(realistic=realistic['summary']['hard_field_mismatch_cases'],dev72_raw_cases=m(len(dev['hard_mismatches']),sum(r['execution'] for r in dev['results']),'V9 dev72 currently executed plans; legacy masks')),
      'NEGATIVE_CONSTRAINT_PRESERVATION':'NATIVE_MATCHES_AND_ADAPTER_FIXTURES_PASS; NO_ARBITRARY_LANGUAGE_GUARANTEE',
      'SEMANTIC_TOPIC_PRESERVATION':realistic['summary']['semantic_preserved'],
      'ADVISORY_PREFERENCE_HANDLING':'IR_ADVISORY_ONLY; SOURCE_TEXT_TRANSPORTED_TO_EMBEDDING_REQUEST; NO_MEASURED_RANKING_GAIN',
      'TARGETED_CLARIFICATION':'IMPLEMENTED_SOURCE_OWNED_PROMPTS_AND_INHERITED_BOUND_EDIT_ADAPTERS; LIVE_TRANSPORT_UNCHANGED',
      'TITLE_MATCHING_CAPABILITY':'GENERAL_TITLE_OR_AUTHOR_SUBSTRING; NORMALIZED_TITLE_OR_ID_EQUALITY; STRICT_TITLE_ONLY_SUBSTRING_AND_BYTE_LITERAL_UNSUPPORTED',
      'SCOPE_CAPABILITY_ENFORCEMENT':'FIVE_BACKEND_OWNED_CONTEXTS_COMPONENT_TESTED; QUERY_CANNOT_SELECT_AUTHORITY',
      'ORDINARY_SEMANTIC_QUERY_ACCURACY':realistic['strata']['complexity']['ordinary'],
      'STRUCTURED_QUERY_ACCURACY':realistic['strata']['complexity']['structured'],
      'COMPLEX_QUERY_ACCURACY':dict(realistic=realistic['strata']['complexity']['complex'],legacy_dev72=dev['summary'],legacy_v8_205=v8['summary']),
      'DEVELOPMENT_TYPED_ACCURACY':dict(realistic=realistic['summary']['typed'],v9_dev72=dev['summary']['typed_accuracy'],v8_exposed205=v8['summary']['typed_accuracy']),
      'DEVELOPMENT_EXECUTION_ACCURACY':dict(realistic=realistic['summary']['execution'],v9_dev72=dev['summary']['execution_accuracy'],v8_exposed205=v8['summary']['execution_accuracy']),
      'DEVELOPMENT_FALSE_EXECUTION':dict(realistic=realistic['summary']['false_execution'],v9_dev72=dev['summary']['false_execution'],v8_exposed205=v8['summary']['false_execution']),
      'DEVELOPMENT_MISSED_VALID':dict(realistic=realistic['summary']['missed_valid'],v9_dev72=dev['summary']['missed_execution'],v8_exposed205=v8['summary']['missed_execution']),
      'DEVELOPMENT_HARD_FIELD_MISMATCHES':dict(realistic=realistic['summary']['hard_field_mismatch_cases'],v9_dev72=m(len(dev['hard_mismatches']),sum(r['execution'] for r in dev['results']),'V9 dev72 executed; legacy masks'),v8_exposed205=m(len(v8['hard_mismatches']),sum(r['execution'] for r in v8['results']),'V8 exposed205 executed; legacy masks')),
      'DISTINCT_LINGUISTIC_FAMILIES':dict(numerator=47,denominator=47,population='47 authored realistic query templates; 235 scope contexts',status='MEASURED_AUTHORED_TAXONOMY_NOT_INDEPENDENT_GENERALIZATION',evidence='EXPOSED_DEVELOPMENT'),
      'SHORT_QUERY_METRICS':realistic['strata']['length_bucket']['short'],
      'MEDIUM_QUERY_METRICS':realistic['strata']['length_bucket']['medium'],
      'LONG_QUERY_METRICS':realistic['strata']['length_bucket']['long'],
      'REAL_SEMANTIC_PROVIDER_VERIFIED':'PARTIAL_CACHED_MINILM_PLUS_EXISTING_LOCAL_12_VECTOR_SNAPSHOT; CONFIGURED_SERVICE_NOT_VERIFIED',
      'RETRIEVAL_RELEVANCE_RESULTS':'UNVERIFIED_NO_INDEPENDENT_BOOK_JUDGMENTS; NO_PRECISION_RECALL_NDCG_FABRICATED',
      'FULL_SEARCH_LATENCY':'UNMEASURED; EMBEDDING_AND_FIXTURE_TIMINGS_ARE_COMPONENTS_ONLY',
      'PARSER_P50_P95':perf['stages']['combined_parser'],'FOUR_WORKER_P95':perf['four_worker'],
      'LEARNED_EXTRACTOR_REQUIRED':False,'LEARNED_EXTRACTOR_EVALUATED':'COMPACT_SCHEMA_TESTS_ONLY_NO_NEW_QWEN_PREDICTIONS; MINILM_PROBE_IS_RETRIEVAL_NOT_EXTRACTION',
      'MODEL_LICENSE_STATUS':'QWEN_PINNED_aa8e72537993ba99e69dfaafa59ed015b17504d1_QWEN_RESEARCH_LICENSE; V9_APACHE_LABEL_INCORRECT; COMMERCIAL_CLEARANCE_NOT_ESTABLISHED',
      'MODEL_RESOURCE_STATUS':dict(audit='reports/search_arch10_resource_license_audit.json',embedding_worker_peak_rss_bytes=embed['peak_worker_tree_rss_bytes'],qwen_resource_measurement='NOT_RUN',new_model_weights=0),
      'SMART_STATUS':'DISABLED_CANDIDATE_ONLY; ORDINARY_WORKFLOW_PASS_COMPLEX_QUALIFICATION_BLOCKED',
      'EXACT_STATUS':'PARSER_PROJECTION_PARITY_AND_NATIVE_FIXTURES_PASS; ACTIVE_ROUTE_UNCHANGED',
      'GLOBAL_STATUS':'OFFLINE_NATIVE_AND_ISOLATED_ADAPTER_FIXTURES_PASS; REAL_EMBEDDING_SNAPSHOT_COMPONENT_ONLY',
      'PUBLIC_LIBRARY_STATUS':'PATRON_STAFF_READ_ONLY_NATIVE_FUNCTION_FIXTURES_PASS; LIVE_AUTH_UNVERIFIED',
      'PRIVATE_LIBRARY_STATUS':'PATRON_STAFF_READ_ONLY_NATIVE_FUNCTION_FIXTURES_PASS; LIVE_AUTH_UNVERIFIED',
      'PRIVATE_GLOBAL_INDEPENDENCE':'UNLINKED_OWN_BOOK_FIXTURES_PASS_WITH_EMPTY_OR_UNAVAILABLE_GLOBAL; LINKED_GLOBAL_OUTAGE_INDEPENDENCE_UNVERIFIED',
      'AUTHORIZATION_FIXTURE_STATUS':'MOCKED_AUTHORITY_404_AND_TENANT_HYDRATION_ISOLATION_PASS; NO_REAL_SECURITY_QUALIFICATION',
      'LIVE_JWT_MONGO_VERIFIED':False,'NATIVE_CHOICE_DURABILITY':'PREVIEW_ONLY; NO_LIVE_ONE_USE_CAS_OR_COMMIT_QUALIFIED',
      'CURRENT_RUNTIME_HEALTH_VERIFIED':False,'INDEPENDENT_ACCEPTANCE_ELIGIBLE':False,'FRESH_ACCEPTANCE_PERFORMED':False,
      'INDEPENDENT_TYPED_ACCURACY':no_measure,'INDEPENDENT_EXECUTION_ACCURACY':no_measure,
      'INDEPENDENT_FALSE_EXECUTION':no_measure,'INDEPENDENT_MISSED_VALID':no_measure,'INDEPENDENT_CRITICAL_OMISSIONS':no_measure,
      'STRUCTURAL_ISOLATION':'PASS_NO_PRODUCTION_IMPORTS_AND_ALL_PROTECTED_HASHES_MATCH',
      'PRODUCTION_SOURCE_CHANGED':False,'C4_POLICY_CHANGED':False,'FRONTEND_CHANGED':False,
      'MONGO_MUTATIONS':0,'HNSW_REBUILDS':0,'KG_REBUILDS':0,'HELDOUT_EVALUATIONS':0,
      'HISTORICAL_EVIDENCE_PRESERVED':True,'STAGING_READINESS':'BLOCKED','PRODUCTION_READINESS':'BLOCKED',
      'REMAINING_BLOCKERS':blockers,
      'NEXT_AUTHORIZED_ACTION':'FOCUSED_DISABLED_DEVELOPMENT_ON_SOURCE_CORRECTIONS_EXPLICIT_CATEGORY_AND_MULTI_FIELD_OWNERSHIP; SOURCE_ONLY_MASK_REVIEW; NO_NEW_ACCEPTANCE_OR_STAGING_ACTIVATION'
    }
    for field,key in [('DEVELOPMENT_TYPED_ACCURACY','typed_accuracy'),('DEVELOPMENT_EXECUTION_ACCURACY','execution_accuracy'),
                      ('DEVELOPMENT_FALSE_EXECUTION','false_execution'),('DEVELOPMENT_MISSED_VALID','missed_execution'),
                      ('DEVELOPMENT_HARD_FIELD_MISMATCHES','hard_field_mismatch_cases')]:
        qa[field]['historical_exposed540']=history_summary[key]
    # Assert every requested mandatory QA field exists. No silent omissions.
    request=Path(r'C:\Users\balak\.codex\attachments\16a20068-52c3-4768-b1e3-332d591eff9f\Pasted text.txt').read_text(encoding='utf8')
    section=request.split('# 20. Mandatory final QA')[1].split('For every quantitative result')[0]
    required=[s[2:].strip() for s in section.splitlines() if s.startswith('- ')]
    assert not(set(required)-set(qa)),set(required)-set(qa)
    write('search_arch10_final_qa.json',qa)
    gates=dict(development_semantic_safety='KNOWN_FALSE_EXECUTION_FAMILIES_REPAIRED; REALISTIC_EXPOSED_PASS',
        remaining_regression_conflicts='ONE_REPAIRED_ONE_REVIEWED_MIGRATION',registry='SOURCE_REVIEWED_WITH_RECORDED_NATIVE_DEFECT',
        complex_development_reliability='FAIL_LEGACY_EXPOSED_COHORTS',architecture_acceptance_freeze=False,
        scorer_and_masks='INHERITED_SCORER_PRESERVED; NEW_LABEL_REVIEW_APPLIED; HISTORICAL_MASK_ADJUDICATION_INCOMPLETE',
        source_obligations='FINITE_COVERAGE_NOT_COMPLETE_ARBITRARY_ENGLISH',independent_review='SOURCE_ONLY_CONTRACT_AND_DEVELOPMENT_LABEL_REVIEW_AVAILABLE',
        structural_isolation='PASS',independent_acceptance_eligible=False,fresh_acceptance_performed=False,
        preregistered_future_thresholds=dict(typed_accuracy_min=.95,execution_accuracy_min=.99,critical_false_execution_max=0,missed_valid_max=.05,critical_operand_loss_or_invention_max=0),
        threshold_origin='User V10 request; unchanged and not retrospectively selected',scope='FUTURE_INDEPENDENT_QUALIFICATION_NOT_CURRENT_DEVELOPMENT')
    write('search_arch10_acceptance_eligibility.json',gates)
    # Record sources AND transitive candidate dependencies. This is an archival
    # checkpoint; explicitly not a gate-passing freeze for independent acceptance.
    paths=[]
    for folder in ['scratch/search_architecture_v10','scratch/search_arch10_regression','scratch/search_v2c_c5er/candidate_search_v4']:
        paths.extend((ROOT/folder).glob('*.py'))
    paths.extend((ROOT/'scripts').glob('search_arch10*.py'))
    deps=['search_arch10_capability_registry.json','search_arch10_source_contract_review.json','search_arch10_development_label_review.json',
          'search_arch10_realistic_reviewed_r1.jsonl','search_arch9_dev_reviewed.jsonl','search_combined8_reviewed_population_r1.jsonl',
          'search_arch10_pinned_Qwen_LICENSE.txt']
    paths.extend(R/f for f in deps)
    paths.extend(ROOT/p for p in ['scripts/search_combined8_score_adapter.py','scripts/search_v2c_c5er_evaluation_adapter_v2.py'])
    freeze=dict(candidate_id=ID,candidate_disabled=True,status='ARCHIVAL_DEVELOPMENT_CHECKPOINT_NOT_QUALIFICATION_FREEZE',
        architecture_frozen_for_independent_acceptance=False,development_gate='PARTIAL_BLOCKED_BY_COMPLEX_RELIABILITY_AND_MASK_REVIEW',
        generated_at_utc=datetime.now(timezone.utc).isoformat(),source_files={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(set(paths))})
    write('search_arch10_source_freeze.json',freeze)
    artifacts=dict(step1=['search_arch10_integrity.json','search_arch10_capability_registry.json','search_arch10_source_contract_review.json',
        'search_arch10_contract_reconciliation.json','search_arch10_dev72_analysis.json','search_arch10_verified_tests.xml','search_arch10_checkpoint_dev72_results.json',
        'search_arch10_intent_audit.json','search_arch10_source_changes.json',
        'search_arch10_checkpoint_v8exposed205_results.json','search_arch10_source_freeze.json'],
        step2=['search_arch10_native_offline_native_components_final.json','search_arch10_native_retrieval_contracts_final.json',
        'search_arch10_realistic_reviewed_r1.jsonl','search_arch10_checkpoint_realistic_results.json','search_arch10_development_label_review.json',
        'search_arch10_embedding_probe2.json','search_arch10_resource_license_audit.json','search_arch10_performance_verified.json',
        'search_arch10_acceptance_eligibility.json','search_arch10_integration_plan.md','search_arch10_preservation.json','search_arch10_final_qa.json'])
    for files in artifacts.values():assert all((R/f).exists() for f in files)
    artifacts['step1'].extend('search_arch10_verified_'+k+'_results.json' for k in historical)
    consolidated=dict(candidate_id=ID,generated_at_utc=datetime.now(timezone.utc).isoformat(),qa=qa,artifacts=artifacts,
        source_hash_manifest='reports/search_arch10_source_freeze.json',real_embedding_component_timing=embedding,
        historical_exposed540=dict(summary=history_summary,per_cohort={k:v['summary'] for k,v in historical.items()}),
        limitations=blockers,final='PARTIAL',production_readiness='BLOCKED',staging_readiness='BLOCKED')
    write('search_arch10_consolidated_report.json',consolidated)
    def ratio(x):return f"{x['numerator']}/{x['denominator']}"
    readable=f'''# LuminaR Combined V10 engineering report

FINAL = PARTIAL. STEP 1 = implemented, development gates partial. STEP 2 =
disabled workflow implemented and component-tested. Staging and production remain
BLOCKED. Independent acceptance was not performed. Active C4 remains unchanged.

Candidate `{ID}` is disabled. Registry `V10-capability-registry-v2`
is source-audited and explicitly records native limitations. The selected design
is semantic-first deterministic discovery with proven native predicates and
targeted clarification; overall qualification remains PATH_C.

## Measured development evidence

| Population | Typed correct | Execution correct | False execution | Missed valid | Hard-field mismatch cases |
|---|---:|---:|---:|---:|---:|
| Realistic reviewed development, 235 contexts / 47 authored templates | {ratio(realistic['summary']['typed'])} | {ratio(realistic['summary']['execution'])} | {ratio(realistic['summary']['false_execution'])} expected blocked | {ratio(realistic['summary']['missed_valid'])} expected valid | {ratio(realistic['summary']['hard_field_mismatch_cases'])} executed |
| Exposed V9 dev72 | {ratio(dev['summary']['typed_accuracy'])} | {ratio(dev['summary']['execution_accuracy'])} | {ratio(dev['summary']['false_execution'])} expected blocked | {ratio(dev['summary']['missed_execution'])} expected valid | {len(dev['hard_mismatches'])}/{sum(r['execution'] for r in dev['results'])} executed |
| Exposed V8 205 | {ratio(v8['summary']['typed_accuracy'])} | {ratio(v8['summary']['execution_accuracy'])} | {ratio(v8['summary']['false_execution'])} expected blocked | {ratio(v8['summary']['missed_execution'])} expected valid | {len(v8['hard_mismatches'])}/{sum(r['execution'] for r in v8['results'])} executed |
| Historical exposed 540 | {ratio(history_summary['typed_accuracy'])} | {ratio(history_summary['execution_accuracy'])} | {ratio(history_summary['false_execution'])} expected blocked | {ratio(history_summary['missed_execution'])} expected valid | {ratio(history_summary['hard_field_mismatch_cases'])} executed |

All entries are measured exposed DEVELOPMENT comparisons. The realistic cohort
was repaired against its initial results; its perfect development score is not
fresh generalization. It contains 42 short, 3 medium and 2 long templates, each
replicated over five scopes. Full semantic-mask and per-field results, denominator
definitions and length/scope/decision strata are in the JSON report.

V9 dev72 false execution fell from 5/48 to 0/48; valid misses remain
{ratio(dev['summary']['missed_execution'])}. Six remaining raw mismatch cases
concern old hard-category expectations versus semantic topic retention; another
concerns the native complement needed for ONLY format. These are not silently
rescored. Their raw failures and the original ten mismatch cases are preserved
in the source analysis. More supported complex requests still need repair.
The historical 540 replay retains 496/540 typed and 522/540 execution decisions,
with zero false executions in 360 expected-blocked contexts and 18/180 valid
misses. Ten raw field mismatch cases newly flag the ONLY-derived physical
exclusion; native-equivalent projection masks remain a qualification blocker.

The reviewed broad regression population passed {passed}/{len(cases)} nodes with
{failed} failures. Seven original nodes are disclosed deselections: six inherited
reviewed migrations and one newly reviewed title-only containment migration.
Missing pages was repaired to INCOMPLETE without migrating its assertion. V10
includes all 42 inherited metamorphic cases, five compact-extractor tests and
39 new workflow cases; the reconciliation report explains the historical count.
An intermediate unfiltered focused run re-exercised five already migrated typo
notice assertions and failed them; the final reviewed broad run applies the
disclosed migration set and passes. Earlier failed attempts remain preserved.

## Implemented behavior

QueryIntent records original source, Unicode spans, source role, domain, operator,
operand, modality, polarity, ownership, support, relationship, resolution, native
projection and correction provenance. Four channels separate semantic discovery,
mandatory filters, advisory preferences and unresolved requirements; background
is nonoperative. Interpretation remains a proposal, validation checks source
and obligations, and planning projects only validated conditions. Recognizers
have finite linguistic coverage; valid JSON/spans are not complete understanding.

The disabled orchestrator has semantic, structured+semantic, clarification and
unsupported routes. The backend owns scope. The read-only adapter sends semantic
topics/advisory source to retrieval, preserves the QueryPlan, filters canonical
hydrated records before sorting/pagination and verifies serialized results.
Totals describe bounded candidate sets. Negative-only global ONLINE uses actual
fixture entitlements; the native production defect remains unchanged.

Completion/removal reuse the inherited version/source-bound edit contracts.
Additive refinement returns a source/IR/version-bound preview. Owner/session,
library/workspace, mode, expiry and one-use state are checked in pure contracts;
no durable CAS or persistence commit is claimed. The active 150-character choice
and search transports remain unchanged against the 500-character parser limit.

## Native, provider and performance limits

40/40 institutional native-function search fixtures, 8/8 global native-function
search fixtures and 4/4 native choice projections passed. Authority and collections
are fixture doubles. New workflow tests exercise five contexts, negative global
entitlements, foreign hydration, serialization changes, provider errors, source
refinement and EXACT parity. These do not qualify live JWT/Mongo security.

A real cached MiniLM CPU encoder and existing local global snapshot were probed
read-only with a matching model fingerprint. The snapshot has 12 vectors and
is not evidence of the historical five-million-book catalog or current service
health. Twelve encodes of four development queries measured embedding p50
{embedding['p50_ms']:.2f} ms / p95 {embedding['p95_ms']:.2f} ms, including cold first
encode; no independent book relevance oracle exists. No precision, recall or
nDCG is reported. The first probe failed because the guarded Windows environment
omitted USERNAME; the second supplied an ephemeral probe username and passed.
Both attempts are retained. No private data or Mongo operations were used.

Offline parser p50/p95 = {perf['stages']['combined_parser']['p50_ms']:.2f}/
{perf['stages']['combined_parser']['p95_ms']:.2f} ms over 705 samples (235 contexts,
three repeats). Four-worker p95 = {perf['four_worker']['p95_ms']:.2f} ms over 235
samples. Stage, EXACT, scope, complexity, decision and matched V9 timings are in
the performance artifact. These are component measurements, not full-search
latency, an availability claim or a retrospectively chosen production SLO.

The exact cached Qwen revision's license was retrieved from its pinned official
repository and hashed. It is the Qwen Research License, not Apache-2.0. Commercial
clearance is not established. No new Qwen predictions, weights or training were
used. A learned extractor is not required or justified by measured benefit.

## Preservation and next action

{len(pre['protected_files'])}/{len(pre['protected_files'])} protected entries and
{len(v9['source_files'])}/{len(v9['source_files'])} V9 freeze entries match their
recorded hashes. No production/C4/frontend source change, Mongo mutation,
HNSW/KG rebuild, heldout evaluation or activation occurred. The source manifest
is an archival development checkpoint; it is explicitly not an acceptance freeze.

The next authorized action is focused disabled development on source corrections,
explicit category ownership and multi-field phrasing, with source-only historical
mask adjudication. The staging proposal identifies the native negative-format
repair, exact backend/frontend transport files, current authority checks,
durable choice requirements, real relevance qualification and full-service
performance prerequisites. No staging or production deployment is authorized.

## Artifact index

'''
    for group,files in artifacts.items():
        readable+=f'\n{group}:\n\n'
        for f in files:readable+=f'- [{f}]({(R/f).as_posix()})\n'
    readable+='\nAll mandatory final-QA keys are in [search_arch10_final_qa.json]('+ (R/'search_arch10_final_qa.json').as_posix()+').\n'
    with (R/'search_arch10_consolidated_report.md').open('x',encoding='utf8') as f:f.write(readable)
    # Hash every delivered V10 artifact as the final package manifest. The
    # manifest excludes itself to avoid a self-referential digest.
    outputs=sorted(p for p in R.glob('search_arch10*') if p.is_file())
    write('search_arch10_package_manifest.json',dict(candidate_id=ID,status='DISABLED_DEVELOPMENT_PACKAGE',
        files={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in outputs}))
    print(json.dumps(dict(final=qa['FINAL'],regressions_passed=passed,regressions_failed=failed,protected=len(pre['protected_files']),
        mandatory_qa_fields=len(required),artifacts=len(outputs),staging='BLOCKED',production='BLOCKED')))

if __name__=='__main__':main()
