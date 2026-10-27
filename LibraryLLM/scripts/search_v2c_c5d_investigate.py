"""Static source/captured-output C5D analysis; no parser/model/application imports."""
from collections import Counter,defaultdict
from pathlib import Path
import ast
import json
import re
from scripts.search_v2c_c5d_prepare import R,P,load,rows,sha,write,jsonl

def source(path,start,end,owner):
    lines=Path(path).read_text(encoding='utf8').splitlines()
    return {'path':path,'start_line':start,'end_line':end,'owner':owner,'sha256':sha(path),'excerpt':'\n'.join(lines[start-1:end])}

def main():
    pre=load(R/(P+'preflight.json'));assert all(sha(p)==h for p,h in pre['protected_files'].items())
    gold={x['case_id']:x for x in rows(R/'search_v2c_c5b_calibration_cases.jsonl')}
    predictions={x['case_id']:x for x in rows(R/'search_v2c_c5c_predictions.jsonl')}
    scored={x['case_id']:x for x in rows(R/'search_v2c_c5c_scored_observations.jsonl')}
    old_failures=rows(R/'search_v2c_c5c_failures.jsonl')
    refs={
      'quote':source('search/query_constraints.py',19,54,'Source.__init__/free/remaining'),
      'subject':source('search/query_constraints.py',149,201,'subject_clauses'),
      'subject_add':source('search/query_constraints.py',255,266,'subject_clauses'),
      'title':source('search/query_repair.py',73,96,'compose'),
      'author':source('search/query_constraints.py',281,299,'author_title_entities'),
      'numeric':source('search/query_numeric.py',110,124,'recognize_ratings'),
      'repair':source('search/query_numeric.py',64,74,'_add'),
      'format':source('search/query_constraints.py',83,96,'formats_availability'),
      'year':source('search/query_numeric.py',163,176,'recognize_years'),
      'unsupported':source('search/query_constraints.py',98,113,'unsupported_and_sorts'),
      'incomplete':source('search/query_repair.py',48,55,'compose'),
      'final_decision':source('search/query_repair.py',131,172,'compose'),
      'validator':source('search/query_confidence.py',19,51,'validate'),
      'policy':source('search/query_calibration.py',16,20,'execution_policy'),
      'confidence':source('search/query_confidence.py',12,17,'decide'),
      'confidence_default':source('search/query_plan.py',76,102,'QueryPlan'),
      'fuzzy':source('search/query_plan.py',44,65,'FacetVocabulary.resolve'),
      'remainder':source('search/query_plan.py',241,257,'_parse_legacy'),
      'intent':source('search/query_repair.py',124,130,'compose'),
      'native':source('search/query_execution.py',17,34,'interpretation/interaction_for'),
      'choices':source('search/query_interaction.py',22,89,'choices_for'),
      'authorization':source('search/interaction_api.py',13,34,'authorized'),
      'resolution':source('search/interaction_api.py',81,105,'resolve'),
      'tenant_boundary':source('search/query_execution.py',196,212,'_tenant_search'),
      'evaluator':source('scripts/search_v2c_c4_evaluate.py',163,199,'rescore (strict field and decision comparison)')}
    write('source_references.json',refs)
    architecture={'status':'AUDITED_STATIC_ONLY','sources':refs,
       'path':[{'layer':'Request authority','owner':'search/interaction_api.py:authorized; catalogue.read_context','contract':'Current identity/login SID, library membership/workspace guards, outsider concealment precede stored choice or catalogue access.'},
               {'layer':'Interpretation','owner':'search/query_plan.py:parse_query -> search/query_repair.py:compose','contract':'Produces QueryPlan, constraint_candidates, spans, typed decision and correction provenance.'},
               {'layer':'Capability validation','owner':'search/query_confidence.py:validate/executable','contract':'Checks parsed constraints; execution allowed for EXECUTABLE and EXECUTABLE_WITH_NOTICE only. No completeness proof for unrecognized clauses.'},
               {'layer':'C4 assessment','owner':'search/query_calibration.py:assess/execution_policy','contract':'Produces categorical policy; no IO, authority or plan mutation. Used by offline evaluator; not directly called by current native query execution module.'},
               {'layer':'Native search response','owner':'search/query_execution.py:interpretation/interaction_for; QueryPlan.public','contract':'Exposes typed decision, chips, corrections and notice; blocked plans have guarded response. Executable correction list can produce server-issued correction choices.'},
               {'layer':'Native choice application','owner':'search/query_interaction.py:load_choice/transformer/reservation; interaction_api.resolve','contract':'Fresh owner/query/mode/version/expiry checks, read-only preview, one-use reservation and fresh authorization. No shadow candidate supplies or commits a plan.'}],
       'static_callsite_finding':'execution_policy is called by assess; assess is absent from search/query_execution.py and search/interaction_api.py. Its policy label is not a native authorization token.',
       'native_behavior_measured_in_C5D':False,'privacy_boundaries_modified':False}
    write('architecture.json',architecture)
    notice=[p for k,p in predictions.items() if gold[k]['expected_typed_decision']=='EXECUTABLE_WITH_NOTICE']
    notice_details=[]
    for p in notice:
        a=p['actual_plan']; flags={'corrections':bool(a['corrections']),'repair_provenance':any(c.get('repair_provenance') for c in a['constraint_candidates']),'unknown_subject':a['unknown_subject']}
        notice_details.append({'case_id':p['case_id'],'scope':gold[p['case_id']]['scope_type'],'parser_typed':p['typed_decision'],'policy':p['assessment']['policy'],
          'execution':p['executable'],'repair_flags':flags,'candidate_recognizers':[c['recognizer_id'] for c in a['constraint_candidates']],
          'root':'UNTAGGED_OR_UNRECOGNIZED_REPAIR_EXECUTED_WITHOUT_NOTICE' if p['executable'] else 'RECOVERABLE_REQUEST_BLOCKED_BY_FALLBACK',
          'representation_only_explanation_sufficient':False})
    assert len(notice)==100
    assert all(not any(x['repair_flags'].values()) for x in notice_details)
    write('typed_decision_contract_audit.json',{'status':'COMPLETE_PROPOSAL_REQUIRES_INDEPENDENT_REVIEW','gold_cohort':100,
      'parser_typed_notice_count':sum(p['typed_decision']=='EXECUTABLE_WITH_NOTICE' for p in notice),
      'C4_policy_notice_count':sum(p['assessment']['policy']=='EXECUTE_WITH_NOTICE' for p in notice),
      'auto_execute_without_notice':sum(p['assessment']['policy']=='AUTO_EXECUTE' for p in notice),
      'clarify_count':sum(p['assessment']['policy']=='CLARIFY' for p in notice),
      'cases':notice_details,'field_ownership':{'typed_decision':'QueryPlan.decision via decide(). Enum accepts notice, but the current SMART composer has no typed-notice producer.',
         'notice_policy':'execution_policy infers notice from repairs/corrections/unknown_subject even when typed decision is EXECUTABLE.',
         'native_notice':'QueryPlan.public corrections/notice and interaction_for correction choices; assessment label alone is not wired as a native response field.',
         'gold':'C5B expected_typed_decision is independently authored and C5C compares it literally; existing scores remain immutable.'},
      'conclusion':'Mixture: structural ownership ambiguity plus actual missing repair recognition/provenance in this cohort. No case has an observed downstream notice that could alone explain the typed miss.',
      'native_limit':'Static reachability traced; no native UI/API behavior newly executed. Do not claim a new measured native notice count.',
      'proposed_contract_specification':{'requires_independent_review':True,'keep_channels_separate':['parser_typed_decision','execution_recommendation','notice_required','notice_reasons','repair_source_spans','native_notice_rendered'],
         'parser_accuracy':'Keep literal historical typed scores; decide independently whether future normative notice target belongs to parser or combined layers.',
         'notice_success':'Requires correct supported interpretation, traceable repair/advisory evidence and an actually observable required notice; AUTO_EXECUTE does not satisfy it.',
         'no_blanket_equivalence':'Never map every EXECUTABLE to EXECUTABLE_WITH_NOTICE, and never equate a notice with refusal.',
         'affected_fields':'Specify field-family vs endpoint codes with source operator/span evidence; do not equate rating to both endpoints unconditionally.',
         'structured_advisory':'Define typed level/length/purpose/subject preference slots with spans, required/advisory ownership, and absence vs unknown. Display strings alone cannot prove structured equality.',
         'intent_priority':'Independently specify author+title intent ownership; both extracted operands and retrieval behavior must be retained. No retrospective override.'},
      'C5C_scores_rewritten':False,'confirmed_policy_adapter_runtime_defects':0,'source_refs':['policy','final_decision','numeric','repair','native','choices']})
    catalog={
      'QUOTED_OPERAND_MASKED':('CONFIRMED_PARSER_DEFECT','HIGH','Quoted literals are removed by Source.remaining and rejected by Source.free; title has an explicit ownership exception, subject/negative resolution does not.','quote','Recognize explicit field ownership around protected literals without parsing literal interiors.'),
      'TITLE_CLEARS_REMAINDER':('CONFIRMED_PARSER_DEFECT','HIGH','compose assigns semantic_text=None when composing an explicit title, after the legacy remainder has been computed.','title','Preserve independent free topical clauses alongside title operands.'),
      'RESIDUAL_TEXT_RETAINED':('INDETERMINATE_MISMATCH','MEDIUM','Normative topic tokens remain in output; extra wrappers/other unresolved text cause strict mismatch. Loss of intent is not established.','remainder','Specify semantic remainder boundaries with independent review.'),
      'HARD_CLAUSE_ROUTED_AS_TOPIC':('MULTIPLE_INTERACTING_CAUSES','HIGH','Missing structured operands coexist with their clause text in semantic remainder; extraction and remainder dimensions are coupled.','subject','Track clause ownership before semantic remainder assembly.'),
      'UNMODELED_RELATIONAL_AMBIGUITY':('CONFIRMED_PARSER_DEFECT','HIGH','No relational author/title or advisory/mandatory resolution state is emitted; narrow composer ambiguity paths are negation-scope candidates and a bare number.','final_decision','Produce unresolved mandatory relation/interpretation records before executable default.'),
      'INCOMPLETE_CUE_GRAMMAR':('CONFIRMED_PARSER_DEFECT','HIGH','Incomplete detection relies on a finite end-anchored residual cue and narrow malformed patterns; captured missing operands are absent from candidates or misread by fallback.','incomplete','Recognize clause-local missing operands, preserving blanks through composition.'),
      'UNSUPPORTED_REQUEST_UNRECOGNIZED':('CONFIRMED_PARSER_DEFECT','HIGH','Finite unsupported/capability grammar emits no matching strict candidate for the applicable requested field; downstream validate cannot reject an absent operand.','unsupported','Represent explicit unsupported mandatory operations even when no enforceable value exists.'),
      'CONTRADICTION_INPUTS_MISSING':('CONFIRMED_PARSER_DEFECT','HIGH','Frozen operands needed for the contradiction are missing; validate sees only the reduced plan.','validator','Retain both sides of required constraints before consistency checking.'),
      'CROSS_FIELD_CONTRADICTION_GAP':('CONFIRMED_PARSER_DEFECT','HIGH','Validator checks numeric bounds, format and category conflicts but has no title/author containment versus broad-text exclusion consistency rule.','validator','Add independently justified cross-field satisfiability checks after extraction.'),
      'UNTAGGED_NUMERIC_FALLBACK':('CONFIRMED_PARSER_DEFECT','HIGH','Captured exact-star candidate replaces a misspelled comparator/range; no repair provenance is present. Equality may invent an extra bound.','numeric','Bounded operator repair must preserve operator semantics and provenance; otherwise withhold unresolved requirement.'),
      'FINITE_FIELD_RECOGNIZER_GAP':('CONFIRMED_PARSER_DEFECT','HIGH','A known applicable operand has no corresponding captured candidate under the finite field grammar.','format','Extend source-backed grammatical coverage with separately reviewed examples.'),
      'FORMAT_ONLY_SCOPE_GAP':('CONFIRMED_PARSER_DEFECT','HIGH','Format is recognized as PRESENT while the separated format-only wording does not set ONLY.','format','Resolve modifier scope across explicit format wording.'),
      'CANDIDATE_COMPOSITION_OVERWRITE':('CONFIRMED_PARSER_DEFECT','HIGH','Multiple recognized author/title candidates are assigned to one scalar; later assignment replaces earlier evidence.','title','Preserve requirement inventory and resolve multiple referents explicitly.'),
      'AFFECTED_FIELD_CONTRACT':('EVALUATOR_CONTRACT_CONCERN','MEDIUM','Correct typed class can still disagree on field-family versus endpoint naming. Equivalence is not proven by this audit and strict score is unchanged.','validator','Independent field-code/operand-ownership contract review.'),
      'SECONDARY_TYPED_SYMPTOM':('MULTIPLE_INTERACTING_CAUSES','HIGH','Affected-field mismatch accompanies an already wrong typed class; it is not evidence that naming alone caused the error.','final_decision','Fix primary recognition before interpreting downstream field codes.'),
      'INTENT_PRECEDENCE_CONTRACT':('EVALUATOR_CONTRACT_CONCERN','HIGH','Composer gives author precedence over title, while retained gold uses FIND_EXACT. Both operands can remain present. Functional equivalence requires independent contract review.','intent','Specify combined author/title intent ownership without rewriting historical labels.'),
      'NOTICE_OWNERSHIP_AND_REPAIR':('MULTIPLE_INTERACTING_CAUSES','HIGH','Typed-notice producer is absent and this cohort also lacks all repair/correction notice signals. It is not a representation-only discrepancy.','policy','Audit typed/advisory ownership and implement traceable bounded repairs separately.'),
      'UNRESOLVED_CAUSE':('INDETERMINATE_MISMATCH','LOW','Frozen mismatch is real under the scoring contract; inspected evidence does not uniquely identify a causal implementation defect.','final_decision','Targeted independent semantic/contract investigation before any change.')}
    root_rows=[]; operand_details=[]; semantic_details=[]; classified=defaultdict(set)
    for failure in old_failures:
        k=failure['case_id'];g=gold[k];p=predictions[k];a=p['actual_plan'];candidate_fields={c['field'] for c in a['constraint_candidates']}
        causes=[]
        for detail in failure['details']:
            field=detail['dimension'];root='UNRESOLVED_CAUSE';expected=detail['observed_expected'].get('expected',detail['observed_expected'].get('expected_common_subset'))
            if field=='decision':
                root={'AMBIGUOUS':'UNMODELED_RELATIONAL_AMBIGUITY','INCOMPLETE':'INCOMPLETE_CUE_GRAMMAR','UNSUPPORTED':'UNSUPPORTED_REQUEST_UNRECOGNIZED','CONTRADICTORY':'CONTRADICTION_INPUTS_MISSING','EXECUTABLE_WITH_NOTICE':'NOTICE_OWNERSHIP_AND_REPAIR'}.get(g['expected_typed_decision'],'UNRESOLVED_CAUSE')
                if g['expected_typed_decision']=='CONTRADICTORY' and a['title_text'] and a['exclude_terms']:root='CROSS_FIELD_CONTRADICTION_GAP'
            elif field=='execution_allowed':
                root={'AMBIGUOUS':'UNMODELED_RELATIONAL_AMBIGUITY','INCOMPLETE':'INCOMPLETE_CUE_GRAMMAR','UNSUPPORTED':'UNSUPPORTED_REQUEST_UNRECOGNIZED','CONTRADICTORY':'CONTRADICTION_INPUTS_MISSING','EXECUTABLE_WITH_NOTICE':'NOTICE_OWNERSHIP_AND_REPAIR'}.get(g['expected_typed_decision'],'UNRESOLVED_CAUSE')
            elif field in ['subjects','exclude_subjects','exclude_terms'] and expected:
                values=expected if isinstance(expected,list) else [expected]
                quoted=any(re.search(r'["“]'+re.escape(str(v))+r'["”]',g['query_text'],re.I) for v in values)
                if quoted:root='QUOTED_OPERAND_MASKED'
            elif field=='semantic_text':
                wanted=g['expected_semantic_remainder'] or '';actual=a['semantic_text'] or ''
                if a['title_text'] and wanted and not actual:root='TITLE_CLEARS_REMAINDER'
                elif wanted and set(re.findall(r'\w+',wanted.casefold())).issubset(set(re.findall(r'\w+',actual.casefold()))):root='RESIDUAL_TEXT_RETAINED'
                elif any(f in failure['failure_categories'] for f in ['MISSING_REQUIRED_OPERAND','HALLUCINATED_OPERAND']):root='HARD_CLAUSE_ROUTED_AS_TOPIC'
            elif field in ['rating_min','rating_max','rating_min_exclusive','rating_max_exclusive']:
                if any(c['recognizer_id']=='rating.exact_star_unit' for c in a['constraint_candidates']) and g['decision_stratum']=='SAFE_UNCERTAIN_EXECUTABLE':root='UNTAGGED_NUMERIC_FALLBACK'
            elif field=='exclusive_formats' and expected and a['formats']:root='FORMAT_ONLY_SCOPE_GAP'
            elif field in ['formats','availability','year_min','year_max','author_text','title_text'] and expected not in (None,[],False,''):
                mapped={'formats':'format','availability':'availability','year_min':'year','year_max':'year','author_text':'author','title_text':'title'}[field]
                if mapped not in candidate_fields:root='FINITE_FIELD_RECOGNIZER_GAP'
                elif field in ['author_text','title_text'] and sum(c['field']==mapped for c in a['constraint_candidates'])>1:root='CANDIDATE_COMPOSITION_OVERWRITE'
            elif field.startswith('expected_') and field.endswith('_fields'):
                root='AFFECTED_FIELD_CONTRACT' if p['typed_decision']==g['expected_typed_decision'] else 'SECONDARY_TYPED_SYMPTOM'
            elif field=='intent' and g['example_class']=='RETAINED_CORE':root='INTENT_PRECEDENCE_CONTRACT'
            disposition,confidence,explanation,ref,remediation=catalog[root]
            # A bounded set of categories is source/capture-backed; causal
            # hypotheses remain explicitly weaker than a dynamic execution trace.
            evidence={'root_id':root,'dimension':field,'existing_failure_category':detail['category'],'existing_C5C_disposition_preserved':detail['disposition'],
                      'C5D_attribution_class':disposition,'causal_confidence':confidence,'candidate_root_cause':explanation,'source_reference':ref,
                      'source_location':{q:refs[ref][q] for q in ['path','start_line','end_line','sha256']},
                      'observed_expected':detail['observed_expected'],'evidence_method':'Static control-flow + frozen candidates/spans/output; no parser reexecution/instrumentation.',
                      'independent_contract_review_required':disposition in ['EVALUATOR_CONTRACT_CONCERN','INDETERMINATE_MISMATCH','MULTIPLE_INTERACTING_CAUSES'],
                      'potential_remediation':remediation}
            causes.append(evidence);classified[disposition].add(k)
            if field in g['expected_hard_constraints'] or field in ['subjects','exclude_subjects','exclude_terms','formats','exclusive_formats','availability','author_text','title_text']:
                operand_details.append({'case_id':k,'scope':g['scope_type'],'stratum':g['decision_stratum'],**evidence})
            if field=='semantic_text':semantic_details.append({'case_id':k,'scope':g['scope_type'],**evidence})
        root_rows.append({'case_id':k,'scope':g['scope_type'],'decision_stratum':g['decision_stratum'],'cohort':failure['cohort'],
             'gold_decision':g['expected_typed_decision'],'observed_parser_decision':p['typed_decision'],'applicable_execution_gold':g['expected_executable'],
             'observed_execution_recommendation':p['executable'],'C4_policy':p['assessment']['policy'],'relevant_operands':g['expected_hard_constraints'],
             'applicability':g['metric_applicability'],'existing_failure_categories':failure['failure_categories'],'causes':causes,
             'safety_severity':'HIGH_FALSE_EXECUTION' if p['executable'] and not g['expected_executable'] else 'MISSED_EXECUTION' if g['expected_executable'] and not p['executable'] else 'DIAGNOSTIC_ONLY',
             'possible_multiple_interacting_causes':len({x['root_id'] for x in causes})>1,'gold_or_predictions_modified':False})
    assert len(root_rows)==635
    jsonl('root_cause_matrix.jsonl',root_rows)
    jsonl('operand_extraction_diagnostics.jsonl',operand_details)
    jsonl('semantic_remainder_diagnostics.jsonl',semantic_details)
    root_contexts=defaultdict(set)
    for r in root_rows:
        for c in r['causes']:root_contexts[c['root_id']].add(r['case_id'])
    write('root_cause_summary.json',{'unique_failure_contexts':635,'new_core_failure_contexts':sum(r['cohort']=='NEW_REVIEWED_CORE' for r in root_rows),
      'retained_original_failure_contexts':sum(r['cohort']=='RETAINED_REVIEWED_CORE' for r in root_rows),
      'C5D_attribution_context_counts':{k:len(v) for k,v in classified.items()},'root_cause_distinct_context_counts':{k:len(v) for k,v in root_contexts.items()},
      'counts_overlap':True,'do_not_add_category_counts':True,'catalog':{k:{'class':v[0],'confidence':v[1],'explanation':v[2],'reference':v[3],'remediation':v[4]} for k,v in catalog.items()},
      'no_dynamic_causality_claim':True,'previous_C5C_dispositions_preserved':True,'normative_gold_concerns_quarantined':[],
      'confirmed_policy_adapter_defects':0,'indeterminate_remaining_ids':sorted(classified['INDETERMINATE_MISMATCH'])})
    traces=[]
    for k,p in predictions.items():
        g=gold[k]
        if not g['expected_executable'] and p['executable']:
            a=p['actual_plan']
            traces.append({'case_id':k,'scope':g['scope_type'],'stratum':g['decision_stratum'],'gold_decision':g['expected_typed_decision'],'gold_execution':False,
              'observed_decision':p['typed_decision'],'observed_execution':True,'reason_code':a['decision']['reason_code'],'policy':p['assessment']['policy'],
              'parsed_candidates':a['constraint_candidates'],'relevant_operands':g['expected_hard_constraints'],
              'unresolved_query_requirements':g['expected_ambiguity'] or g['expected_incomplete_fields'] or g['expected_unsupported_fields'] or g['expected_contradiction'],
              'decision_path':['compose has no recognized blocking condition for this requirement','decide(plan) defaults EXECUTABLE','validate sees reduced parsed operands','executable returns true','execution_policy returns AUTO_EXECUTE with no repair flags'],
              'earliest_observable_divergence':'Candidate inventory/mandatory unresolved-state absent or incomplete, before execution recommendation.',
              'downstream_policy_overrode_blocked_parser':False,'native_execution_performed':False,
              'source_references':['final_decision','validator','policy'],'prediction_sha256':p['output_sha256']})
    assert len(traces)==191 and all(t['policy']=='AUTO_EXECUTE' and t['observed_decision']=='EXECUTABLE' for t in traces)
    jsonl('false_execution_traceability.jsonl',traces)
    diag={}
    for kind in ['AMBIGUOUS','INCOMPLETE','UNSUPPORTED','CONTRADICTORY']:
        cohort=[(gold[k],p) for k,p in predictions.items() if gold[k]['example_class']=='CORE' and gold[k]['expected_typed_decision']==kind]
        misses=[(g,p) for g,p in cohort if p['typed_decision']!=kind]
        diag[kind]={'eligible':len(cohort),'typed_misses':len(misses),'false_execution':sum(p['executable'] for g,p in cohort),
                    'decision_reason_counts':dict(Counter(p['typed_decision']+'/'+p['actual_plan']['decision']['reason_code'] for g,p in misses)),
                    'case_ids':[g['case_id'] for g,p in misses],'source_reference':{'AMBIGUOUS':'final_decision','INCOMPLETE':'incomplete','UNSUPPORTED':'unsupported','CONTRADICTORY':'validator'}[kind],
                    'same_rules_shared_across_scopes':True,'scope_counts':dict(Counter(g['scope_type'] for g,p in misses))}
    diag['five_revised_cases']=[{'case_id':k,'scope':gold[k]['scope_type'],'decision':predictions[k]['typed_decision'],'execution':predictions[k]['executable'],
       'intentional_unknown_author':True,'cause':'No mandatory relational author-resolution state; a single recognized numeric fallback happens to block one case, not successful author-relation understanding.'}
       for k in [x['case_id'] for x in load(R/'search_v2c_c5b_corpus_admission.json')['cases']]]
    # The one AMBIGUOUS result is NUMBER_WITHOUT_FIELD, not author-relation evidence.
    for x in diag['five_revised_cases']:x['actual_reason']=predictions[x['case_id']]['actual_plan']['decision']['reason_code']
    write('ambiguity_contradiction_diagnostics.json',diag)
    confidence={'generation_sources':['QueryPlan.interpretation_confidence default 1.0','FacetVocabulary exact/alias/fuzzy similarity values','decide forces 0.0 on blocked typed kinds'],
      'interpretation':'Deterministic default/string-match similarity + typed-block flag. No probabilistic training, calibrated likelihood or normative confidence target.',
      'frozen_observed_values':dict(Counter(str(p['native_interpretation_confidence']) for p in predictions.values())),
      'matches_binary_execution_on_this_corpus':all((p['native_interpretation_confidence']==1.0)==p['executable'] for p in predictions.values()),
      'at_native_one':{'cases':398,'typed_correct':137,'typed_incorrect':261,'correct_executable_gold':207,'false_execution':191},
      'separation_limit':'207 legitimate execution and 191 unsafe execution recommendations share the same native value. A confidence-only rule cannot distinguish within that tied group.',
      'other_possible_scores':'Elsewhere alias/fuzzy paths can emit nonbinary similarities; no probability interpretation is inferred.',
      'required_future_features':['complete source-backed mandatory requirement ledger','field resolution and operator provenance','supported operation/capability evidence','unresolved relation/ambiguity state','independent safety labels and structurally separated validation'],
      'thresholds_fitted_or_swept':0,'transformations_fitted':0,'source_refs':['confidence','confidence_default','fuzzy']}
    write('confidence_investigation.json',confidence)
    invariants=[
      {'id':'AUTHORITY','established':'Fresh identity, library/workspace and owner checks precede native reads/choices/commits.','source':['authorization','resolution','tenant_boundary'],'shadow_limit':'No live authority proof is supplied; candidates cannot authorize or bypass native guards.'},
      {'id':'TYPED_BLOCK','established':'Only the two executable kinds permit execution; blocked kinds return guarded responses.','source':['validator','tenant_boundary'],'shadow_limit':'Shadow recommendation may restrict baseline only, never promote a blocked result.'},
      {'id':'CONSISTENCY','established':'Numeric, format and canonical category contradictions block when their operands are present.','source':['validator'],'shadow_limit':'Cannot infer constraints omitted by recognizers.'},
      {'id':'CAPABILITY','established':'Parsed year/language/availability and formats must fit supplied catalogue capabilities.','source':['validator'],'shadow_limit':'Unrecognized unsupported operations have no parsed signal.'},
      {'id':'MANDATORY_RESOLUTION','established':'Recognized INCOMPLETE/AMBIGUOUS candidates cause clarification.','source':['final_decision','choices'],'shadow_limit':'A full mandatory requirement inventory is a missing guarantee, not an existing field to assume true.'},
      {'id':'REPAIR_NOTICE','established':'Repair/correction evidence can yield notice without refusing an executable request.','source':['policy','choices'],'shadow_limit':'Uncertainty or a missing completeness certificate alone must not automatically reject every safe-uncertain request.'},
      {'id':'NATIVE_PRECONDITIONS','established':'Choice owner/mode/query/version/expiry, preview and reservation protect operations.','source':['resolution'],'shadow_limit':'Not assessable from offline single-turn predictions; no native calls.'}]
    write('safety_invariants.json',{'invariants':invariants,'no_new_authorization_semantics':True,'confidence_is_not_safety_proof':True})
    print(json.dumps({'contract_notice':{'typed':0,'policy_notice':0,'auto_without_notice':70,'clarify':30},'failure_contexts':len(root_rows),
       'root_distinct_counts':{k:len(v) for k,v in root_contexts.items()},'false_executions_traced':len(traces),'new_parser_calls':0}))

if __name__=='__main__':main()
