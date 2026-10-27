"""Prepare/freeze offline shadow guards and input-only replay packets."""
from pathlib import Path
from copy import deepcopy
import ast
import importlib.util
import json
from scripts.search_v2c_c5d_prepare import R,P,load,rows,sha,digest,write,jsonl

GUARD=Path('scratch/search_v2c_c5d/shadow_guard.py')
def module():
    spec=importlib.util.spec_from_file_location('c5d_offline_guard',GUARD)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result

def input_packet(prediction,caps,intents,modes):
    actual=prediction['actual_plan']
    fields=['mode','intent','author_text','title_text','subjects','exclude_subjects','exclude_terms','rating_min','rating_max','rating_min_exclusive','rating_max_exclusive',
            'year_min','year_max','year_min_exclusive','year_max_exclusive','formats','exclusive_formats','excluded_formats','availability','physical_available_only','language']
    plan={k:actual[k] for k in fields}
    cfields=['field','operator','normalized_value','support_status','recognizer_id','source_span_start','source_span_end']
    plan['constraint_candidates']=[{k:c.get(k) for k in cfields} for c in actual['constraint_candidates']]
    plan['decision']={'decision_type':actual['decision']['decision_type'],'unresolved_fragments':actual['decision']['unresolved_fragments']}
    return {'plan':plan,'baseline_executable':prediction['executable'],'baseline_policy':prediction['assessment']['policy'],
            'capabilities':caps,'intents':intents,'modes':modes}

