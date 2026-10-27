"""Supplementary grouped historical replay and post-freeze prototype limitations."""
from copy import deepcopy
from pathlib import Path
import argparse
import json
import os
import re
import sys
from scripts.search_v2c_c5d_prepare import R,P,load,rows,sha,digest,write,jsonl

def prepare():
    freeze=load(R/(P+'shadow_candidate_freeze.json'));assert all(sha(p)==h for p,h in freeze['files'].items())
    dev=rows(R/'search_v2c_c2_v2_development.jsonl')
    eligible=[r for r in dev if not r.get('requires_native_execution') and r.get('review_status')=='AI_REVIEWED' and r.get('reviewer_type')=='independent_output_blind_AI']
    assert len(eligible)==6 and all('Independent output-blind AI semantic' in r['review_source'] for r in eligible)
    observed={r['query_id']:r for r in rows(R/'search_v2c_c4_development_reviewed_observations.jsonl')}
    from scripts.search_v2c_c2_benchmark import structure
    current=rows(R/'search_v2c_c5b_calibration_cases.jsonl')
    primary_ids={r['case_id'] for r in rows(R/'search_v2c_c5c_predictions.jsonl')}
    primary=[x for x in current if x['case_id'] in primary_ids]
    overlap={structure(x) for x in eligible}&{structure(x) for x in primary};assert not overlap
    from scripts.search_v2c_c5d_shadow_prepare import input_packet
    config=rows(R/(P+'shadow_inputs.jsonl'))[0]['payload']
    scopes=load(R/'search_v2c_c_scope_vocabularies.json')
    packets=[]
    for case in eligible:
        raw=observed[case['query_id']]
        assert raw['query_text']==case['query_text'] and raw['expected_execution'] is case['execution_allowed']
        pred={'actual_plan':raw['actual_plan'],'executable':raw['execution'],'assessment':raw['assessment']}
        packets.append({'case_id':case['query_id'],'payload':input_packet(pred,scopes[case['scope_type']]['capabilities'],config['intents'],config['modes'])})
    jsonl('validation_inputs.jsonl',packets)
    write('validation_population.json',{'ids':[x['query_id'] for x in eligible],'contexts':6,
      'group_ids':sorted({x['structural_family_id'] for x in eligible}),'groups':len({x['structural_family_id'] for x in eligible}),
      'topology_overlap_with_primary':[],'near_duplicate_groups_split':False,'all_one_group_preserved':True,
      'label_independence':'Pre-existing independent output-blind AI review recorded on authorized DEVELOPMENT rows; no new labels and no new reviewer claim.',
      'mixed_review_file_not_decoded':'Only its previously inspected metadata header and byte hash referenced. Mixed heldout review entries were not decoded.',
      'review_evidence_sha256':sha(R/'search_v2c_c2_independent_review.json'),
      'source_gold_population':str(R/'search_v2c_c2_v2_development.jsonl'),'source_gold_sha256':sha(R/'search_v2c_c2_v2_development.jsonl'),
      'source_predictions':str(R/'search_v2c_c4_development_reviewed_observations.jsonl'),'source_predictions_sha256':sha(R/'search_v2c_c4_development_reviewed_observations.jsonl'),
      'labels_used_for_rule_design':False,
      'preparation_attempts':[{'attempt':1,'result':'STOPPED_METADATA_PREPARATION','reason':'Repeatedly decoded the same frozen prediction file inside a context-filter comprehension; fixed to decode once.','parser_calls':0,'candidate_calls':0,'output_files_created':0},
                              {'attempt':2,'result':'PREPARED','parser_calls':0}],
      'limitations':['Only six executable-positive examples in one structural group.','No blocked/ambiguous/private safety coverage or generalization estimate.','Historical predictions, not a new parser run.']})
    write('validation_replay_freeze.json',{'files':{str(Path(__file__)):sha(__file__),str(R/(P+'validation_inputs.jsonl')):sha(R/(P+'validation_inputs.jsonl')),
       'scratch/search_v2c_c5d/shadow_guard.py':sha('scratch/search_v2c_c5d/shadow_guard.py')},'candidate_code_already_frozen_before_primary_and_validation_replay':True})
    print(json.dumps({'validation_prepared':6,'structural_groups':1,'topology_overlap':0,'new_parser_calls':0}))

