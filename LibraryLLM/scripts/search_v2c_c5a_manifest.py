"""C5A schema/accounting/freeze tooling. No parser or confidence-policy calls."""
from collections import Counter,defaultdict
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,unicodedata

R=Path('reports');P='search_v2c_c5a_';VERSION='V2C-C-C5A-calibration-v1'
SCOPES=['GLOBAL','PUBLIC_TENANT_PATRON','PUBLIC_TENANT_STAFF','PRIVATE_TENANT_PATRON','PRIVATE_TENANT_STAFF']
STRATA=['CLEAR_EXECUTABLE','SAFE_UNCERTAIN_EXECUTABLE','AMBIGUOUS','INCOMPLETE','UNSUPPORTED','CONTRADICTORY']
ALIASES={'GLOBAL':'GLOBAL','PUBLIC_PATRON':'PUBLIC_TENANT_PATRON','PUBLIC_STAFF':'PUBLIC_TENANT_STAFF','PRIVATE_PATRON':'PRIVATE_TENANT_PATRON','PRIVATE_STAFF':'PRIVATE_TENANT_STAFF'}
REQUIRED='case_id benchmark_version query_text family_id structural_component_id scope_type workspace_type search_mode decision_stratum expected_typed_decision expected_executable expected_hard_constraints expected_soft_preferences expected_semantic_remainder expected_ambiguity expected_incomplete_fields expected_unsupported_fields expected_contradiction protected_entities capability_profile review_status reviewer_type label_confidence_or_review_notes metric_applicability partition'.split()
def read(name):return json.loads((R/(P+name)).read_text(encoding='utf8'))
def old(name):return json.loads((R/name).read_text(encoding='utf8'))
def rows(path):return [json.loads(x) for x in Path(path).read_text(encoding='utf8').splitlines() if x.strip()]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(name,value):(R/(P+name)).write_text(json.dumps(value,indent=2,default=str)+'\n',encoding='utf8')
def normalize(text):return ' '.join(unicodedata.normalize('NFKC',str(text)).casefold().split())
def canonical(row,caps):
    return (normalize(row['query_text']),row['search_mode'],row['scope_type'],row['workspace_type'],json.dumps(caps[row['scope_type']]['capabilities'],sort_keys=True),row.get('native_action') or ('NATIVE:'+row['family_id'] if row.get('unit')=='NATIVE_SEQUENCE' else 'PARSER'))