def main():
    pre=load(R/(P+'preflight.json'));assert all(sha(p)==h for p,h in pre['protected_files'].items())
    # Read existing production vocabulary constants as AST literals, without import.
    tree=ast.parse(Path('search/query_plan.py').read_text(encoding='utf8'))
    constants={n.targets[0].id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ['INTENTS','MODES']}
    predictions=rows(R/'search_v2c_c5c_predictions.jsonl')
    caps=load(R/'search_v2c_c5a_capability_matrix.json')['scopes']
    packets=[{'case_id':p['case_id'],'prediction_output_sha256':p['output_sha256'],
              'payload':input_packet(p,caps[p['scope_supplied']]['capabilities'],constants['INTENTS'],constants['MODES'])} for p in predictions]
    jsonl('shadow_inputs.jsonl',packets)
    guard=module()
    base=deepcopy(packets[0]['payload']);base['plan']['constraint_candidates']=[]
    for field in ['subjects','exclude_subjects','exclude_terms','formats','exclusive_formats','excluded_formats']:base['plan'][field]=[]
    for field in ['author_text','title_text','language','availability','rating_min','rating_max','year_min','year_max']:base['plan'][field]=None
    base['plan']['decision']={'decision_type':'EXECUTABLE','unresolved_fragments':[]};base['baseline_executable']=True;base['baseline_policy']='AUTO_EXECUTE'
    checks=[]
    def test(name,candidate,packet,expected):
        answer=guard.recommend(candidate,packet);assert answer['recommend_execution'] is expected,(name,answer)
        checks.append({'invariant':name,'candidate':candidate,'passed':True,'expected_recommend_execution':expected,
                       'actual_recommend_execution':answer['recommend_execution'],'not_independent_semantic_validation':True})
    test('No evidence gap is automatically called unsafe','E_COMPOSED_GUARD',base,True)
    blocked=deepcopy(base);blocked['baseline_executable']=False;blocked['baseline_policy']='CLARIFY';blocked['plan']['decision']['decision_type']='AMBIGUOUS'
    for c in guard.CANDIDATES:test('Never promote baseline blocked result',c,blocked,False)
    p=deepcopy(base);p['plan']['constraint_candidates']=[{'field':'author','operator':'CONTAINS','normalized_value':'Synthetic Author','support_status':'SUPPORTED'}]
    test('Recognized author must survive composition','B_CANDIDATE_OPERAND_GUARD',p,False)
    p['plan']['author_text']='Synthetic Author';test('Preserved author is permitted','B_CANDIDATE_OPERAND_GUARD',p,True)
    p=deepcopy(base);p['plan']['constraint_candidates']=[{'field':'rating','operator':'>=','normalized_value':3,'support_status':'SUPPORTED'}];p['plan']['rating_min']=4
    test('Stronger conjunction satisfies weaker numeric candidate','B_CANDIDATE_OPERAND_GUARD',p,True)
    p['plan']['rating_min']=2;test('Weaker numeric bound loses required candidate','B_CANDIDATE_OPERAND_GUARD',p,False)
    p=deepcopy(base);p['plan']['rating_min']=4;p['plan']['rating_max']=3;test('Numeric contradiction','C_PARSED_CONSISTENCY_GUARD',p,False)
    p=deepcopy(base);p['plan']['formats']=['ONLINE'];p['plan']['excluded_formats']=['ONLINE'];test('Format contradiction','C_PARSED_CONSISTENCY_GUARD',p,False)
    p=deepcopy(base);p['plan']['author_text']='Synthetic Author';p['plan']['exclude_terms']=['Author'];test('Required literal excluded everywhere','C_PARSED_CONSISTENCY_GUARD',p,False)
    p=deepcopy(base);p['plan']['year_min']=2010;p['capabilities']['year']=False;test('Scope capability remains binding','D_SUPPORTED_OUTPUT_GUARD',p,False)
    p=deepcopy(base);p['baseline_policy']='EXECUTE_WITH_NOTICE';test('Notice is not automatically a refusal','E_COMPOSED_GUARD',p,True)
    p=deepcopy(base);p['plan']['intent']='SYNTHETIC_UNKNOWN_OPERATION';test('Unknown output intent is withheld','D_SUPPORTED_OUTPUT_GUARD',p,False)
    write('shadow_invariant_checks.json',{'status':'PASS','checks':checks,'passed':len(checks),'independent_semantic_validation':False,
          'scope':'Hand-authored controlled plan invariants, no parser calls, no benchmark gold, no statistical accuracy claim.'})
    write('shadow_candidate_specifications.json',{'status':'FROZEN_FOR_EXPLORATORY_REPLAY','candidates':{
      'A_BASELINE':{'description':'Exact existing recorded execution recommendation and policy; no changes.'},
      'B_CANDIDATE_OPERAND_GUARD':{'description':'Checks that supported captured candidate operands survived in parsed plan; numeric conjunction uses logical entailment.',
          'limitations':['Does not discover absent candidates or parse query text.','Repeated/hypothetical candidates may cause false holds.','Broad exclude and include clauses requiring new vocabulary interpretation are not guessed.']},
      'C_PARSED_CONSISTENCY_GUARD':{'description':'Withholds on already captured unresolved states or numeric/format/category/literal include-exclude contradictions.',
          'limitations':['Cannot recover discarded contradictory requirements or recognize missing semantic ambiguity.','Does not generate server-issued clarification choices.']},
      'D_SUPPORTED_OUTPUT_GUARD':{'description':'Validates existing output intent/mode/schema/numeric domain and parsed scope-capability compatibility.',
          'limitations':['Output-vocabulary validation is not semantic supported-request recognition.','A default known intent does not certify that the user requested a supported operation.']},
      'E_COMPOSED_GUARD':{'description':'Union of B/C/D source-grounded restrictions; never promotes a blocked baseline.',
          'limitations':['No independent completeness ledger or authorization proof.','Not a selected production policy.']}},
      'inference_inputs':'Captured plan subset, supplied capability profile, existing INTENTS/MODES literals, baseline recommendation/policy only.',
      'not_supplied_to_candidate':['context ID','query text','gold','expected decisions','review rationale','scope stratum','evaluation results','native confidence'],
      'logic_access':'Candidate function only receives payload. Runner associates case IDs externally for traceability.',
      'safe_uncertain_rule':'Notice and confidence uncertainty alone do not block. Existing blocked recommendations stay blocked.',
      'authorization_boundary':'Offline restriction advice only; cannot call production entry points, return accepted plans, issue choices, commit transactions or replace native authority.',
      'source_grounding':['query_confidence.validate consistency/capabilities','query_repair.compose source-candidate composition','query_plan.matches broad text exclusions','query_calibration.execution_policy'],
      'review_status':'Source-grounded engineering prototypes; no fresh independent semantic approval or deployment acceptance claim.'})
    write('shadow_candidate_freeze.json',{'version':'C5D-shadow-freeze-v1','files':{str(GUARD):sha(GUARD),str(Path(__file__)):sha(__file__),
          str(Path('scripts/search_v2c_c5d_shadow_replay.py')):sha('scripts/search_v2c_c5d_shadow_replay.py'),
          str(R/(P+'shadow_candidate_specifications.json')):sha(R/(P+'shadow_candidate_specifications.json')),
          str(R/(P+'shadow_inputs.jsonl')):sha(R/(P+'shadow_inputs.jsonl'))},
          'input_records':644,'gold_available_to_guard':False,'scoring_has_not_started':True,'calibration_or_threshold_fit':False})
    print(json.dumps({'frozen_candidates':len(guard.CANDIDATES),'invariant_checks_passed':len(checks),'input_packets':644,'parser_calls':0}))

if __name__=='__main__':main()
