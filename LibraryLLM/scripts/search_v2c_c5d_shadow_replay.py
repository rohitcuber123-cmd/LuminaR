"""Separated C5D shadow capture/scoring. Never invokes the production parser."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import argparse
import importlib.util
import json
import os
import sys
from scripts.search_v2c_c5d_prepare import R,P,load,rows,sha,digest,write,jsonl

def rate(n,d):return {'numerator':n,'denominator':d,'percent':100*n/d if d else None,'status':'MEASURED' if d else 'N/A'}

def capture():
    freeze_path=R/(P+'shadow_candidate_freeze.json');freeze=load(freeze_path)
    assert all(sha(p)==h for p,h in freeze['files'].items())
    packets=rows(R/(P+'shadow_inputs.jsonl'));assert len(packets)==644
    allowed_reads={(R/(P+'shadow_inputs.jsonl')).resolve(),freeze_path.resolve()}
    report_dir=R.resolve();reads=set();denied=[]
    def audit(event,args):
        if event in ['socket.connect','socket.bind','socket.getaddrinfo','subprocess.Popen','os.system']:
            denied.append(event);raise RuntimeError('Offline shadow cannot use network/process IO')
        if event=='import' and str(args[0]).split('.')[0] in ['search','backend','assistant','pymongo','sqlite3','requests','httpx','rag','recommendation']:
            denied.append(event+':'+str(args[0]));raise RuntimeError('Shadow may not import application/parser/database modules')
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            path=Path(os.fsdecode(args[0])).resolve();mode,flags=args[1],args[2]
            writing=isinstance(mode,str) and any(c in mode for c in 'wax+') or isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)
            if writing and (path.parent!=report_dir or not path.name.startswith(P)):
                denied.append(str(path));raise RuntimeError('Only new C5D evidence writes allowed')
            if not writing and report_dir in path.parents and path not in allowed_reads:
                denied.append(str(path));raise RuntimeError('Gold/review/results unavailable in shadow inference')
            if not writing:reads.add(str(path))
        if event in ['os.remove','os.rename','os.rmdir','os.mkdir','os.truncate']:
            denied.append(event);raise RuntimeError('Shadow cannot mutate application filesystem')
    sys.addaudithook(audit)
    spec=importlib.util.spec_from_file_location('c5d_offline_guard','scratch/search_v2c_c5d/shadow_guard.py')
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    write('shadow_capture_started.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'candidate_freeze_sha256':digest(freeze),
          'logical_contexts':644,'candidate_replays_planned':len(guard.CANDIDATES)*644,'new_parser_calls':0,'gold_available':False})
    count=0;hasher=__import__('hashlib').sha256()
    with (R/(P+'shadow_predictions.jsonl')).open('xb') as out:
        for packet in packets:
            outcomes={name:guard.recommend(name,packet['payload']) for name in guard.CANDIDATES}
            value={'case_id':packet['case_id'],'input_sha256':digest(packet['payload']),'baseline_prediction_sha256':packet['prediction_output_sha256'],
                   'outcomes':outcomes,'output_sha256':digest(outcomes)}
            encoded=(json.dumps(value,sort_keys=True,ensure_ascii=False)+'\n').encode('utf8');hasher.update(encoded);out.write(encoded);count+=len(outcomes)
    write('shadow_capture_complete.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'logical_contexts':644,'candidate_replays':count,
          'candidate_count':len(guard.CANDIDATES),'errors':0,'retries':0,'new_production_parser_calls':0,'gold_reads':0,'network_calls':0,
          'isolation_denials':denied,'files_read_after_isolation':sorted(reads),'prediction_sha256':hasher.hexdigest()})
    print(json.dumps({'shadow_capture':'COMPLETE','logical_contexts':644,'candidate_replays':count,'new_parser_calls':0,'gold_reads':0}))

def metrics(group):
    negative=[x for x in group if not x['gold_execution']];positive=[x for x in group if x['gold_execution']]
    false=sum(x['shadow_execution'] for x in negative);missed=sum(not x['shadow_execution'] for x in positive)
    return {'contexts':len(group),'false_execution':rate(false,len(negative)),'missed_execution':rate(missed,len(positive)),
            'correct_non_execution':rate(len(negative)-false,len(negative)),
            'executable_coverage':rate(sum(x['shadow_execution'] for x in group),len(group)),
            'baseline_executable_coverage':rate(sum(x['baseline_execution'] for x in group),len(group)),
            'coverage_change_count':sum(x['shadow_execution']-x['baseline_execution'] for x in group),
            'changed_execution_decisions':sum(x['shadow_execution']!=x['baseline_execution'] for x in group),
            'additional_missed_valid_execution':sum(x['gold_execution'] and x['baseline_execution'] and not x['shadow_execution'] for x in group),
            'baseline_blocked_promoted':sum(not x['baseline_execution'] and x['shadow_execution'] for x in group),
            'withheld_for_review':sum(x['action']=='SHADOW_WITHHOLD_FOR_REVIEW' for x in group),
            'baseline_native_clarification_policy_count':sum(x['action']=='CLARIFY' for x in group),
            'native_clarifications_issued':0,'unassessable_full_requirement_coverage':sum(bool(x['unassessable']) for x in group)}

def score():
    complete=load(R/(P+'shadow_capture_complete.json'));assert complete['prediction_sha256']==sha(R/(P+'shadow_predictions.jsonl'))
    freeze=load(R/(P+'shadow_candidate_freeze.json'));assert all(sha(p)==h for p,h in freeze['files'].items())
    write('shadow_scoring_started.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'captured_predictions_sha256':complete['prediction_sha256'],
          'capture_complete_before_gold_join':True,'new_parser_calls':0,'candidate_logic_calls_during_scoring':0})
    gold={x['case_id']:x for x in rows(R/'search_v2c_c5b_calibration_cases.jsonl')}
    baseline={x['case_id']:x for x in rows(R/'search_v2c_c5c_predictions.jsonl')}
    outputs=rows(R/(P+'shadow_predictions.jsonl'));assert len(outputs)==644
    scored=[]
    for row in outputs:
        assert row['output_sha256']==digest(row['outcomes'])
        g=gold[row['case_id']];base=baseline[row['case_id']]
        for candidate,outcome in row['outcomes'].items():
            assert not outcome['recommend_execution'] or base['executable']
            scored.append({'case_id':row['case_id'],'candidate':candidate,'scope':g['scope_type'],'stratum':g['decision_stratum'],
                           'cohort':'NEW_CORE' if g['example_class']=='CORE' else 'RETAINED_ORIGINAL',
                           'gold_execution':g['expected_executable'],'gold_decision':g['expected_typed_decision'],
                           'baseline_execution':base['executable'],'baseline_typed':base['typed_decision'],'baseline_policy':base['assessment']['policy'],
                           'shadow_execution':outcome['recommend_execution'],'action':outcome['action'],'reason_codes':outcome['reasons'],
                           'unassessable':outcome['unassessable'] if candidate!='A_BASELINE' else [],
                           'guard_input_did_not_include_gold_or_id':True,'captured_output_sha256':row['output_sha256']})
    jsonl('shadow_scored_observations.jsonl',scored)
    candidates=sorted({x['candidate'] for x in scored})
    ids={x['case_id'] for x in load(R/'search_v2c_c5b_corpus_admission.json')['cases']}
    summaries={};regressions={}
    for name in candidates:
        group=[x for x in scored if x['candidate']==name]
        summaries[name]={'overall':metrics(group),'by_cohort':{cohort:metrics([x for x in group if x['cohort']==cohort]) for cohort in ['NEW_CORE','RETAINED_ORIGINAL']},
            'by_scope':{scope:metrics([x for x in group if x['scope']==scope]) for scope in sorted({x['scope'] for x in group})},
            'by_stratum':{stratum:metrics([x for x in group if x['stratum']==stratum]) for stratum in sorted({x['stratum'] for x in group})},
            'thirty_cells':[{'scope':scope,'stratum':stratum,**metrics([x for x in group if x['scope']==scope and x['stratum']==stratum])}
                            for scope in sorted({x['scope'] for x in group}) for stratum in sorted({x['stratum'] for x in group})],
            'changed_decisions':[x for x in group if x['shadow_execution']!=x['baseline_execution']],
            'five_revised_ambiguity_cases':[x for x in group if x['case_id'] in ids],
            'withhold_reason_context_counts':dict(Counter(reason['code'] for x in group for reason in x['reason_codes'])),
            'limits':'Same C5C cohort inspected during design; not independent validation. Missing parser requirements and live authorization cannot be recovered.'}
        regressions[name]={'CLEAR_EXECUTABLE':summaries[name]['by_stratum']['CLEAR_EXECUTABLE']['additional_missed_valid_execution'],
                          'SAFE_UNCERTAIN_EXECUTABLE':summaries[name]['by_stratum']['SAFE_UNCERTAIN_EXECUTABLE']['additional_missed_valid_execution'],
                          'by_scope':{scope:m['additional_missed_valid_execution'] for scope,m in summaries[name]['by_scope'].items()},
                          'regression_ids':[x['case_id'] for x in group if x['gold_execution'] and x['baseline_execution'] and not x['shadow_execution']],
                          'new_false_execution':sum(x['shadow_execution'] and not x['baseline_execution'] and not x['gold_execution'] for x in group),
                          'native_authorization_or_privacy_execution':'Not performed; no inference of live privacy correctness.'}
    base=summaries['A_BASELINE']['overall'];assert base['false_execution']['numerator']==191 and base['missed_execution']['numerator']==43
    assert all(s['overall']['baseline_blocked_promoted']==0 for s in summaries.values())
    write('shadow_replay_results.json',{'status':'EXPLORATORY_REPLAY_COMPLETE','candidate_count':len(candidates),'logical_contexts':644,
          'candidate_replays':3220,'new_parser_evaluations':0,'candidates':summaries,'policy_selected':False,
          'interpretation':'Changes are additional review holds on already captured predictions, not repaired parser outputs or native executions.'})
    write('safety_regression_analysis.json',{'candidates':regressions,'no_baseline_blocked_promotions':True,'same_population_regression_only':True,
          'independent_validation':False,'native_authority_bypass':False})
    print(json.dumps({name:{k:s['overall'][k] for k in ['false_execution','missed_execution','executable_coverage','changed_execution_decisions','additional_missed_valid_execution']} for name,s in summaries.items()}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['capture','score']);args=parser.parse_args()
    capture() if args.phase=='capture' else score()
