"""C5A evidence closure and non-ready freeze. No parser/policy scoring."""
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json

R=Path('reports');P='search_v2c_c5a_'
def read(name):return json.loads((R/(P+name)).read_text(encoding='utf8'))
def rows(path):return [json.loads(x) for x in Path(path).read_text(encoding='utf8').splitlines() if x.strip()]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(name,value):(R/(P+name)).write_text(json.dumps(value,indent=2,default=str)+'\n',encoding='utf8')
def agreement(value):return f"{value['numerator']}/{value['denominator']}"

def main():
    base=read('baseline.json');changed_source=[p for p,h in base['production_source_hashes'].items() if sha(p)!=h]
    changed_history=[p for p,h in base['historical_evidence_hashes'].items() if sha(p)!=h]
    assert not changed_source and not changed_history,(changed_source,changed_history)
    c4=json.loads((R/'search_v2c_c4_freeze.json').read_text());assert all(sha(p)==h for p,h in c4['files'].items())
    family=read('family_isolation.json');assert family['status']=='PASS' and family['cross_split_structural_overlap']==0
    corpus=rows(R/(P+'calibration_cases.jsonl'));account=read('partition_accounting.json');matrix=read('scope_decision_matrix.json');review=read('core_review.json')
    assert len(corpus)==account['total_repaired_calibration_contexts']==1024
    assert sha(R/(P+'reviewed_draft.jsonl'))==review['reviewed_draft_sha256']
    eligible=[r for r in corpus if r.get('example_class')=='CORE' and r.get('review_status')=='AI_REVIEWED' and r.get('review_complete') is True]
    partial=[r for r in corpus if r.get('example_class')=='CORE' and r.get('review_required_decision_safety_resolved') is False]
    unresolved=[{'case_id':r['case_id'],'scope':r['scope_type'],'labels':r['review_unresolved_decision_safety_labels'],'metric_applicability':r['metric_applicability']} for r in partial]
    assert len(eligible)==account['new_independently_reviewed_core']==589
    assert all(r.get('review_required_decision_safety_resolved') is True for r in eligible)
    native=read('native_results.json');modes=read('native_modes_results.json');security=read('security_regression.json');audit=read('harness_failure_audit.json');missing=read('native_missing_contexts.json')
    post=read('native_independent_postrun_review.json')
    assert native['status']=='PASS_NATIVE_INFRASTRUCTURE_ONLY' and modes['status']=='PASS' and security['status']=='PASS'
    for name in ['status_oracle','state_oracle','privacy_oracle','suggestion_issuance_oracle','correction_issuance_oracle']:
        assert native[name]['numerator']==native[name]['denominator'] and native[name]['denominator']>0
    assert missing['completed']==10 and audit['audited']==66
    write('review_readiness.json',{'status':'PARTIAL_REQUIRED_DECISION_LABELS_UNRESOLVED','independent_review_records_preserved':True,
        'reviewed_core_eligible_after_isolation':len(eligible),'partial_context_count':len(partial),'unresolved_required_label_fields':sum(len(x['labels']) for x in unresolved),
        'cases':unresolved,'quota_credit_for_partial_cases':0,'unresolved_labels_used_as_gold':False,
        'review_service_interruption':'Reviewer wrote all600 independent per-case verdicts and hashes, then service usage limit prevented a follow-up revision cycle. No root-authored substitution was made for independent gold.',
        'next_action':'Independently revise or resolve the five mapping-note contexts, review revised semantics and re-audit their family isolation before declaring inputs ready.'})
    hold={'status':'PASS','heldout_parser_evaluations':0,'heldout_policy_evaluations':0,'heldout_evaluator_invocations':0,
        'author_or_semantic_reviewer_heldout_exposure':False,'heldout_predictions_accessed':False,'sealed_structural_audit_permitted':True,
        'sealed_access_audit':P+'sealed_access_audit.json','preservation':family['preservation'],
        'discarded_new_candidates':family['discarded_new_case_ids'],'final_new_context_forbidden_overlap':0,'original_heldout_population_unchanged':True}
    assert all(x['unchanged'] for x in family['preservation'])
    write('holdout_preservation.json',hold)
    prior=json.loads((R/'search_v2c_c_preservation.json').read_text());artifacts=[]
    for item in prior['files']:
        p=item['file']
        if p.startswith(('data_pipeline/','local-data/','recommendation/','rag/')) or p=='scripts/search_v2c_c_author_gold.py':
            before=item['after'];s=Path(p).stat()
            same=sha(p)==before['sha256'] if 'sha256' in before else s.st_size==before['size'] and s.st_mtime_ns==before['mtime_ns']
            assert same,p
            artifacts.append({'path':p,'unchanged':same,'method':'SHA256' if 'sha256' in before else 'size+mtime_ns; no fresh full index checksum'})
    write('source_preservation.json',{'status':'PASS','production_source_files':len(base['production_source_hashes']),'historical_evidence_files':len(base['historical_evidence_hashes']),
        'production_changes':changed_source,'historical_report_changes':changed_history,'production_source_hashes':base['production_source_hashes'],
        'historical_evidence_hashes':base['historical_evidence_hashes'],'large_artifacts':artifacts,'C4_freeze_still_matches':True,
        'calibration_parser_evaluations':0,'new_policy_evaluations':0,'production_hnsw_or_kg_builds':0,'fixture_hnsw_or_kg_builds':0,
        'auth_journal':'Native attempts and smoke use separate C5A LUMINAR_SESSION_DB paths; resident production journal not used.',
        'resident_http_access':False,'full_index_checksum_claim':False,'models_or_Qwen_called':False})
    # Explicitly freeze the current non-ready inputs; freeze does not authorize
    # scoring or convert unresolved fields into definitive gold.
    report_inputs=['calibration_cases.jsonl','expected_labels.jsonl','capability_matrix.json','family_assignments.json','label_provenance.json','core_review.json','reviewed_draft.jsonl','author_draft.jsonl',
        'scope_decision_matrix.json','partition_accounting.json','family_isolation.json','native_oracles.json','native_missing_contexts.json','harness_failure_audit.json','harness_v2.json',
        'native_independent_review.json','native_independent_postrun_review.json','native_modes_oracles.json','native_modes_independent_review.json','native_modes_results.json','native_results.json','security_regression.json','review_readiness.json']
    paths={str(R/(P+n)) for n in report_inputs if (R/(P+n)).is_file()}
    paths.update(str(p) for p in Path('scripts').glob(P+'*.py'))
    paths.update(str(p) for p in Path('tests/institution_v2g').glob('test_query_v2c_c5a*.py'))
    paths.update(str(p) for p in Path('tests/institution_v2g').glob('*c5a*.py'))
    paths.update([native['raw_observations'],modes['raw_file'],'scripts/search_v2c_c4_evaluate.py','scripts/search_v2c_c_evaluate.py','scripts/search_v2c_c5_baseline.py'])
    frozen={p:sha(p) for p in sorted(paths)}
    write('freeze_manifest.json',{'version':'C5A-candidate-input-freeze-v1','frozen_at_utc':datetime.now(timezone.utc).isoformat(),'client_date':'2026-10-25',
        'status':'FROZEN_NON_READY_CANDIDATE','calibration_rerun_authorized':False,'reason':'Five contexts retain ten unresolved required decision/execution labels.',
        'files':frozen,'production_parser_and_policy_hashes':{p:h for p,h in c4['files'].items() if p.startswith('search/')},
        'accepted_C4_freeze_sha256':sha(R/'search_v2c_c4_freeze.json'),'accepted_policy_sha256':sha('search/query_calibration.py'),
        'label_hash':sha(R/(P+'expected_labels.jsonl')),'calibration_corpus_hash':sha(R/(P+'calibration_cases.jsonl')),
        'evaluator_version':'C5A schema/accounting and sealed structural validator v1; accepted C4/C5 scorer source hashes frozen for separate future calibration driver',
        'evaluator_hashes':{p:sha(p) for p in ['scripts/search_v2c_c5a_manifest.py','scripts/search_v2c_c5a_sealed_audit.py','scripts/search_v2c_c4_evaluate.py','scripts/search_v2c_c5_baseline.py']},
        'native_harness_version':read('harness_v2.json')['version'],'native_fixture_spec':P+'native_oracles.json#fixtures',
        'heldout_manifest_hashes':{x['path']:x['sha256_after'] for x in family['preservation'] if 'manifest' in x['path']},
        'new_calibration_parser_evaluations':0,'new_policy_evaluations':0,'heldout_parser_evaluations':0,'heldout_policy_evaluations':0})
    snapshot=read('catalogue_snapshot.json');health=snapshot['previous_live_health'];classes=audit['classifications']
    qa={'FINAL':'PARTIAL','C5A_IMPLEMENTED':'YES','C4_ACTIVE_POLICY_PRESERVED':'YES','PRODUCTION_PARSER_CHANGED':'NO','PRODUCTION_POLICY_CHANGED':'NO',
        'CALIBRATION_POLICY_SELECTED':'NO','CALIBRATION_POLICY_ACTIVATED':'NO','CALIBRATION_PARSER_EVALUATIONS':'0 new evaluations','HELDOUT_PARSER_EVALUATIONS':0,'HELDOUT_POLICY_EVALUATIONS':0,
        'ORIGINAL_C5_CALIBRATION_CASES':'50 evaluated parser cases','NEW_CALIBRATION_CORE_CASES':len(eligible),'NEW_CALIBRATION_UNIQUE_CONTEXTS':account['new_unique_calibration_contexts'],
        'TOTAL_REPAIRED_CALIBRATION_CONTEXTS':len(corpus),'MINIMUM_SCOPE_DECISION_COVERAGE':matrix['status'],
        'INDEPENDENT_AI_REVIEWED':len(eligible),'HUMAN_REVIEWED':0,'UNREVIEWED':sum(r['review_status']=='UNREVIEWED' for r in corpus),
        'PARTIALLY_REVIEWED':len(partial),'UNRESOLVED_REQUIRED_LABELS':sum(len(x['labels']) for x in unresolved),'UNRESOLVED_REQUIRED_LABEL_CONTEXTS':len(partial),
        'REJECTED_CORE_DIVERSITY':sum(r['review_status']=='REJECTED_CORE_DIVERSITY' for r in corpus),'DUPLICATE_CANONICAL_CONTEXTS':0,'CROSS_SPLIT_STRUCTURAL_OVERLAP':0,
        'TEN_MISSING_NATIVE_CONTEXTS_COMPLETED':'10/10','ORIGINAL_NATIVE_HARNESS_ASSERTIONS_FAILED':'66 historical','HARNESS_FAILURES_AUDITED':'66/66',
        'HARNESS_DEFECTS_CONFIRMED':classes.get('TEST_ADAPTER_DEFECT',0),'FIXTURE_DEFECTS_CONFIRMED':classes.get('FIXTURE_DEFECT',0),
        'STALE_EXPECTATIONS_CONFIRMED':audit['stale_historical_contract'],'ACTUAL_APPLICATION_DEFECTS_CONFIRMED':audit['actual_application_defects'],'INDETERMINATE_FAILURES':audit['indeterminate'],
        'REVIEWED_NATIVE_HARNESS':'PASS','NATIVE_STATUS_ORACLE':agreement(native['status_oracle']),'NATIVE_STATE_ORACLE':agreement(native['state_oracle']),
        'NATIVE_PRIVACY_ORACLE':agreement(native['privacy_oracle']),'SUGGESTION_ISSUANCE_ORACLE':agreement(native['suggestion_issuance_oracle']),'CORRECTION_ISSUANCE_ORACLE':agreement(native['correction_issuance_oracle']),
        'B1_SECURITY_REGRESSION':security['B1'],'C1_WORKSPACE_REGRESSION':security['C1'],'PRIVATE_OUTSIDER_CONCEALMENT':security['private_outsider_concealment'],
        'CALIBRATION_MANIFEST_FROZEN':'YES','LABEL_HASH_FROZEN':'YES','EVALUATOR_HASH_FROZEN':'YES','NATIVE_HARNESS_HASH_FROZEN':'YES','HELDOUT_HASH_UNCHANGED':'YES',
        'GLOBAL_BOOK_COUNT':snapshot['global_book_count'],'GLOBAL_SEARCH_HEALTH':f"{health['index_status']} / {health['status']}; baseline_verified={health['baseline_verified']} (last C5 live snapshot; immutable artifacts verified; resident endpoint not repolled)",
        'HNSW_REBUILT':'NO','KG_REBUILT':'NO','MODEL_CHANGED':'NO','QWEN_CHANGED':'NO','RECOMMENDATION_CHANGED':'NO','MORE_LIKE_THIS_CHANGED':'NO','STAFF_INVENTORY_CHANGED':'NO','PART_2I_STARTED':'NO','CALIBRATION_RERUN_AUTHORIZED':'NO'}
    order=['CLEAR_EXECUTABLE','SAFE_UNCERTAIN_EXECUTABLE','AMBIGUOUS','INCOMPLETE','UNSUPPORTED','CONTRADICTORY']
    global_names=['GLOBAL_CLEAR_EXECUTABLE','GLOBAL_SAFE_UNCERTAIN','GLOBAL_AMBIGUOUS','GLOBAL_INCOMPLETE','GLOBAL_UNSUPPORTED','GLOBAL_CONTRADICTORY']
    for label,stratum in zip(global_names,order):qa[label]=matrix['matrix']['GLOBAL'][stratum]['reviewed_new_core']
    for label,scope in [('PUBLIC_PATRON_STRATA','PUBLIC_TENANT_PATRON'),('PUBLIC_STAFF_STRATA','PUBLIC_TENANT_STAFF'),('PRIVATE_PATRON_STRATA','PRIVATE_TENANT_PATRON'),('PRIVATE_STAFF_STRATA','PRIVATE_TENANT_STAFF')]:
        qa[label]={s:matrix['matrix'][scope][s]['reviewed_new_core'] for s in order}
    qa.update(strata_order=order,new_authored_core_before_review=600,new_derivatives_retained=account['new_derivatives'],retained_old_calibration_contexts=280,
        raw_review_status_counts=dict(Counter(r['review_status'] for r in corpus)),independently_reviewed_core_count_scope='New core only; retained C3 fifty and native review provenance are separate, not added to the589 count.',
        discarded_new_sealed_collisions=6,native_main_sequences=264,native_mode_supplement='5/5 disjoint native EXACT/SMART flows,15 additional API boundaries; zero parser-core credit.',
        security_smoke='46/46; separate from main264 counts',freeze_status='FROZEN_NON_READY_CANDIDATE',
        blocking_reasons=['Five independently reviewed mapping-note cases retain unresolved required typed-decision/execution labels (ten fields). No unknown label is made definitive by the freeze.','Independent follow-up review/revision could not complete after the reviewer service usage limit; retained v1 verdicts are not silently replaced.'],
        application_defects_found=0,completed_at_utc=datetime.now(timezone.utc).isoformat())
    write('final_qa.json',qa)
    lines=['V2C-C.5A PARTIAL. Calibration policy selection remains blocked.','',
        'The repaired candidate contains1024 logical calibration contexts:744 new contexts plus280 retained original contexts. The744 new rows comprise589 accepted independently reviewed core cases,149 unreviewed derivatives,5 partially reviewed core cases and1 rejected value-only core diversity example. Six new candidates were discarded for heldout structural collisions; no heldout case was moved, rewritten or disclosed.','',
        'All30 scope/decision cells meet the15-core/4-pattern requirement after independent review and isolation. Minimum accepted cell size is17; minimum independently validated meaningful pattern count is5. Five partial contexts remain excluded from quota credit and decision/execution gold. Their ten required labels remain explicitly masked; this is a non-ready freeze, not calibration authorization.','',
        'The independent reviewer inspected all600 authored core cases, amended29 normative label sets before parser output, accepted594 before isolation, left5 partial and rejected1 value-only example. Five accepted core cases and one derivative were then removed by the sealed audit, leaving589 accepted core cases. All uncertainty is semantic; no target confidence floats or parser-produced gold were authored.','',
        'Native repair is complete: all10 exact missing contexts; all66 historical failures individually classified (22 adapter defects,44 fixture defects); main264/264 scenarios,833/833 status/state/privacy boundaries,59/59 suggestion issuances,213/213 genuine correction issuances and154 authorized commits. The independent reviewer signed oracles before execution and recomputed evidence after execution. Original C5 failures remain historical FAIL. Retries/probes are preserved and excluded from final denominators.','',
        'A separate five-scope supplement passes5/5 explicitEXACT versus genuineSMART correction flows with15 additional boundaries. It receives no parser-calibration core credit. All new parser-core modes remainSMART because established literal-mode structural families are already exposed in development. Accepted B1/C1/security smoke passes46/46 without production or fixture HNSW/KG builds.','',
        'Global book count is5,000,000 by Mongo metadata. Health is the last measured C5 STALE/degraded, baseline_verified=False snapshot, with index artifacts verified unchanged. The resident endpoint was deliberately not repolled to preserve historical runtime logs byte-for-byte; no fresh live-health measurement is claimed.','',
        '| QA field | Observed |','|---|---|']
    lines += [f'| {k} | {json.dumps(v) if isinstance(v,(dict,list)) else v} |' for k,v in qa.items() if k not in ['blocking_reasons']]
    lines += ['', 'Blocking requirements:']+[f'- {x}' for x in qa['blocking_reasons']]
    lines += ['', 'Production source462 files and historical evidence1001 files match their initial hashes. Large artifact preservation uses SHA256 or inherited size/mtime where available; no new full-index checksum claim. All corrected inputs and oracles are versioned and hashed. No repaired-corpus parser scoring, policy evaluation/selection, heldout scoring, Qwen/model inference, frontend work or Part2I occurred.']
    (R/(P+'review.md')).write_text('\n'.join(lines)+'\n',encoding='utf8')
    (R/(P+'next_scope.md')).write_text('V2C-C.5A PARTIAL. Calibration policy selection remains blocked.\n\nResolve the five mapping-note contexts listed in review_readiness.json through independent query-spec clarification or independently authored versioned replacements, then independently review their typed-decision/execution labels. Preserve current draft, review and masks. Re-audit only changed new cases for structural/context isolation, reassemble counts and refreeze. Do not promote unresolved labels based on parser outputs. Native repair is already complete; no production patch is indicated. Do not rerun C5, evaluate heldout or select a policy under this task. A later separate authorization may rerun calibration only after readiness closure.\n',encoding='utf8')
    sources=[str(p) for p in Path('scripts').glob(P+'*.py')]+[str(p) for p in Path('tests/institution_v2g').glob('*c5a*.py')]
    artifacts=[str(p) for p in R.rglob('*') if p.is_file() and (p.name.startswith(P) or any(part.startswith(P) for part in p.parts))]
    write('changed_files.json',{'production_changes':[],'historical_report_changes':[],'new_sources':{p:sha(p) for p in sorted(set(sources))},'new_artifacts':sorted(artifacts),
        'git':'No staging, commit, reset, migration, index rebuild or destructive cleanup.','fixture_scope':'Random isolated Mongo databases and separate C5A session journals; resident production records not changed.'})
    assert all(sha(p)==h for p,h in frozen.items()),'Frozen candidate changed during closure'
    print(json.dumps({'FINAL':'PARTIAL','reviewed_core':len(eligible),'total_contexts':len(corpus),'matrix':matrix['status'],'unresolved_contexts':len(partial),'unresolved_required_labels':qa['UNRESOLVED_REQUIRED_LABELS'],'native':'PASS','calibration_rerun_authorized':False}))

if __name__=='__main__':main()
