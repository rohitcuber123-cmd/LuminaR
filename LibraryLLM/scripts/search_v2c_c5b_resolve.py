"""Apply independently reviewed five-case revisions and validate metadata only.

No production parser, evaluator, policy, database or endpoint is imported/called.
All historical files are read-only. Non-target JSONL lines remain byte-identical.
"""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import ast,hashlib,json,re,unicodedata

R=Path('reports');P='search_v2c_c5b_'
def load(path):return json.loads(Path(path).read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def chash(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def dump(name,value):(R/(P+name)).write_text(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
def jsonlines(path):return [json.loads(x) for x in Path(path).read_text(encoding='utf8').splitlines() if x.strip()]

def main():
    base=load(R/(P+'baseline.json'));assert all(sha(p)==h for p,h in base['protected_files'].items())
    work=load(R/(P+'working_manifest.json'));original_ids={r['case_id'] for r in work['cases']}
    proposals=load(R/(P+'resolution_proposals.json'));proposal={r['case_id']:r for r in proposals['cases']}
    review=load(R/(P+'independent_review_output_v2.json'));verdict={r['case_id']:r for r in review['cases']}
    packet=load(R/(P+'independent_review_input_v2.json'));packet_cases={r['case_id']:r for r in packet['cases']}
    assert set(verdict)==set(proposal)==set(packet_cases)==original_ids and len(verdict)==5
    assert sha(R/(P+'independent_review_input_v2.json'))==review['cases'][0]['fingerprints']['input_file_sha256']
    old_path=R/'search_v2c_c5a_calibration_cases.jsonl';old_bytes=old_path.read_bytes();raw_lines=old_bytes.splitlines(keepends=True)
    old_rows=[json.loads(x) for x in raw_lines if x.strip()];old={r['case_id']:r for r in old_rows};assert len(old)==1024
    proposed={r['case_id']:r for r in jsonlines(R/(P+'proposed_contexts.jsonl'))}
    old_new_ids={r['case_id'] for r in jsonlines(R/'search_v2c_c5a_new_accepted_cases.jsonl')}
    components={r.get('operation_topology'):r['structural_component_id'] for r in old_rows if r.get('operation_topology')}
    revised={};lineage=[];resolutions=[];label_log=[]
    for key in sorted(original_ids):
        before=old[key];v=verdict[key];p=proposal[key];candidate=packet_cases[key]['candidate_query']
        assert v['review_disposition']=='ACCEPT' and v['eligibility']['core_semantic_eligible'] is True
        assert v['revision']['intended_testing_objective_preserved'] is True
        assert v['candidate']['annotation_label_unresolved'] is False
        assert v['candidate']['typed_decision']=='AMBIGUOUS' and v['candidate']['executable'] is False
        assert hashlib.sha256(candidate.encode()).hexdigest()==v['fingerprints']['candidate_query_utf8_sha256_computed']==p['proposed_query_utf8_sha256']
        assert hashlib.sha256(before['query_text'].encode()).hexdigest()==v['fingerprints']['original_query_utf8_sha256_computed']
        assert before['example_class']=='CORE' and before['review_status']=='PARTIAL'
        row=json.loads(json.dumps(before));row['query_text']=candidate
        row['context_version']='C5B-context-v2';row['label_version']='C5B-independent-labels-v2'
        row['context_parent']={'case_id':key,'source':'reports/search_v2c_c5a_calibration_cases.jsonl','source_corpus_sha256':sha(old_path),'source_case_canonical_sha256':chash(before),'source_query_sha256':hashlib.sha256(before['query_text'].encode()).hexdigest()}
        row['operation_topology']=proposed[key]['operation_topology']
        row['structural_component_id']=components.get(row['operation_topology'],proposed[key]['structural_component_id'])
        row['expected_typed_decision']=v['candidate']['typed_decision'];row['expected_executable']=v['candidate']['executable']
        row['expected_hard_constraints'].pop('author_text',None)
        ar=v['candidate']['author_resolution']
        row['expected_ambiguity']=[{'field':'author_text','kind':v['candidate']['ambiguity_kind'],'fragment':'by the author my note pairs with the requested title',
            'possible_names_without_selected_mapping':ar['possible_names_without_selected_mapping'],'reference':ar['reference'],
            'requirement_present':True,'grounded_author_value_available':False,'coauthorship_assumed_excluded':False,
            'clarification_target':v['candidate']['clarification_target'],'normative_reason':v['candidate']['normative_explanation']}]
        # Maintain bibliographic strings; recompute all real occurrences after
        # insertion/replacement. No missing old occurrence is fabricated.
        kinds={e['text']:e['kind'] for e in before['protected_entities']}
        protected=[]
        for text,kind in kinds.items():
            for match in re.finditer(re.escape(text),candidate):
                protected.append({'text':text,'start':match.start(),'end':match.end(),'kind':'AUTHOR_CANDIDATE' if text in ar['possible_names_without_selected_mapping'] else kind})
        row['protected_entities']=sorted(protected,key=lambda x:(x['start'],x['end'],x['text']))
        masks=row['metric_applicability']
        for name in list(masks):
            if name.startswith('protected_entities['):del masks[name]
        for i,e in enumerate(row['protected_entities']):
            assert candidate[e['start']:e['end']]==e['text']
            masks[f'protected_entities[{i}]']={'status':'APPLICABLE','reason':'Exact entity content unchanged; zero-based half-open occurrence recalculated mechanically in the independently accepted revision.'}
        for name in ['typed_decision','executable','ambiguity','independent_core_coverage']:
            masks[name]={'status':'APPLICABLE','required_gold_label_resolved':True,'reason':'Fresh independent final review under the user-authorized context revision contract; audit and quota admission are separately verified.'}
        masks['author_text']={'status':'UNRESOLVED','reason':'The QUERY deliberately leaves a mandatory author operand unknown. This is a definitive ambiguity annotation, not a missing typed-decision/execution gold label.',
            'query_requirement_present':True,'grounded_author_value_available':False,'required_annotation_label_unresolved':False,'strict_author_value_scoring':'INAPPLICABLE_UNTIL_CLARIFICATION'}
        row['review_status']='AI_REVIEWED';row['reviewer_type']='independent_output_blind_AI';row['review_complete']=True
        row['review_required_decision_safety_resolved']=True;row['review_unresolved_decision_safety_labels']=[]
        row['review_unresolved_fields']=['author_text'];row['independent_pattern_id']='c5b-independent-ambiguous-mandatory-author-title-association'
        row['reviewed_pattern_id']=row['independent_pattern_id'];row['label_confidence_or_review_notes']=v['candidate']['normative_explanation']
        row['semantic_review_notes']=[v['revision']['necessity_and_proportionality'],v['candidate']['normative_explanation']]
        row['prior_review_provenance']=before['review_provenance']
        row['review_provenance']={'review_id':review['version'],'reviewer':review['reviewer'],'reviewed_at':review['timestamp_utc'],
            'input_file':'reports/'+P+'independent_review_input_v2.json','input_sha256':sha(R/(P+'independent_review_input_v2.json')),
            'output_file':'reports/'+P+'independent_review_output_v2.json','output_sha256':sha(R/(P+'independent_review_output_v2.json')),
            'reviewed_case_individually':True,'parser_output_visible':False,'human_review_claimed':False,'proposer_is_different_fresh_agent':True,
            'v1_C5A_verdict_used_as_proof':False,'model_override':None,'model_identity':'Not exposed by collaboration runtime; no model substitution requested.'}
        row['human_reviewed']=False;row['parser_output_used_for_authoring']=False
        revised[key]=row
        diffs={k:{'before':before.get(k),'after':row.get(k)} for k in before.keys()|row.keys() if before.get(k)!=row.get(k)}
        lineage.append({'case_id':key,'original_case_sha256':chash(before),'revised_case_sha256':chash(row),'original_query_sha256':hashlib.sha256(before['query_text'].encode()).hexdigest(),
            'revised_query_sha256':hashlib.sha256(candidate.encode()).hexdigest(),'context_revision':True,'scope_unchanged':row['scope_type']==before['scope_type'],
            'mode_unchanged':row['search_mode']==before['search_mode'],'intended_stratum_unchanged':row['decision_stratum']==before['decision_stratum'],
            'original_context_preserved_in_C5A':True,'changed_fields':diffs})
        label_log.append({'case_id':key,'required_labels':{'expected_typed_decision':{'before':before['expected_typed_decision'],'after':row['expected_typed_decision']},'expected_executable':{'before':before['expected_executable'],'after':row['expected_executable']}},
            'author_operand_before':before['expected_hard_constraints'].get('author_text'),'author_operand_after':'Unresolved mandatory query reference; no invented author value',
            'literal_author_filter_replaced':v['revision']['literal_author_filter_replaced'],'required_gold_labels_resolved':2,'other_mask_and_entity_changes':diffs.get('metric_applicability')})
        resolutions.append({'case_id':key,'scope':row['scope_type'],'actor':packet_cases[key]['actor'],'stratum':row['decision_stratum'],
            'original_semantic_intent':p['original_semantic_intent'],'source_of_uncertainty':p['source_of_uncertainty'],
            'original_candidate_pair':{'typed_decision':v['original']['typed_decision'],'executable':v['original']['executable']},
            'final_pair':{'typed_decision':row['expected_typed_decision'],'executable':row['expected_executable']},
            'normative_justification':v['candidate']['normative_explanation'],'context_revision_necessary':v['revision']['necessary'],
            'independent_reviewer_verdict':v['review_disposition'],'review_provenance':row['review_provenance'],'final_state':'REVISED_AND_ACCEPTED_PENDING_INTEGRITY_GATES'})
    encoded=[];unchanged=0;corpus=[]
    for line in raw_lines:
        if not line.strip():encoded.append(line);continue
        oldrow=json.loads(line);key=oldrow['case_id'];row=revised.get(key,oldrow);corpus.append(row)
        if key in revised:
            newline=b'\r\n' if line.endswith(b'\r\n') else b'\n'
            encoded.append(json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()+newline)
        else:encoded.append(line);unchanged+=1
    (R/(P+'calibration_cases.jsonl')).write_bytes(b''.join(encoded));assert unchanged==1019
    # Preserve non-target label lines exactly too.
    labels=[]
    for line in (R/'search_v2c_c5a_expected_labels.jsonl').read_bytes().splitlines(keepends=True):
        oldlabel=json.loads(line);key=oldlabel['case_id']
        if key not in revised:labels.append(line);continue
        row=revised[key];value={'case_id':key,**{k:v for k,v in row.items() if k.startswith('expected_') or k in ['protected_entities','metric_applicability','retained_original_expected_labels']}}
        labels.append(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()+(b'\r\n' if line.endswith(b'\r\n') else b'\n'))
    (R/(P+'expected_labels.jsonl')).write_bytes(b''.join(labels))
    (R/(P+'revised_contexts.jsonl')).write_text(''.join(json.dumps(revised[k],sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n' for k in sorted(revised)),encoding='utf8')
    (R/(P+'new_calibration_contexts.jsonl')).write_text(''.join(json.dumps(r,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n' for r in corpus if r['case_id'] in old_new_ids),encoding='utf8')
    # Reuse only two hash-protected pure validation functions. No C5A main runs.
    source=Path('scripts/search_v2c_c5a_manifest.py');assert sha(source)==base['protected_files'][str(source).replace('/','\\')]
    tree=ast.parse(source.read_text());defs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['canonical','normalize']]
    namespace={'json':json,'unicodedata':unicodedata};exec(compile(ast.Module(body=defs,type_ignores=[]),str(source),'exec'),namespace)
    caps=load(R/'search_v2c_c5a_capability_matrix.json')['scopes'];contexts=defaultdict(list)
    for row in corpus:contexts[namespace['canonical'](row,caps)].append(row['case_id'])
    duplicates=[ids for ids in contexts.values() if len(ids)>1];assert not duplicates
    assert len({r['case_id'] for r in corpus})==len(corpus)==1024
    dump('deduplication.json',{'status':'PASS','contexts':len(corpus),'unique_canonical_contexts':len(contexts),'duplicate_canonical_contexts':0,'mechanism':'Hash-protected C5A canonical/normalize functions; full scope/mode/workspace/capability/native-action context. Gold never determines identity.','unchanged_non_target_corpus_lines':unchanged,'revised_stable_ids':sorted(revised)})
    scope_order=['GLOBAL','PUBLIC_TENANT_PATRON','PUBLIC_TENANT_STAFF','PRIVATE_TENANT_PATRON','PRIVATE_TENANT_STAFF'];strata=['CLEAR_EXECUTABLE','SAFE_UNCERTAIN_EXECUTABLE','AMBIGUOUS','INCOMPLETE','UNSUPPORTED','CONTRADICTORY'];matrix={};eligible=[]
    for scope in scope_order:
        matrix[scope]={}
        for stratum in strata:
            cell=[r for r in corpus if r['scope_type']==scope and r['decision_stratum']==stratum and r['example_class']=='CORE' and r['review_status']=='AI_REVIEWED' and r.get('review_complete') is True]
            assert all(r.get('review_required_decision_safety_resolved') is True for r in cell)
            patterns=Counter(r.get('independent_pattern_id',r['pattern_id']) for r in cell);eligible.extend(cell)
            matrix[scope][stratum]={'accepted_core':len(cell),'meaningful_patterns':len(patterns),'pattern_counts':dict(patterns),'pass':len(cell)>=15 and len(patterns)>=4}
    quota=all(c['pass'] for s in matrix.values() for c in s.values());assert quota and len(eligible)==594
    dump('scope_decision_matrix.json',{'status':'PASS','matrix':matrix,'accepted_new_core':len(eligible),'minimum_core_cell_size':min(c['accepted_core'] for s in matrix.values() for c in s.values()),'minimum_meaningful_pattern_count':min(c['meaningful_patterns'] for s in matrix.values() for c in s.values()),'derivative_native_rejected_partial_core_credit':0})
    remaining=[]
    for row in corpus:
        if row['example_class']=='CORE' and row.get('review_status') in ['PARTIAL','PARTIALLY_REVIEWED']:
            remaining.append(row['case_id'])
    dump('label_completeness.json',{'status':'PASS','required_gold_keys':['expected_typed_decision','expected_executable'],'partial_contexts_at_start':5,'partial_contexts_resolved':5,'partial_contexts_remaining':len(remaining),
        'required_labels_at_start':10,'required_labels_resolved':10,'unresolved_required_labels':0,'all_revised_required_masks_applicable':all(revised[k]['metric_applicability'][s]['status']=='APPLICABLE' for k in revised for s in ['typed_decision','executable']),
        'intentionally_unknown_query_author_operands':5,'distinction':'A definite AMBIGUOUS/false annotation records an unknown mandatory query operand. Its scalar author-value metric remains masked; this is not missing decision/execution gold.',
        'unreviewed_derivatives_or_retained_native_rows_not_promoted':True})
    dump('partition_accounting.json',{'status':'PASS','total_calibration_contexts':1024,'new_calibration_contexts':744,'retained_original_contexts':280,'accepted_new_core_cases':len(eligible),
        'new_derivative_contexts':sum(r['example_class']=='DERIVATIVE' for r in corpus),'unreviewed_contexts':sum(r['review_status']=='UNREVIEWED' for r in corpus),
        'rejected_core_cases':sum(r['review_status']=='REJECTED_CORE_DIVERSITY' for r in corpus),'partial_core_cases':len(remaining),'review_status_counts':dict(Counter(r['review_status'] for r in corpus)),
        'old_contexts_revised_in_place_with_lineage':5,'additional_active_contexts_created':0,'old_C5A_versions_preserved':True,'historical_plus_current_distinct_versions_not_added_to_active_denominator':True,
        'development_contexts':6881,'development_parser_cases':6529,'development_native_cases':352,'heldout_contexts':50,'logical_benchmark_active_total':7955,'native_mode_supplement_parser_core_credit':0})
    dump('five_case_resolution.json',{'version':'C5B-five-case-resolution-v2','cases':resolutions,'independent_review_input_sha256':sha(R/(P+'independent_review_input_v2.json')),'independent_review_output_sha256':sha(R/(P+'independent_review_output_v2.json')),'parser_predictions_used':False})
    dump('context_lineage.json',{'source_corpus_sha256':sha(old_path),'new_corpus_sha256':sha(R/(P+'calibration_cases.jsonl')),'unchanged_non_target_rows':1019,'changed_cases':lineage})
    dump('normative_label_revisions.json',{'required_label_pairs_resolved':5,'required_label_fields_resolved':10,'literal_author_operands_replaced':sum(verdict[k]['revision']['literal_author_filter_replaced'] for k in verdict),'cases':label_log,
        'original_C5A_labels_or_verdicts_overwritten':False,'original_semantic_EXECUTABLE_candidates_not_adopted_as_original_historical_gold':True})
    assert all(sha(p)==h for p,h in base['protected_files'].items())
    print(json.dumps({'contexts':1024,'changed_cases':5,'unchanged_rows':1019,'accepted_new_core':594,'quota':'PASS','duplicates':0,'required_labels_resolved':10,'partial_remaining':len(remaining)}))

if __name__=='__main__':main()
