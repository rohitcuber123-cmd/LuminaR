"""Freeze disabled parser after unit regressions and before candidate scoring."""
from pathlib import Path
from datetime import datetime,timezone
import json,xml.etree.ElementTree as ET
from scripts.search_v2c_c5d_repair_prepare import R,P,C,load,sha,write

def main():
    pre=load(R/(P+'preflight.json'));assert all(sha(p)==h for p,h in pre['protected_files'].items())
    xml=ET.parse(R/(P+'regression_final.xml')).getroot();suite=next(xml.iter('testsuite'))
    assert int(suite.attrib['failures'])==int(suite.attrib['errors'])==0 and int(suite.attrib['tests'])==1373
    (R/(P+'eligibility.json')).write_bytes((R/'search_v2c_c5c_eligibility.json').read_bytes())
    (R/(P+'parser_inputs.jsonl')).write_bytes((R/'search_v2c_c5c_parser_inputs.jsonl').read_bytes())
    caps=R/'search_v2c_c5a_capability_matrix.json'
    files={str(p):sha(p) for p in C.glob('*.py')}
    files.update({str(p):sha(p) for p in Path('scripts').glob(P+'*.py')})
    files.update({str(p):sha(p) for p in Path('scratch/search_v2c_c5d_repair/regression').glob('*.py')})
    files['scratch/search_v2c_c5d_repair/test_candidate_semantics.py']=sha('scratch/search_v2c_c5d_repair/test_candidate_semantics.py')
    files['scripts/search_v2c_c5c_score.py']=sha('scripts/search_v2c_c5c_score.py')
    write('candidate_freeze.json',{'version':'C5D-disabled-parser-repair-candidate-v1','frozen_at_utc':datetime.now(timezone.utc).isoformat(),
       'files':files,'regression_tests_passed':1373,'prior_failed_development_attempt_preserved':True,'primary_measurement_has_not_started':True,
       'same_corpus_used_for_development':True,'new_parser_namespace':'scratch.search_v2c_c5d_repair.candidate_search','production_activation':False,
       'C4_policy_source_sha256':sha('search/query_calibration.py'),'C5C_scorer_unchanged':True,'gold_source_sha256':sha(R/'search_v2c_c5b_expected_labels.jsonl')})
    config={'version':'C5D-disabled-candidate-evaluation-v1','input_sha256':sha(R/(P+'parser_inputs.jsonl')),'caps_path':str(caps),'caps_sha256':sha(caps),
       'prediction_calls_planned':644,'parser_source_hashes':{str(p):sha(p) for p in C.glob('*.py')},
       'frozen_before_prediction_scripts':files,'score_contract':'Exact frozen C5C scoring code and applicability masks; no label/representation changes.',
       'activation':False,'new_production_parser_calls':0,'candidate_parser_calls_planned':644,'model_calls_planned':0,'gold_visible_to_predictor':False}
    write('parser_configuration.json',config)
    # Six already independently reviewed development examples, kept in their
    # original complete structural group. Prepared with no heldout access.
    pop=load(R/'search_v2c_c5d_validation_population.json');ids=set(pop['ids'])
    development=[json.loads(s) for s in (R/'search_v2c_c2_v2_development.jsonl').read_text(encoding='utf8').splitlines()]
    cases=[r for r in development if r['query_id'] in ids];assert len(cases)==6
    alias={'GLOBAL':'GLOBAL','PUBLIC_PATRON':'PUBLIC_TENANT_PATRON','PUBLIC_STAFF':'PUBLIC_TENANT_STAFF','PRIVATE_PATRON':'PRIVATE_TENANT_PATRON','PRIVATE_STAFF':'PRIVATE_TENANT_STAFF'}
    packet=[{'case_id':r['query_id'],'query_text':r['query_text'],'scope_type':alias[r['scope_type']],
             'workspace_type':r['workspace_type'],'search_mode':r['search_mode']} for r in cases]
    vprefix=P+'validation_'
    with (R/(vprefix+'parser_inputs.jsonl')).open('x',encoding='utf8') as out:
        for r in packet:out.write(json.dumps(r,sort_keys=True)+'\n')
    validation={**config,'input_sha256':sha(R/(vprefix+'parser_inputs.jsonl')),'prediction_calls_planned':6,'candidate_parser_calls_planned':6}
    with (R/(vprefix+'parser_configuration.json')).open('x',encoding='utf8') as out:out.write(json.dumps(validation,sort_keys=True,indent=2)+'\n')
    write('evaluation_protocol.json',{'primary_eligible':644,'new_core':594,'retained_originals':50,'excluded':380,
       'eligible_source':str(R/'search_v2c_c5c_eligibility.json'),'masks_source':str(R/'search_v2c_c5b_expected_labels.jsonl'),
       'baseline_predictions_sha256':sha(R/'search_v2c_c5c_predictions.jsonl'),'candidate_freeze_sha256':sha(R/(P+'candidate_freeze.json')),
       'primary_attempts_planned':1,'tuning_after_measurement':False,'same_corpus_warning':'Designed after C5C error inspection; development assessment only.',
       'additional_development_contexts':6,'development_groups':1,'development_topology_overlap':0,'independent_safety_validation':'Unavailable: six positive cases only.',
       'native_tests':'No production/native transactions; one transformer-dependent test excluded from pure namespace-adapted suite. Production native modules preserved.',
       'diagnostic_candidate_parser_calls':7,'unit_regression_passes':1373,'unit_development_failures_retained':13,
       'contract':'Existing EXECUTABLE_WITH_NOTICE enum used only for bounded source-backed repairs. Copied C4 assessment code unchanged. No confidence thresholds.'})
    print(json.dumps({'candidate_frozen':True,'files':len(files),'regressions_passed':1373,'primary_calls_planned':644,'additional_development_calls':6}))

if __name__=='__main__':main()