def capture():
    f=load(R/(P+'validation_replay_freeze.json'));assert all(sha(p)==h for p,h in f['files'].items())
    packets=rows(R/(P+'validation_inputs.jsonl'));assert len(packets)==6
    report_dir=R.resolve();denied=[]
    def audit(event,args):
        if event in ['socket.connect','socket.bind','subprocess.Popen','os.system']:
            denied.append(event);raise RuntimeError('No networking or subprocess in validation inference')
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            path=Path(os.fsdecode(args[0])).resolve();mode=args[1];flags=args[2]
            writing=isinstance(mode,str) and any(x in mode for x in 'wax+') or isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)
            if not writing and report_dir in path.parents:
                denied.append(str(path));raise RuntimeError('Validation inference cannot open report/gold files')
            if writing and (path.parent!=report_dir or not path.name.startswith(P)):
                denied.append(str(path));raise RuntimeError('Only new C5D evidence writes allowed')
    sys.addaudithook(audit)
    from scripts.search_v2c_c5d_shadow_prepare import module
    guard=module();output=[]
    for packet in packets:
        outcomes={c:guard.recommend(c,packet['payload']) for c in guard.CANDIDATES}
        output.append({'case_id':packet['case_id'],'outcomes':outcomes,'output_sha256':digest(outcomes)})
    jsonl('validation_predictions.jsonl',output)
    # A post-freeze, hand-constructed contract counterexample is a prototype
    # limitation, never a silently changed guard or a corpus score adjustment.
    example=deepcopy(packets[0]['payload']);plan=example['plan']
    for k in ['subjects','exclude_subjects','formats','exclusive_formats','excluded_formats','constraint_candidates']:plan[k]=[]
    plan['decision']={'decision_type':'EXECUTABLE','unresolved_fragments':[]};plan['author_text']='Marsh';plan['title_text']=None;plan['exclude_terms']=['ar']
    example['baseline_executable']=True;example['baseline_policy']='AUTO_EXECUTE'
    result=guard.recommend('C_PARSED_CONSISTENCY_GUARD',example)
    # Same explicit word-boundary condition used in query_plan.matches, evaluated
    # as a reference expression, without importing or executing production code.
    exclusion_matches=bool(re.search(r'(?<!\w)ar(?!\w)','marsh'))
    assert not exclusion_matches and result['recommend_execution'] is False
    write('prototype_counterexample_audit.json',{'frozen_prototype_changed':False,'candidate':'C_PARSED_CONSISTENCY_GUARD and its use in E',
       'counterexample':{'required_author':'Marsh','broad_excluded_term':'ar','native_whole_word_exclusion_matches':False,'shadow_withholds':True},
       'finding':'The shadow substring entailment check is stronger than the production normalized whole-word negative predicate. It can add false review holds on unseen legitimate requests.',
       'disposition':'CONFIRMED_SHADOW_PROTOTYPE_LIMITATION','post_freeze_counterexample_calls':1,'primary_scoring_population_changed':False,
       'future_spec_correction':'Require the exact source normalization and word-boundary semantics plus independently reviewed adversarial cases before considering this rule further.',
       'new_production_parser_calls':0,'gold_reads_during_inference':0,'isolation_denials':denied})
    write('validation_capture_complete.json',{'contexts':6,'candidate_replays':30,'post_freeze_counterexample_calls':1,'new_parser_calls':0,
       'errors':0,'retries':0,'gold_reads':0,'isolation_denials':denied,'prediction_sha256':'Bound by next score-stage hash; no report reads allowed here.'})
    print(json.dumps({'historical_validation_replays':30,'prototype_counterexamples':1,'new_parser_calls':0}))

def score():
    pop=load(R/(P+'validation_population.json'));outputs=rows(R/(P+'validation_predictions.jsonl'))
    gold={r['query_id']:r for r in rows(R/'search_v2c_c2_v2_development.jsonl') if r['query_id'] in set(pop['ids'])}
    results={}
    for c in outputs[0]['outcomes']:
        values=[(gold[r['case_id']],r['outcomes'][c]) for r in outputs]
        results[c]={'contexts':6,'executable_gold':6,'blocked_gold':0,'correct_executable':sum(v['recommend_execution'] for g,v in values),
           'missed_execution':{'numerator':sum(not v['recommend_execution'] for g,v in values),'denominator':6},
           'false_execution':{'numerator':0,'denominator':0,'status':'N/A'},
           'changed_decision_ids':[g['query_id'] for g,v in values if not v['baseline_preserved']]}
    write('independent_validation_limits.json',{'availability':'LIMITED_HISTORICAL_REGRESSION_ONLY','independent_labels_available':True,
       'adequate_independent_safety_validation':False,'validation_contexts':6,'structural_groups':1,'blocked_gold_contexts':0,
       'near_duplicate_group_split':False,'overlap_with_C5C_operation_topology':0,'candidate_results':results,
       'validation_predictions_sha256':sha(R/(P+'validation_predictions.jsonl')),
       'design_bias':'Primary shadow candidates were designed after inspecting C5C failures. Neither primary replay gains nor six positive historical examples establish generalization.',
       'counterexample_audit':str(R/(P+'prototype_counterexample_audit.json')),
       'prerequisites':['Fresh output-blind independently reviewed hard-negative and safe-uncertain examples.','Freeze candidates/contracts before new validation labels/results are exposed.',
                        'Keep complete structural components together; include all five scopes and six strata without sealed heldout access.','Prove normalization, exclusion boundaries and required/advisory ownership.'],
       'no_policy_acceptance_claim':True})
    print(json.dumps({'limited_validation_contexts':6,'groups':1,'candidate_results':results,'independent_safety_validation':False}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','capture','score']);args=parser.parse_args()
    {'prepare':prepare,'capture':capture,'score':score}[args.phase]()
