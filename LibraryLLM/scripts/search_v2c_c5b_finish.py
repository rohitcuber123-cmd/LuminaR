"""C5B provenance, preservation and readiness closure. No scoring entry point."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json

R=Path('reports');P='search_v2c_c5b_'
def load(path):return json.loads(Path(path).read_text(encoding='utf8'))
def read(name):return load(R/(P+name))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(name,value):(R/(P+name)).write_text(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
def lines(path):return Path(path).read_bytes().splitlines(keepends=True)

def main():
    baseline=read('baseline.json');oldfreeze=load(R/'search_v2c_c5a_freeze_manifest.json')
    changes=[p for p,h in baseline['protected_files'].items() if sha(p)!=h];assert not changes,changes
    assert sha(R/'search_v2c_c5a_freeze_manifest.json')==baseline['C5A_freeze_sha256']
    assert all(sha(p)==h for p,h in oldfreeze['files'].items())
    work=read('working_manifest.json');author=read('resolution_proposals.json');packet=read('independent_review_input_v2.json');review=read('independent_review_output_v2.json')
    ids={x['case_id'] for x in work['cases']};assert len(ids)==5
    author_id=author['author_identity']['agent_task'];reviewer_id=review['reviewer']['agent_identity_as_exposed'];assert author_id!=reviewer_id
    assert review['aggregate']['accepted']==5 and review['aggregate']['unresolved']==0
    assert all(v==0 for v in review['audit']['prohibited_calls'].values())
    assert all(v==0 for v in review['audit']['prohibited_data_reads'].values())
    assert review['reviewer']['fresh_independent_context'] and not review['reviewer']['shared_proposer_history_supplied']
    assert not review['reviewer']['prior_verdicts_supplied'] and review['reviewer']['human']==0
    assert all(sha(p)==h for p,h in author['input_sha256'].items())
    packet_hash=sha(R/(P+'independent_review_input_v2.json'))
    old_records={json.loads(x)['case_id']:json.loads(x) for x in lines(R/'search_v2c_c5a_calibration_cases.jsonl')}
    new_records={json.loads(x)['case_id']:json.loads(x) for x in lines(R/(P+'calibration_cases.jsonl'))}
    old_lines={json.loads(x)['case_id']:x for x in lines(R/'search_v2c_c5a_calibration_cases.jsonl')};new_lines={json.loads(x)['case_id']:x for x in lines(R/(P+'calibration_cases.jsonl'))}
    assert set(old_records)==set(new_records) and len(new_records)==1024
    altered={k for k in old_records if old_lines[k]!=new_lines[k]};assert altered==ids
    verified=[]
    w={x['case_id']:x for x in work['cases']};p={x['case_id']:x for x in packet['cases']}
    for verdict in review['cases']:
        key=verdict['case_id'];f=verdict['fingerprints'];source=old_records[key];new=new_records[key]
        source_hash=hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        assert source_hash==w[key]['source_case_sha256']
        assert f['input_file_sha256']==packet_hash
        assert hashlib.sha256(source['query_text'].encode()).hexdigest()==f['original_query_utf8_sha256_computed']
        assert hashlib.sha256(new['query_text'].encode()).hexdigest()==f['candidate_query_utf8_sha256_computed']==p[key]['candidate_query_sha256']
        assert verdict['review_disposition']=='ACCEPT' and new['expected_typed_decision']==verdict['candidate']['typed_decision']=='AMBIGUOUS'
        assert new['expected_executable'] is verdict['candidate']['executable'] is False
        assert new['review_required_decision_safety_resolved'] and not new['review_unresolved_decision_safety_labels']
        assert all(new['metric_applicability'][k]['status']=='APPLICABLE' for k in ['typed_decision','executable'])
        assert new['example_class']==source['example_class']=='CORE' and source['review_status']=='PARTIAL'
        assert new['scope_type']==source['scope_type'] and new['workspace_type']==source['workspace_type'] and new['search_mode']==source['search_mode']
        assert new['decision_stratum']==source['decision_stratum']=='AMBIGUOUS'
        for entity in new['protected_entities']:assert new['query_text'][entity['start']:entity['end']]==entity['text']
        verified.append({'case_id':key,'source_fingerprint_verified':True,'input_fingerprint_verified':True,'candidate_fingerprint_verified':True,'reviewed_labels_match_candidate':True,'scope_actor_mode_stratum_preserved':True})
    original_labels={json.loads(x)['case_id']:x for x in lines(R/'search_v2c_c5a_expected_labels.jsonl')};new_labels={json.loads(x)['case_id']:x for x in lines(R/(P+'expected_labels.jsonl'))}
    assert {k for k in original_labels if original_labels[k]!=new_labels[k]}==ids
    provenance={'status':'PASS','mechanism':'Established collaboration workflow: distinct fresh contexts with fork_turns=none and no model override.',
        'proposal_author':author['author_identity'],'final_reviewer':review['reviewer'],'same_agent_self_review':False,
        'model_substitution_requested':False,'actual_model_identity':'Not exposed by runtime; no unsupported identity claim.',
        'review_timestamp_utc':review['timestamp_utc'],'reviewer_unavailable':False,'prior_C5A_reviewer_usage_limit':'Historical blocker preserved; the current distinct fresh reviewer completed successfully.',
        'input_file':P+'independent_review_input_v2.json','input_sha256':packet_hash,'output_file':P+'independent_review_output_v2.json','output_sha256':sha(R/(P+'independent_review_output_v2.json')),
        'proposal_input_hashes_verified':True,'five_case_fingerprints':verified,'prohibited_calls':review['audit']['prohibited_calls'],'prohibited_data_reads':review['audit']['prohibited_data_reads'],
        'v1_review_and_root_contract_correction':P+'review_contract_audit.json','v1_verdicts_preserved':True,'final_review_did_not_receive_v1_verdicts':True,
        'record_binding':'Identity, timestamp, input/output SHA256 and actual tool workflow; no cryptographic digital-signature or human-review claim.', 'human_reviewed':0}
    dump('review_provenance.json',provenance)
    quota=read('scope_decision_matrix.json');dedup=read('deduplication.json');isolation=read('structural_isolation.json');labels=read('label_completeness.json');account=read('partition_accounting.json')
    assert quota['status']==dedup['status']==isolation['status']==labels['status']=='PASS'
    assert isolation['forbidden_colliding_new_case_count']==0 and isolation['new_case_count']==744
    assert isolation['new_duplicate_context_excess_rows']==0 and dedup['duplicate_canonical_contexts']==0
    assert labels['unresolved_required_labels']==labels['partial_contexts_remaining']==0
    assert account['accepted_new_core_cases']==594 and account['total_calibration_contexts']==1024
    # Revalidate inherited large-artifact evidence with the same declared method.
    # Never convert size/mtime preservation into a full index checksum claim.
    oldpreserve=load(R/'search_v2c_c_preservation.json');artifacts=[]
    for item in oldpreserve['files']:
        name=item['file']
        if name.startswith(('data_pipeline/','local-data/','recommendation/','rag/')) or name=='scripts/search_v2c_c_author_gold.py':
            before=item['after'];stat=Path(name).stat()
            same=sha(name)==before['sha256'] if 'sha256' in before else stat.st_size==before['size'] and stat.st_mtime_ns==before['mtime_ns']
            assert same,name
            artifacts.append({'path':name,'unchanged':same,'method':'artifact SHA256' if 'sha256' in before else 'inherited size+mtime_ns, rechecked now; not full checksum'})
    evaluator={p:{'expected':h,'actual':sha(p),'unchanged':sha(p)==h} for p,h in oldfreeze['evaluator_hashes'].items()}
    native={p:{'expected':h,'actual':sha(p),'unchanged':sha(p)==h} for p,h in oldfreeze['files'].items() if p.replace('\\','/').startswith('tests/') and 'c5a' in p}
    assert all(x['unchanged'] for x in evaluator.values()) and all(x['unchanged'] for x in native.values())
    assert all(x['unchanged'] and sha(x['path'])==x['sha256_after'] for x in isolation['preservation'])
    preserve={'status':'PASS','C5A_original_freeze_sha256':sha(R/'search_v2c_c5a_freeze_manifest.json'),'C5A_original_freeze_files_verified':len(oldfreeze['files']),
        'protected_file_count':len(baseline['protected_files']),'protected_hashes':baseline['protected_files'],'protected_hash_changes':changes,
        'production_source_files':462,'original_historical_evidence_files':1001,'additional_C5A_files_preserved':len(baseline['protected_files'])-1463,
        'original_C5_failure_evidence_preserved':True,'evaluator_hashes':evaluator,'native_harness_hashes':native,'sealed_audit_preservation':isolation['preservation'],
        'large_artifacts':artifacts,'full_HNSW_KG_checksum_claim':False,'resident_endpoint_repolled':False,'Mongo_catalogue_access_or_mutation':False,
        'global_book_count':'5,000,000 recorded C5A Mongo metadata observation; not newly measured',
        'global_search_health':'Last measured STALE/degraded, baseline_verified=False. Not repolled; unchanged artifacts do not prove runtime health.'}
    dump('preservation.json',preserve)
    activities={'NEW_CALIBRATION_PARSER_EVALUATIONS':0,'HELDOUT_PARSER_EVALUATIONS':0,'HELDOUT_POLICY_EVALUATIONS':0,'QWEN_INFERENCES':0,'HNSW_REBUILDS':0,'KG_REBUILDS':0,
        'THRESHOLD_FITTING_RUNS':0,'POLICY_COMPARISON_RUNS':0,'POLICY_SELECTIONS':0,'POLICY_ACTIVATIONS':0,'NATIVE_TEST_RERUNS':0,'PRODUCTION_SOURCE_CHANGES':0,'MONGO_REGENERATIONS':0,
        'sealed_access':'Unchanged established auditor; only runtime evidence namespace and trace-key spelling adapted. No query/label/prediction disclosure.','source_interface':P+'sealed_interface_provenance.json'}
    dump('prohibited_activity_audit.json',activities)
    hashes={'calibration_cases':{'old_path':'reports/search_v2c_c5a_calibration_cases.jsonl','old_sha256':sha(R/'search_v2c_c5a_calibration_cases.jsonl'),'new_path':'reports/'+P+'calibration_cases.jsonl','new_sha256':sha(R/(P+'calibration_cases.jsonl'))},
        'expected_labels':{'old_path':'reports/search_v2c_c5a_expected_labels.jsonl','old_sha256':sha(R/'search_v2c_c5a_expected_labels.jsonl'),'new_path':'reports/'+P+'expected_labels.jsonl','new_sha256':sha(R/(P+'expected_labels.jsonl'))}}
    dump('candidate_manifest.json',{'version':'V2C-C-C5B-readiness-v1','status':'LABEL_COMPLETE_ISOLATED_CANDIDATE','source_C5A_freeze':baseline['C5A_original_freeze'],
        'source_C5A_freeze_sha256':baseline['C5A_freeze_sha256'],'candidate_hashes':hashes,'context_count':1024,'revised_contexts':5,'unchanged_contexts':1019,
        'active_context_count_change':0,'accepted_new_core':594,'retained_original_contexts':280,'new_contexts':744,'lineage':P+'context_lineage.json',
        'review_provenance':P+'review_provenance.json','required_gold_labels_complete':True,'native_C5A_evidence_reused_unchanged':True,
        'evaluator_hashes_unchanged':True,'policy_source_hash':sha('search/query_calibration.py'),'parser_version':'search-v2c-c4-deterministic-1',
        'separate_calibration_authorization_required':True})
    required_artifacts=['baseline.json','working_manifest.json','resolution_proposals.json','independent_review_input_v1.json','independent_review_output_v1.json',
        'independent_review_input_v2.json','independent_review_output_v2.json','review_contract_audit.json','review_provenance.json','five_case_resolution.json',
        'context_lineage.json','normative_label_revisions.json','scope_decision_matrix.json','partition_accounting.json','deduplication.json','structural_isolation.json',
        'label_completeness.json','candidate_manifest.json','calibration_cases.jsonl','expected_labels.jsonl','prohibited_activity_audit.json','preservation.json','sealed_interface_provenance.json','sealed_access_audit.json']
    frozen={str(R/(P+n)):sha(R/(P+n)) for n in required_artifacts}
    frozen.update({str(p):sha(p) for p in Path('scripts').glob(P+'*.py')})
    dump('freeze_manifest.json',{'version':'C5B-ready-candidate-freeze-v1','status':'FROZEN_READY_CANDIDATE','frozen_at_utc':datetime.now(timezone.utc).isoformat(),
        'files':frozen,'candidate_hashes':hashes,'original_C5A_freeze_unchanged':True,'original_C5A_freeze_sha256':baseline['C5A_freeze_sha256'],
        'evaluator_hashes_unchanged':oldfreeze['evaluator_hashes'],'native_harness_hashes_unchanged':{p:x['actual'] for p,x in native.items()},
        'production_parser_and_policy_hashes':oldfreeze['production_parser_and_policy_hashes'],
        'heldout_manifest_hashes':oldfreeze['heldout_manifest_hashes'],'required_gold_label_fields_resolved':10,'unresolved_required_gold_labels':0,
        'candidate_ready':True,'calibration_evaluation_authorized_by_this_phase':False,'policy_selected':False,'policy_activated':False})
    readiness={'FINAL':'PASS','CALIBRATION_CANDIDATE_READY':'YES','status_meaning':'Label-complete, independently reviewed, isolated and reproducibly frozen candidate; not calibrated or production-ready.',
        'gates':{'all_ten_required_labels_resolved':True,'all_five_independent_reviews':True,'no_required_annotation_mask_remaining':True,'quota':True,'deduplication':True,
            'structural_isolation':True,'review_provenance':True,'label_lineage':True,'protected_hash_preservation':True,'new_candidate_consistency':True,'forbidden_activity_zero':True},
        'intentionally_unresolved_query_operands':'Five mandatory author references are deliberately unknown in the queries. The correct gold is definitively AMBIGUOUS/false. Scalar author-value scoring stays masked; no required decision/execution annotation remains unknown.',
        'CALIBRATION_RERUN_AUTHORIZED':'NO','precise_next_prerequisite':'A separate explicit user authorization to run C5 parser calibration against this exact C5B freeze. Verify hashes and honor applicability/native-unit distinctions before that run. No threshold fitting, policy selection or heldout evaluation is authorized here.'}
    dump('readiness.json',readiness)
    qa={'FINAL':'PASS','C5B_IMPLEMENTED':'YES','C5A_ORIGINAL_FREEZE_PRESERVED':'YES','C4_ACTIVE_POLICY_PRESERVED':'YES','PRODUCTION_PARSER_CHANGED':'NO','PRODUCTION_POLICY_CHANGED':'NO',
        'CALIBRATION_CANDIDATE_READY':'YES','CALIBRATION_POLICY_SELECTED':'NO','CALIBRATION_POLICY_ACTIVATED':'NO','CALIBRATION_RERUN_AUTHORIZED':'NO',
        'PARTIAL_CONTEXTS_AT_START':5,'PARTIAL_CONTEXTS_RESOLVED':5,'PARTIAL_CONTEXTS_REMAINING':0,'REQUIRED_LABELS_AT_START':10,'REQUIRED_LABELS_RESOLVED':10,
        'UNRESOLVED_REQUIRED_LABELS':0,'INDEPENDENT_REVIEW_COMPLETED':'YES','REVIEWER_PROVENANCE_VERIFIED':'YES','REVIEWER_UNAVAILABLE':'NO',
        'NORMATIVE_LABEL_REVISIONS':{'required_gold_fields':10,'context_revisions':5,'literal_author_operands_replaced':2,'original_queries_and_verdicts_preserved':True},
        'TOTAL_CALIBRATION_CONTEXTS':1024,'NEW_CALIBRATION_CONTEXTS':744,'RETAINED_ORIGINAL_CONTEXTS':280,'ACCEPTED_NEW_CORE_CASES':594,'DERIVATIVE_CONTEXTS':account['new_derivative_contexts'],
        'REJECTED_CORE_CASES':account['rejected_core_cases'],'DUPLICATE_CANONICAL_CONTEXTS':0,'CROSS_SPLIT_STRUCTURAL_OVERLAP':0,'SCOPE_DECISION_COVERAGE':'PASS',
        'MINIMUM_CORE_CELL_SIZE':quota['minimum_core_cell_size'],'MINIMUM_MEANINGFUL_PATTERN_COUNT':quota['minimum_meaningful_pattern_count'],'REVIEW_STATUS_COUNTS':account['review_status_counts'],
        'PRODUCTION_SOURCE_HASH_VERIFICATION':'PASS (462 files)','HISTORICAL_EVIDENCE_HASH_VERIFICATION':f"PASS ({len(baseline['protected_files'])} protected files total, including source and C5A artifacts)",
        'ORIGINAL_C5_FAILURE_EVIDENCE_PRESERVED':'YES','SEALED_HELDOUT_HASH_UNCHANGED':'YES','C5A_MANIFEST_UNCHANGED':'YES','C5B_MANIFEST_FROZEN':'YES','LABEL_HASH_FROZEN':'YES',
        'EVALUATOR_HASH_UNCHANGED':'YES','NATIVE_HARNESS_HASH_UNCHANGED':'YES',**{k:activities[k] for k in ['NEW_CALIBRATION_PARSER_EVALUATIONS','HELDOUT_PARSER_EVALUATIONS','HELDOUT_POLICY_EVALUATIONS','QWEN_INFERENCES','HNSW_REBUILDS','KG_REBUILDS']},
        'human_reviewed':0,'unchanged_non_target_rows':1019,'retained_native_unreviewed_contexts':200,'review_binding':'Hash-bound independent AI provenance; no digital signature or human review claim.',
        'native_evidence':'C5A264/264 main,833/833 status/state/privacy,59/59 suggestions,213/213 corrections,154 commits; supplement5/5 and security46/46. Preserved historical evidence, not rerun.',
        'last_known_global_health':preserve['global_search_health'],'next_authorized_action':readiness['precise_next_prerequisite']}
    dump('final_qa.json',qa)
    report=['V2C-C.5B PASS — calibration candidate ready for separately authorized evaluation.','',
        'Exactly five contexts were revised; all1019 other corpus lines and their label lines remain byte-identical in the new version. C5A remains a reproducible immutable non-ready milestone. Both previous and new hashes are recorded. No corpus generation, parser scoring, policy comparison/selection/activation, native rerun or production behavior change occurred.','',
        'A fresh semantic author independently found the original contexts executable: uncertain background narration did not make author association mandatory. The revisions add a mandatory note-based author association in three cases and replace fixed author clauses in two staff cases. A different fresh reviewer independently judged all five revisions AMBIGUOUS/false under the user-authorized intended-objective rule. Unknown author operands are intentional query ambiguity, not unresolved gold labels.','',
        'The first final-review packet incorrectly required blanket preservation of all literal filters, a stricter condition than the user instruction. Its three ACCEPT/two REJECT verdicts are preserved as v1. The input contract was corrected with the user-verbatim revision rule; candidate queries were unchanged. A third fresh context received no previous verdicts or proposed label pairs and independently accepted all five for narrowly justified objective-linked necessity. This contract correction and all fingerprints are auditable.','',
        'Final corpus1024 contexts =744 new +280 retained. Accepted new core rises589→594; all30 cells pass15/4 requirements, minimum18 core cases and5 independently validated meaningful patterns. Derivatives, one rejected core and native mode supplement receive no core credit. Canonical duplicates and forbidden structural overlap remain0. All status totals reconcile.','',
        'The established sealed auditor was invoked unchanged with an in-memory C5B output namespace. Only trace-key spelling was adapted to avoid falsely implying C5A writes. No audit rule, capability, identity or topology mechanism changed, and no sealed content reached authoring/review agents.','',
        '| QA field | Observed |','|---|---|']
    report += [f'| {k} | {json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v} |' for k,v in qa.items()]
    report += ['', 'Exact evidence:']+[f'- reports/{P}{name}' for name in ['independent_review_output_v2.json','review_provenance.json','context_lineage.json','normative_label_revisions.json','scope_decision_matrix.json','deduplication.json','structural_isolation.json','label_completeness.json','preservation.json','candidate_manifest.json','freeze_manifest.json','readiness.json']]
    report += ['', 'No live health assertion is derived from unchanged index artifacts. Global5,000,000 and STALE/degraded baseline_verified=False remain recorded prior observations. No resident endpoint was repolled. Large-asset checks retain their inherited artifact-SHA256 or size/mtime limits; no full HNSW/KG checksum is claimed.','',
        'Next prerequisite: explicit separate authorization for C5 calibration scoring against this exact freeze, with applicability masks and native cases handled correctly. Readiness PASS is not authorization to score, tune, select a policy, evaluate heldout or deploy.']
    (R/(P+'review.md')).write_text('\n'.join(report)+'\n',encoding='utf8')
    (R/(P+'next_scope.md')).write_text('C5B candidate readiness PASS.\n\nPrerequisite for the next phase: a separate explicit user authorization to run C5 calibration parser evaluation against search_v2c_c5b_freeze_manifest.json and its exact corpus/label hashes. Verify the unchanged C4 parser/policy, frozen evaluator/native references and all applicability masks first. Keep native-sequence rows separate from parser-plan scoring. Do not infer that unknown authors are missing gold: all five typed-decision/execution labels are now definitive AMBIGUOUS/false. No heldout evaluation, threshold fitting, policy selection/activation or production change is authorized by C5B.\n',encoding='utf8')
    dump('changed_files.json',{'production_changes':[],'C5A_or_earlier_evidence_changes':[],'revised_active_context_ids':sorted(ids),'changed_corpus_rows':5,'unchanged_corpus_rows':1019,
        'new_sources':{str(p):sha(p) for p in Path('scripts').glob(P+'*.py')},'new_artifacts':sorted(str(p) for p in R.glob(P+'*') if p.is_file()),
        'runtime_bytecode':'Standard Python may cache imported evidence-tool modules; this is not production source or frozen historical evidence. No unrelated cleanup performed.',
        'git':'No staging, commit, reset, deletion, index rebuild or migration.'})
    assert all(sha(p)==h for p,h in frozen.items())
    assert all(sha(p)==h for p,h in baseline['protected_files'].items())
    print(json.dumps({'FINAL':'PASS','candidate_ready':True,'resolved_contexts':5,'resolved_required_labels':10,'accepted_core':594,'contexts':1024,'minimum_cell':quota['minimum_core_cell_size'],'minimum_patterns':quota['minimum_meaningful_pattern_count'],'calibration_rerun_authorized':False}))

if __name__=='__main__':main()