def retained(oldrow,caps):
    scope=ALIASES[oldrow['scope_type']];native=bool(oldrow.get('requires_native_execution'))
    mapping={'expected_subjects':'subjects','expected_excluded_subjects':'exclude_subjects','expected_exclude_terms':'exclude_terms','expected_author':'author_text','expected_title':'title_text','expected_exact_text':'exact_text','expected_rating_min':'rating_min','expected_rating_max':'rating_max','expected_year_min':'year_min','expected_year_max':'year_max','expected_format':'formats','expected_exclusive_formats':'exclusive_formats','expected_excluded_formats':'excluded_formats','expected_availability':'availability','expected_language':'language'}
    constraints={v:oldrow[k] for k,v in mapping.items() if k in oldrow} if not native else {}
    for key in ['rating_min_exclusive','rating_max_exclusive','year_min_exclusive','year_max_exclusive']:
        if not native and key in oldrow:constraints[key]=oldrow[key]
    entity=[]
    for span in oldrow.get('protected_spans',[]):
        t=span['text'];start=span['start'];end=span['end']
        if len(t)>1 and t[0]==t[-1] and t[0] in ['"',"'"]:t=t[1:-1];start+=1;end-=1
        entity.append({'text':t,'start':start,'end':end,'kind':'RETAINED_PROTECTED_ENTITY'})
    case={'case_id':oldrow['query_id'],'benchmark_version':VERSION,'source_benchmark_version':oldrow['benchmark_version'],'query_text':oldrow['query_text'],
        'family_id':oldrow['family_id'],'structural_component_id':oldrow['structural_family_id'],'scope_type':scope,'workspace_type':caps[scope]['workspace_type'],
        'search_mode':oldrow['search_mode'],'decision_stratum':'NATIVE_LIFECYCLE' if native else 'CLEAR_EXECUTABLE','expected_typed_decision':None if native else oldrow['expected_decision'],
        'expected_executable':None if native else oldrow['execution_allowed'],'expected_hard_constraints':constraints,
        'expected_soft_preferences':None if native else oldrow.get('expected_soft_preferences',[]),'expected_semantic_remainder':None if native else oldrow.get('expected_semantic_text'),
        'expected_ambiguity':None if native else oldrow.get('expected_ambiguous_spans',[]),'expected_incomplete_fields':None if native else oldrow.get('expected_incomplete_fields',[]),
        'expected_unsupported_fields':None if native else oldrow.get('expected_unsupported_fields',[]),'expected_contradiction':None if native else {'present':False,'fields':oldrow.get('expected_contradiction_fields',[])},
        'protected_entities':entity,'capability_profile':{'profile_id':scope+'-frozen-v1','capabilities':caps[scope]['capabilities'],'canonical_reference':P+'capability_matrix.json#'+scope},
        'review_status':oldrow['review_status'],'reviewer_type':oldrow.get('reviewer_type'),'label_confidence_or_review_notes':'Original calibration context retained. Native single-turn parser fields are inapplicable; operational oracles are separately versioned.' if native else 'C3 independent sealed calibration labels retained; quote delimiters represented as syntax around protected content, consistent with frozen C5 adapter.',
        'metric_applicability':{'parser_plan_metrics':{'status':'INAPPLICABLE' if native else 'APPLICABLE','reason':'Native sequence' if native else 'Existing independently authored labels'},'native_oracles':{'status':'APPLICABLE' if native else 'INAPPLICABLE','reference':P+'native_oracles.json' if native else None}},
        'partition':'calibration','example_class':'RETAINED_NATIVE' if native else 'RETAINED_CORE','unit':'NATIVE_SEQUENCE' if native else 'PARSER_CONTEXT',
        'original_query_id':oldrow.get('original_query_id',oldrow['query_id']),'source_row_sha256':hashlib.sha256(json.dumps(oldrow,sort_keys=True).encode()).hexdigest(),
        'source_row_reference':{'path':'reports/search_v2c_c5_calibration.jsonl','query_id':oldrow['query_id']},
        'requires_native_execution':native,'parser_evaluable':not native,
        'human_reviewed':False,'parser_output_used_for_authoring':False}
    if native:
        case['native_action']=oldrow.get('expected_action') or oldrow['family_id']
        case['retained_historical_sequence_spec']=oldrow.get('sequence_steps')
        case['native_current_oracle_reference']={'path':P+'native_oracles.json','action':case['native_action'],'missing_context_mapping':P+'native_missing_contexts.json#'+oldrow['query_id'] if oldrow['family_id']=='c04_correction_actions' else None}
    else:
        case['expected_intent']=oldrow.get('expected_intent')
        case['expected_sort']=oldrow.get('expected_sort')
        case['retained_original_expected_labels']={k:v for k,v in oldrow.items() if k.startswith('expected_') or k.endswith('_exclusive') or k=='execution_allowed'}
    return case

