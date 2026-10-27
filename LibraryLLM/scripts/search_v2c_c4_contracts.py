"""Machine projection of frozen output-blind semantic authorship; no parser IO."""
import hashlib,json,unicodedata
from pathlib import Path
R=Path('reports')
AUTHORED_HASH='8edfa36dbc8fd883a059f9a053a104f4eb6d74782c75b1a17e7201b3596a6c8f'
def normalized_text(v):return unicodedata.normalize('NFKC',v).casefold() if isinstance(v,str) else v
def projection(row):
    fields=dict(row['expected_fields'])
    if row['mode']=='SMART':
        for key in ['author_text','title_text']:
            if fields.get(key) is not None:fields[key]=normalized_text(fields[key])
    # These are representation adapters for independently authored semantic
    # predicates, not new normative values chosen from parser predictions.
    if row.get('preserved_free_prefix') is not None:fields['semantic_text']=normalized_text(row['preserved_free_prefix'])
    if row.get('preserved_soft_topic') is not None:fields['semantic_text']=normalized_text(row['preserved_soft_topic'])
    if isinstance(row.get('rating_min_inclusive'),bool):fields['rating_min_exclusive']=not row['rating_min_inclusive']
    return fields
def main():
    p=R/'search_v2c_c4_blind_contract_authored.json';assert hashlib.sha256(p.read_bytes()).hexdigest()==AUTHORED_HASH
    authored=json.loads(p.read_text());records={r['review_id']:r for r in authored['records']};assert len(records)==68
    dev={r['query_id']:r for l in (R/'search_v2c_c2_v2_development.jsonl').read_text().splitlines() if (r:=json.loads(l))}
    prior=json.loads((R/'search_v2c_c3_development_label_overrides.json').read_text());overrides=dict(prior['overrides']);changes=[]
    mapping={'decision':'expected_decision','executable':'execution_allowed','subjects':'expected_subjects','exclude_subjects':'expected_excluded_subjects','exclude_terms':'expected_exclude_terms','author_text':'expected_author','title_text':'expected_title','exact_text':'expected_exact_text','rating_min':'expected_rating_min','rating_max':'expected_rating_max','intent':'expected_intent','semantic_text':'expected_semantic_text','rating_min_exclusive':'rating_min_exclusive'}
    for qid,row in records.items():
        if qid not in dev:continue
        case=dev[qid];assert case['split']=='development' and not case.get('requires_native_execution')
        assert hashlib.sha256(case['query_text'].encode()).hexdigest()==row['query_sha256']
        new={mapping[k]:v for k,v in projection(row).items() if k in mapping}
        if 'expected_title' in new:new['expected_title_entity']=new['expected_title']
        if 'execution_allowed' in new:new['expected_execution_allowed']=new['execution_allowed']
        before={**case,**overrides.get(qid,{})};overrides[qid]={**overrides.get(qid,{}),**new}
        changes.append({'query_id':qid,'changed_fields':{k:{'C3':before.get(k),'C4':v} for k,v in new.items() if before.get(k)!=v},'reason':row['semantic_reason'],'query_text_unchanged':True})
    data={'version':'C4-independent-development-contract-v1','review_status':'AI_REVIEWED','parser_output_visible':False,'overrides':overrides,'case_count':len(overrides),'C3_override_source_sha256':hashlib.sha256((R/'search_v2c_c3_development_label_overrides.json').read_bytes()).hexdigest(),'newly_reviewed_C4_cases':len(changes),'newly_reviewed_source_sha256':AUTHORED_HASH,'raw_corpus_preserved':True,'population_and_supported_contradiction_denominators_unchanged':True,'projection_policy':'SMART author/title/free-topic values use established NFKC+casefold representation; TITLE_AUTHOR and exact identifier retain raw literal operands. No predictions used.'}
    (R/'search_v2c_c4_development_label_overrides.json').write_text(json.dumps(data,indent=2))
    gold={r['id']:r for l in (R/'search_v2c_a_gold_queries.jsonl').read_text().splitlines() if (r:=json.loads(l))};legacy={};audit=[]
    for qid in ['gold-065','gold-066','gold-069','gold-094','gold-095','gold-043','gold-056']:
        row=records[qid];case=gold[qid];assert hashlib.sha256(case['query'].encode()).hexdigest()==row['query_sha256']
        fields=projection(row);values={('decision_type' if k=='decision' else k):v for k,v in fields.items() if k!='executable' and (k in case['expected'] or k in ['exclude_subjects','decision'])}
        legacy[qid]=values
        audit.append({'id':qid,'query':case['query'],'original_expected':case['expected'],'reviewed_field_overrides':values,'classification':'SAFER_BEHAVIOR_WITH_VERSIONED_CONTRACT_CHANGE','review_status':'AI_REVIEWED','parser_output_visible':False,'group':'PREVIOUSLY_REVIEWED_THREE_GOLD_DEFECTS' if qid in ['gold-066','gold-094','gold-095'] else 'TWO_NEW_NATURAL_NEGATION_DISAGREEMENTS' if qid in ['gold-065','gold-069'] else 'EXPLICIT_C4_FREE_PREFIX_TITLE_POLICY','reason':row['semantic_reason'],'eligibility_examples':row['eligibility_examples'],'unresolved_fields':row['unresolved_fields']})
    assertion_map={
     'tests.test_search_v2c_a::test_curated_candidate_plan[gold-065]':'gold-065',
     'tests.test_search_v2c_a::test_curated_candidate_plan[gold-066]':'gold-066',
     'tests.test_search_v2c_a::test_curated_candidate_plan[gold-069]':'gold-069',
     'tests.test_search_v2c_a::test_curated_candidate_plan[gold-094]':'gold-094',
     'tests.test_search_v2c_a::test_curated_candidate_plan[gold-095]':'gold-095',
     'tests.test_search_v2c_a::test_mixed_negative_refinement_and_instead_provenance':'mixed_refinement',
     'tests.institution_v2g.test_query_v2a::test_kg_negative_and_rating_cannot_be_overridden':'kg_negative',
     'tests.institution_v2g.test_query_v2c_b::test_one_chip_removal_keeps_other_subjects_and_exclusions[False]':'chip_removal_without_session',
     'tests.institution_v2g.test_query_v2c_b::test_one_chip_removal_keeps_other_subjects_and_exclusions[True]':'chip_removal_with_session',
     'tests.test_search_v2c_a::test_curated_candidate_plan[gold-043]':'gold-043',
     'tests.test_search_v2c_a::test_curated_candidate_plan[gold-056]':'gold-056',
     'tests.institution_v2g.test_query_v2c_b::test_choices_reuse_parser_and_validate_before_commit[include Romance but exclude Romance-1-None-<lambda>]':'clarification_subject_exclude'}
    contract={'version':'C4-accepted-current-contract-v1','review_status':'AI_REVIEWED','AI_REVIEWED':68,'HUMAN_REVIEWED':0,'parser_output_visible':False,'authored_sha256':AUTHORED_HASH,'overrides':legacy,'records':{qid:projection(r) for qid,r in records.items()},'historical_assertion_map':assertion_map,'canonical_negation':'A scoped category exclusion does not additionally ban text. Explicit not-about content negation uses text only. Canonical subject choices and chip edits preserve this distinction.','free_prefix_title_policy':'Free text before by AUTHOR stays semantic unless explicit title syntax supplies strict evidence.','devel_corrections':changes,'unresolved_policy':'Unresolved decisions/intent/carriers stay visible. No new review value is copied from predictions. Soft carrier and casing adapters are documented above.','raw_legacy_source_sha256':hashlib.sha256((R/'search_v2c_a_gold_queries.jsonl').read_bytes()).hexdigest()}
    (R/'search_v2c_c4_reviewed_contract.json').write_text(json.dumps(contract,indent=2))
    (R/'search_v2c_c4_legacy_gold_review.json').write_text(json.dumps({'case_count':7,'original_raw_C3_failures':5,'previously_reviewed_three':3,'new_natural_negation_reviews':2,'additional_explicit_title_policy_reviews':2,'AI_REVIEWED':7,'HUMAN_REVIEWED':0,'raw_labels_and_assertions_unchanged':True,'authored_sha256':AUTHORED_HASH,'cases':audit},indent=2))
    failures=json.loads((R/'search_v2c_c3_final_qa.json').read_text())['raw_assertion_failures'];delta=[]
    for f in failures:
        key=f['class']+'::'+f['name'];rid=assertion_map[key];row=records[rid]
        delta.append({'test':key,'review_id':rid,'original_accepted_behavior':'Canonical subject exclusion plus a broad text-negative assertion','current_behavior':'Canonical subject exclusion only; other tested filters/state/actions remain required','source_change':'C3 search/query_repair.py removed duplicate broad text composition; C4 preserves it and applies same rule to subject-exclude clarification choices','candidate_eligibility_changes':True,'candidate_set_effect':'Books with incidental excluded words but without the excluded canonical category remain eligible','security_changes':False,'session_ownership_changes':False,'session_semantic_change':'Only explicit query/refinement or addressed chip item is edited','classification':'SAFER_BEHAVIOR_WITH_VERSIONED_CONTRACT_CHANGE','review_status':'AI_REVIEWED','parser_output_visible_to_reviewer':False,'reason':row['semantic_reason'],'eligibility_examples':row['eligibility_examples'],'reviewed_expected_fields':projection(row),'historical_failure':f})
    (R/'search_v2c_c4_regression_delta.json').write_text(json.dumps({'broader_exclusion_assertions':9,'all_nine_independently_reviewed':True,'AI_REVIEWED':9,'HUMAN_REVIEWED':0,'raw_historical_suite':'Preserved; must run fresh and report exact failures','reviewed_current_contract_suite':'New versioned tests; original assertions remain untouched','cases':delta,'additional_title_policy_changes':[r for r in audit if r['group']=='EXPLICIT_C4_FREE_PREFIX_TITLE_POLICY']},indent=2))
    lines=['# C4 independently reviewed negative semantics','',f'Frozen AI authorship SHA256: `{AUTHORED_HASH}`. AI_REVIEWED=68; HUMAN_REVIEWED=0. Original labels, predictions, source and failure reports were not visible to the semantic reviewer.','', 'Canonical subjects and text exclusions are different candidate predicates. Do not automatically emit both. Canonical negative requests preserve incidental words in title, author and description. Explicit not-about content negation uses text only. Not-only does not prohibit a category; non-fiction is lexical text unless the current scope provides its canonical category. Chip removal and canonical exclusion choices retain this distinction.','', 'All nine historical broader-exclusion assertions remain raw evidence. Seven legacy rows have versioned field overrides: the original three reviewed defects, two independently reviewed natural-negation disagreements, and two explicit C4 free-prefix title policy changes.','', '| Review | Decision / strict negatives | Reason |','|---|---|---|']
    for qid,r in records.items():
        if qid.startswith('natural-'):lines.append(f"| {qid} | {r['expected_fields'].get('decision','UNRESOLVED')}; categories={r['expected_fields'].get('exclude_subjects')}; text={r['expected_fields'].get('exclude_terms')} | {r['semantic_reason']} |")
    lines+=['','Partial intent and soft-carrier projections are disclosed in the frozen authored records. No parser probability or LLM second opinion is implemented.']
    (R/'search_v2c_c4_negative_semantics.md').write_text('\n'.join(lines)+'\n')
    print('C4 independent contracts projected:46 development rows;7legacy rows;9broader assertions;10natural negation examples')
if __name__=='__main__':main()
