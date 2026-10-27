"""Truthful C5E completion, preservation verification and evidence freeze.

No parser calls, database operations, candidate changes or acceptance retries.
"""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib,json,xml.etree.ElementTree as ET
R=Path('reports');P='search_v2c_c5e_';ROOT=Path.cwd()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def rows(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf8').splitlines() if s.strip()]
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf8') as f:json.dump(v,f,sort_keys=True,indent=2,ensure_ascii=False)
def rate(n,d):return {'numerator':n,'denominator':d,'percent':100*n/d if d else None}
def short(r):return f"{r['numerator']}/{r['denominator']}"+(f" ({r['percent']:.2f}%)" if r.get('percent') is not None else '')
def main():
    pre=load(R/(P+'preflight.json'));protected=pre['protected_files']
    assert all(sha(p)==h for p,h in protected.items())
    candidate=load(R/(P+'candidate_freeze.json'));assert all(sha(p)==h for p,h in candidate['files'].items())
    # Both exposed development versions retain their exact frozen source.
    for n in ['development_candidate_freeze.json','v2_development_candidate_freeze.json']:
        assert all(sha(p)==h for p,h in load(R/(P+n))['files'].items())
    for n in ['search_v2c_c5d_repair_freeze_manifest.json','search_v2c_c5d_repair_v2_candidate_freeze.json']:
        assert all(sha(p)==h for p,h in load(R/n)['files'].items())
    ind=load(R/(P+'independent_metrics.json'));overall=ind['overall'];error=load(R/(P+'acceptance_error_analysis.json'))
    native=load(R/(P+'native_integration.json'));assert native['qualification']=='PASS' and native['database']['cleanup_complete']
    dev=load(R/(P+'v2_development_typed_decision_scoring.json'))['overall'];fidelity=load(R/(P+'development_analysis.json'))
    supplement=load(R/(P+'supplemental_operand_audit.json'));prediction=load(R/(P+'independent_prediction_complete.json'))
    assert prediction['parser_calls']==90 and prediction['retries']==0 and not prediction['isolation_denials']
    assert not fidelity['introduced_false_execution_vs_C5D_v2'] and not fidelity['introduced_missed_execution_vs_C5D_v2']
    assert overall['false_execution_count']==25 and overall['missed_execution_count']==10
    def recognition(kind):return {'A_C5C_development':dev['per_decision'][kind]['recall'],'C_independent':overall['per_decision'][kind]['recall']}
    present=defaultdict(list);absence=defaultdict(list);invented=[]
    for row in supplement['details']:
        for a in row['assertions']:
            if a['mask']['status']=='APPLICABLE_ABSENCE':
                absence[a['field']].append(a['correct'])
                if not a['correct']:invented.append({'case_id':row['case_id'],'field':a['field'],'actual':a['actual']})
            else:present[a['field']].append(a['correct'])
    preds=rows(R/(P+'independent_predictions.jsonl'))
    suspicious=[]
    for row in preds:
        repairs=[x for x in row['actual_plan']['decision'].get('repair_notices',[]) if str(x.get('from','')).casefold() in ['sort','titles']]
        if repairs:suspicious.append({'case_id':row['case_id'],'repairs':repairs})
    write('semantic_fidelity.json',{'A_C5C_development':{'eligible':644,'per_field':fidelity['per_field'],
          'executable_contexts_without_scored_hard_operand_mismatch':rate(250,250),
          'executable_contexts_without_strict_semantic_remainder_mismatch':rate(250,250),
          'strict_mismatch_contexts':425,'all_raw_failures_retained':True},
          'C_independent_supplemental_only':{'present_resolved_operand_accuracy':{k:rate(sum(v),len(v)) for k,v in present.items()},
             'known_absence_accuracy':{k:rate(sum(v),len(v)) for k,v in absence.items()},'invented_scalar_diagnostics':invented,
             'all_scored_operand_match':supplement['all_scored_operand_match'],'semantic_known_absence':supplement['known_absence_semantic']['rate'],
             'structured_semantic_or_advisory_rows_without_frozen_adapter':len(supplement['semantic_list_to_string_adapter_unavailable']),
             'suspicious_grammar_repairs':suspicious,'source_provenance_is_not_semantic_repair_correctness':True,
             'primary_scalar_mask_issue_disclosed':True,'normative_gold_or_primary_scores_changed':False},
          'B_focused':'1401 passed test cases, six additional source-backed wrapper/intent regressions included; no independent reliability claim.',
          'D_native':'310 passed disposable scenarios; representative author/title/subject/exclusion/pagination/mode/provider checks. See native_integration.json.',
          'taxonomy':{'confirmed_loss_or_wrong_filter':'Independent scalar and literal ownership failures; false-executable aggregate and missing required values.',
            'incorrect_negative_behavior':'Independent unresolved negative ownership and missing whole-word/category exclusion paraphrases.',
            'valid_representation_only':'Existing case/whitespace and formats-only BOTH equality remain the only authorized equivalences.',
            'evaluator_contract_disagreement':'Historical intent50 mismatch and structured semantic/advisory list versus native string; not silently normalized.',
            'indeterminate':'Blocked-development residual text and affected-field diagnostic strings retained without declaring all of them functional defects.'}})
    production_count=sum(str(p).replace('\\','/').split('/')[0] in ['search','backend','frontend','assistant','rag','recommendation','knowledge_graph'] for p in protected)
    write('protected_verification.json',{'status':'PASS','protected_entries':len(protected),'production_entries':production_count,
          'verified_at_utc':datetime.now(timezone.utc).isoformat(),'mismatches':[],
          'C5D_master_files':len(load(R/'search_v2c_c5d_repair_freeze_manifest.json')['files']),
          'C5D_v2_candidate_files':len(load(R/'search_v2c_c5d_repair_v2_candidate_freeze.json')['files']),
          'C5C_predictions_sha256':sha(R/'search_v2c_c5c_predictions.jsonl'),'C5B_gold_sha256':sha(R/'search_v2c_c5b_expected_labels.jsonl'),
          'C5D_failed_V1_and_unsafe_V2_preserved':True,'C5E_candidate1_and_rejected_blind_draft_preserved':True,
          'C5E_candidate2_freeze_verified':True,'live_application_side_effects_observed':0,'resident_endpoint_calls':0,'heldout_evaluations':0,
          'sealed_structural_audit_only':True,'production_database_mutations':0,'hnsw_rebuilds':0,'kg_rebuilds':0})
    fields={
       'FINAL':'PARTIAL','C5E_IMPLEMENTED':True,'C5D_V2_BASELINE_VERIFIED':True,'C5D_V2_FROZEN_EVIDENCE_PRESERVED':True,
       'FINAL_CANDIDATE_ID':'search-v2c-c5e-disabled-candidate-2','KNOWN_UNSAFE_C5D_CASE_RESOLVED':True,
       'NEW_UNSAFE_EXECUTION_REGRESSIONS':{'A_vs_C5D_v2':0,'C_new_independent_unsafe_recommendations':25},
       'REMAINING_UNSAFE_EXECUTION_CASES':error['false_execution'],
       'EXECUTABLE_WITH_NOTICE_CORRECT':recognition('EXECUTABLE_WITH_NOTICE'),'AMBIGUITY_RECOGNITION':recognition('AMBIGUOUS'),
       'INCOMPLETE_RECOGNITION':recognition('INCOMPLETE'),'UNSUPPORTED_RECOGNITION':recognition('UNSUPPORTED'),'CONTRADICTION_RECOGNITION':recognition('CONTRADICTORY'),
       'SEMANTIC_FIDELITY_RESULTS':{'A_strict_semantic_text':fidelity['per_field']['semantic_text'],'A_broad_exclusion':fidelity['per_field']['exclude_terms'],
          'C_supplemental_all_scored_operands':supplement['all_scored_operand_match'],'primary_scalar_metrics_incomplete':True,'structured_semantic_adapter':'N/A'},
       'INDEPENDENT_REVIEW_COMPLETED':{'reviewed':90,'total':90,'human':0,'author':'/root/c5e_blind_normative_author','reviewer':'/root/c5e_blind_normative_reviewer','model_identity':'NOT_EXPOSED'},
       'STRUCTURAL_ISOLATION_VERIFIED':True,'INDEPENDENT_ACCEPTANCE_TYPED_ACCURACY':overall['typed_accuracy'],
       'INDEPENDENT_ACCEPTANCE_EXECUTION_ACCURACY':overall['execution_accuracy'],'INDEPENDENT_ACCEPTANCE_FALSE_EXECUTION':overall['false_execution_rate'],
       'INDEPENDENT_ACCEPTANCE_MISSED_EXECUTION':overall['missed_execution_rate'],'NATIVE_INTEGRATION_VALIDATED':{'status':'PASS','scenarios':rate(310,310),'boundaries':833,'denials':529},
       'SMART_MODE_REGRESSION':'Native and exposed development pass; independent safety gate FAILED',
       'EXACT_MODE_REGRESSION':'PASS in disposable native fixture across five scopes',
       'NOTICE_AND_CORRECTION_WORKFLOWS':'Native issued Apply/Keep, literal clarification and grammar notices PASS; independent notice semantic correctness NOT qualified',
       'PUBLIC_PRIVATE_ISOLATION':'PASS in disposable native fixture','STAFF_PATRON_AUTHORIZATION':'PASS in disposable native fixture','OUTSIDER_CONCEALMENT':'PASS, exact404 for private outsider/admin without membership',
       'PARSER_LATENCY':error['parser_capture_latency'],'FULL_SEARCH_LATENCY_AVAILABLE':{'isolated_fixture':native['fixture_full_search_latency'],'production':False},
       'GLOBAL_SEARCH_HEALTH_LAST_KNOWN':'STALE/degraded; baseline_verified=False','PRODUCTION_PARSER_CHANGED':False,'ACTIVE_C4_POLICY_CHANGED':False,
       'PRODUCTION_DATABASE_MUTATED':False,'HNSW_REBUILT':False,'KG_REBUILT':False,'HELDOUT_EVALUATIONS':0,
       'PREVIOUS_EVIDENCE_HASH_VERIFIED':{'entries':len(protected),'production_entries':production_count,'changes':0},'C5E_EVIDENCE_FROZEN':True,'C5F_READY':False}
    implementation=[str(p.resolve()) for p in sorted(Path('scratch/search_v2c_c5e/candidate_search_v2').glob('*.py'))]
    artifacts=[str((R/(P+n)).resolve()) for n in ['preflight.json','implementation_changes.json','implementation.patch','requirement_ledger.md','development_analysis.json','v2_regression.xml',
       'author_provenance_v3.json','independent_review_v3.json','review_reconciliation_v3.json','reviewed_population_v3.jsonl','v3_structural_isolation.json',
       'candidate_freeze.json','independent_parser_configuration.json','independent_predictions.jsonl','independent_prediction_complete.json','independent_metrics.json','independent_failures.json',
       'supplemental_operand_audit.json','semantic_fidelity.json','acceptance_error_analysis.json','v2_native_final.xml','native_integration.json','privacy_authorization.json',
       'v2_parser_performance.json','protected_verification.json','operational_limits.md','freeze_manifest.json']]
    report={'required_final_fields':fields,'candidate_activation':'DISABLED','production_readiness':'BLOCKED','cohort_separation':{
       'A':{'population':'Original eligible C5C development','typed':rate(644,644),'execution':rate(644,644),'false_execution':rate(0,394),'missed_execution':rate(0,250),'independent':False},
       'B':{'population':'C5E source-backed focused and inherited pure-parser tests','passed':rate(1401,1401),'independent':False},
       'C':{'population':'New independently authored/reviewed SMART acceptance','contexts':90,'shared_patterns':18,'actual_topologies':18,'30_cells':'3 contexts per scope/stratum','attempts':1,'capture_errors':0},
       'D':{'population':'Real native disposable scenarios','passed':rate(310,310),'boundaries':833,'denials':529,'privacy_violations':0,'cleanup':True}},
       'integrity_status':'PASS; no privacy/isolation/prohibited-operation violation observed. PARTIAL is failed safety/readiness qualification, not a production activation.',
       'concrete_blockers':error['minimum_safe_resolution'],'implementation_files':implementation,'evidence_files':artifacts,
       'scoring_limitation':'Primary typed/execution metrics valid. Primary scalar-mask namespace lookup omitted all hard operands; its strict5/90 is incomplete and not an acceptance gate. Primary structured-list/native-string semantic0/50 is not a semantic accuracy claim. Separate supplemental audit retains exact frozen gold/predictions and existing norm/BOTH with mechanical prefixed key lookup. No primary outputs changed.',
       'no_retuning':'No implementation changes or acceptance recapture after the single frozen90 prediction capture.',
       'finite_sample_limit':'Synthetic90 share18 semantic patterns across five scopes; zero privacy failures or development errors is not proof of real-world zero risk.',
       'candidate_freeze_sha256':sha(R/(P+'candidate_freeze.json')),'completed_at_utc':datetime.now(timezone.utc).isoformat(),'C5F_started':False}
    write('final_report.json',report)
    text=['# C5E final report — PARTIAL\n\nC5F readiness is BLOCKED. The disabled candidate passed exposed development and native compatibility but failed independent execution safety. No production activation or C5F work occurred.\n',
       '\n| Cohort | Result |\n|---|---|\n| A: C5C development644 | Typed644/644; execution644/644; false0/394; missed0/250. Exposed development only. |\n| B: focused/inherited parser tests | 1401/1401 passed. |\n| C: independent90 | Typed25/90 (27.78%); execution55/90 (61.11%); false25/60 (41.67%); missed10/30 (33.33%). |\n| D: native disposable scenarios | 310/310 passed; 833 boundary requests,529 denials; zero observed privacy/authorization violations. |\n',
       '\n90 independent contexts cover all30 scope/decision cells,3 each, sharing18 semantic patterns and18 actual C2 topologies. The structurally rejected initial draft is preserved and was never predicted. AI author and independent AI reviewer completed90/90; human0. Gold and scorer were frozen before one90-call capture, with zero capture errors/retries.\n',
       '\nThe acceptance failure mechanisms are unresolved mandatory alternatives, explicit empty required operands, creator-wide aggregate rating treated as per-work rating, overly broad refusal of supported bibliographic intersections, field/literal boundaries and spurious grammar repairs. Source substring provenance alone does not establish semantic repair correctness. All five independent contradictory patterns/scopes failed typed recognition; none is credited merely because it was blocked.\n',
       '\nThe primary scorer omitted prefixed scalar masks. Its typed/execution confusion is unaffected; its strict5/90 is incomplete. Its structured-list/string semantic comparison is not semantic accuracy. Primary files remain immutable. A separate postcapture operand audit reports5/90 all-scored-operand matches using frozen masks and existing norm/BOTH; it changes no label, primary metric, candidate or prediction.\n',
       '\nParser-only independent capture: p50 %.2f ms, p95 %.2f ms, max %.2f ms (90 calls). Native fixture full-search-plus-serialization: p50 %.2f ms, p95 %.2f ms (55 mixed fixture requests). No production full-search latency is available. Last known global health remains STALE/degraded; baseline_verified=False. No resident endpoint repoll occurred.\n'%(error['parser_capture_latency']['p50_ms'],error['parser_capture_latency']['p95_ms'],error['parser_capture_latency']['max_ms'],native['fixture_full_search_latency']['p50_ms'],native['fixture_full_search_latency']['p95_ms']),
       '\n## Required final fields\n\n| Field | Value |\n|---|---|\n']
    for k,v in fields.items():
        value=json.dumps(v,ensure_ascii=False,separators=(',',':')) if not isinstance(v,str) else v
        text.append('| '+k+' | '+value.replace('|','\\|')+' |\n')
    text.append('\n## Concrete blockers and minimum safe resolution\n\n')
    for item in error['minimum_safe_resolution']:text.append('- '+item+'\n')
    text.append('\n## Implementation and evidence paths\n\n')
    for path in implementation+artifacts:text.append('- ['+Path(path).name+']('+path.replace('\\','/')+')\n')
    text.append('\nAll1,868 protected entries, including462 production entries, and both historical C5D freezes verified unchanged. Candidate1, failed runs, rejected draft, reviewed gold, primary predictions and failures are preserved. The evidence manifest excludes only itself and its independent verification file to avoid recursive hashes. Stop after this C5E report.\n')
    with (R/(P+'final_report.md')).open('x',encoding='utf8') as f:f.writelines(text)
    files={str(p):sha(p) for p in R.rglob(P+'*') if p.is_file() and p.name not in [P+'freeze_manifest.json',P+'freeze_verification.json']}
    # Include files beneath namespaced native report directories as well.
    for directory in R.glob(P+'*'):
        if directory.is_dir():files.update({str(p):sha(p) for p in directory.rglob('*') if p.is_file()})
    files.update({str(p):sha(p) for p in Path('scripts').glob(P+'*.py')})
    files.update({str(p):sha(p) for p in Path('scratch/search_v2c_c5e').rglob('*.py')})
    write('freeze_manifest.json',{'version':'C5E-evidence-freeze-v1','at_utc':datetime.now(timezone.utc).isoformat(),'files':files,
          'protected_files_reference':str(R/(P+'preflight.json')),'candidate_freeze_sha256':sha(R/(P+'candidate_freeze.json')),
          'final':'PARTIAL','C5F_READY':False,'production_activation':False,'self_exclusions':[P+'freeze_manifest.json',P+'freeze_verification.json']})
    assert all(sha(p)==h for p,h in files.items()) and all(sha(p)==h for p,h in protected.items())
    write('freeze_verification.json',{'status':'PASS','at_utc':datetime.now(timezone.utc).isoformat(),'C5E_files':len(files),'historical_entries':len(protected),
          'candidate_files':len(candidate['files']),'changes':0,'manifest_sha256':sha(R/(P+'freeze_manifest.json')),
          'final_report_sha256':sha(R/(P+'final_report.json')),'candidate_freeze_sha256':sha(R/(P+'candidate_freeze.json')),
          'primary_prediction_sha256':sha(R/(P+'independent_predictions.jsonl'))})
    print(json.dumps({'FINAL':'PARTIAL','C5F_READY':False,'historical_entries_unchanged':len(protected),'C5E_frozen_files':len(files),'candidate_freeze_sha256':sha(R/(P+'candidate_freeze.json')),'manifest_sha256':sha(R/(P+'freeze_manifest.json'))}))
if __name__=='__main__':main()