def main():
    caps=read('capability_matrix.json')['scopes'];draft=rows(R/(P+'reviewed_draft.jsonl'))
    isolation=read('family_isolation_candidates.json')
    # The sealed tool exposes only colliding NEW identifiers; it never supplies
    # held-out text/labels/topology strings to this authoring/assembly process.
    assert isolation['status']!='NOT_RUN_INPUT_ABSENT'
    collisions={r['new_case_id'] for r in isolation.get('colliding_new_rows',[])
        if r.get('required_action')=='DISCARD_NEW_CASE' or 'canonical_context_sha256' in r.get('collision_types_by_partition',{}).get('original_calibration',[])}
    collisions.update(r['new_case_id'] for r in isolation.get('duplicate_new_context_rows',[]))
    accepted=[x for x in draft if x['case_id'] not in collisions]
    for row in accepted:
        assert all(k in row for k in REQUIRED),(row.get('case_id'),[k for k in REQUIRED if k not in row])
        assert row['scope_type'] in SCOPES and row['decision_stratum'] in STRATA and row['partition']=='calibration'
        assert row['capability_profile']['capabilities']==caps[row['scope_type']]['capabilities']
        row['unit']='PARSER_CONTEXT';row['requires_native_execution']=False;row['parser_evaluable']=True
        row['parser_output_used_for_authoring']=False;row['human_reviewed']=False
    original=rows(R/'search_v2c_c5_calibration.jsonl');assert len(original)==280
    retained_rows=[retained(x,caps) for x in original]
    corpus=retained_rows+accepted
    identities=defaultdict(list)
    for row in corpus:identities[canonical(row,caps)].append(row['case_id'])
    duplicates=[ids for ids in identities.values() if len(ids)>1]
    assert not duplicates,duplicates
    assert len({x['case_id'] for x in corpus})==len(corpus)
    matrix={};core=[]
    for scope in SCOPES:
        matrix[scope]={}
        for stratum in STRATA:
            cell=[r for r in accepted if r['scope_type']==scope and r['decision_stratum']==stratum]
            eligible=[r for r in cell if r['example_class']=='CORE' and r['review_status']=='AI_REVIEWED' and r.get('review_complete') is True]
            core+=eligible;patterns=Counter(r.get('independent_pattern_id',r['pattern_id']) for r in eligible)
            matrix[scope][stratum]={'reviewed_new_core':len(eligible),'meaningful_patterns':len(patterns),'pattern_counts':dict(patterns),
                'derivatives':sum(r['example_class']=='DERIVATIVE' for r in cell),'partial_or_unreviewed_core':sum(r['example_class']=='CORE' and r not in eligible for r in cell),
                'minimum_pass':len(eligible)>=15 and len(patterns)>=4}
    matrix_pass=all(c['minimum_pass'] for s in matrix.values() for c in s.values())
    write('scope_decision_matrix.json',{'status':'PASS' if matrix_pass else 'FAIL','matrix':matrix,'minimum_per_cell':15,'minimum_patterns_per_cell':4,'minimum_reviewed_core':450,
        'actual_new_independently_reviewed_core':len(core),'derivatives_never_count_as_core':True})
    (R/(P+'calibration_cases.jsonl')).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in corpus),encoding='utf8')
    (R/(P+'new_accepted_cases.jsonl')).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in accepted),encoding='utf8')
    (R/(P+'expected_labels.jsonl')).write_text(''.join(json.dumps({'case_id':r['case_id'],**{k:v for k,v in r.items() if k.startswith('expected_') or k in ['protected_entities','metric_applicability','retained_original_expected_labels']}})+'\n' for r in corpus),encoding='utf8')
    family_assignments=defaultdict(list)
    for row in corpus:family_assignments[row['structural_component_id']].append(row['case_id'])
    write('family_assignments.json',{'version':VERSION,'partition':'calibration','components':dict(family_assignments),'discarded_new_case_ids':sorted(collisions)})
    review_counts=dict(Counter(r['review_status'] for r in corpus))
    write('label_provenance.json',{'version':VERSION,'new_core_independent_author':'/root/c5a_corpus_author','new_core_independent_reviewer':'/root/c5a_corpus_reviewer','new_independently_reviewed_core':len(core),
        'review_status_counts':review_counts,'human_reviewed':0,'new_parser_outputs_seen_by_author_or_reviewer':False,'calibration_parser_evaluations':0,
        'retained_core':50,'retained_native':230,'derivative_policy':'Generated derivatives are marked UNREVIEWED; no independent core review claim. Native semantic plan labels are not reused as single-turn gold.',
        'native_review_separate':P+'native_independent_review.json','author_draft_sha256':sha(R/(P+'author_draft.jsonl')),'reviewed_draft_sha256':sha(R/(P+'reviewed_draft.jsonl'))})
    write('partition_accounting.json',{'version':VERSION,'original_logical_contexts':7211,'development_logical_contexts':6881,'development_parser_cases':6529,'development_native_contexts':352,
        'heldout_logical_contexts':50,'original_calibration_contexts_retained':280,'original_calibration_contexts_replaced':0,
        'new_unique_calibration_contexts':len(accepted),'new_independently_reviewed_core':len(core),'new_derivatives':sum(r['example_class']=='DERIVATIVE' for r in accepted),
        'total_repaired_calibration_contexts':len(corpus),'repaired_parser_contexts':sum(r['unit']=='PARSER_CONTEXT' for r in corpus),'retained_native_sequences':230,
        'new_logical_benchmark_contexts_total':7211+len(accepted),'canonical_context_duplicates':0,'review_status_counts':review_counts,
        'old_C3_fifty_label_versions':'Replacements of50 original C2 contexts, not additional logical contexts; original C5 population already contains them.',
        'native_validation_test_scenarios':'Separate harness scenarios/API boundaries are validation evidence, not additional corpus rows unless explicitly represented in this manifest.',
        'original_manifest_unchanged':True,'new_calibration_parser_evaluations':0,'new_policy_evaluations':0,'heldout_parser_evaluations':0,
        'discarded_new_candidates':len(collisions),'discarded_new_case_ids':sorted(collisions),'isolation_reference':P+'family_isolation.json'})
    print(json.dumps({'matrix':'PASS' if matrix_pass else 'FAIL','new_reviewed_core':len(core),'new_contexts':len(accepted),'total_contexts':len(corpus),'duplicates':len(duplicates),'discarded':len(collisions)}))

if __name__=='__main__':main()
