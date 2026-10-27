"""Regression only: frozen C4 development population and contracts, C5 outputs."""
import json,time
from scripts.search_v2c_c5_prepare import R,P,read,rows,write,sha

def main():
    from scripts.search_v2c_c4_evaluate import prepare,rescore,metrics_for,violations_for,verify_frozen
    verify_frozen(['reports/search_v2c_c4_development_label_overrides.json'])
    cases,overrides,_,_=prepare('reports/search_v2c_c4_development_label_overrides.json')
    with (R/(P+'development_started.json')).open('x') as out:json.dump({'evaluator_sha256':sha(__file__),'purpose':'Regression only; not used to select candidate thresholds','parser_rows':6529},out)
    from scripts.search_v2c_c_evaluate import evaluate_case
    scopes=read(R/'search_v2c_c_scope_vocabularies.json');observed=[];errors=[];start=time.perf_counter()
    for c in cases:
        if c.get('requires_native_execution'):continue
        try:
            raw=evaluate_case(c,scopes);observed.append(rescore({**c,**overrides.get(c['query_id'],{})},raw,normalize_formats=True))
        except Exception as error:errors.append({'id':c['query_id'],'error':repr(error)})
    m=metrics_for(observed);violations=violations_for(m)
    assert not errors and len(observed)==6529
    expected=read(R/'search_v2c_c4_development_metrics.json')['reviewed_v2_label_metrics']
    differences={k:{'C4':v,'C5':m[k]} for k,v in expected.items() if v!=m[k]}
    write('development_safety_regression.json',{'status':'PASS' if not violations and not differences else 'FAIL','parser_cases':len(observed),'native_cases':'Measured separately; historical C4 native352 not rerun as part of this parser-only count',
        'metrics':m,'C4_metric_differences':differences,'mandatory_violations':violations,'errors':errors,'elapsed_s':time.perf_counter()-start,
        'parser_source_changed':False,'policy_activated':False,'plan_metrics_vs_final_execution':'Identical: current C4 policy retained. Candidate simulations are separately reported, never counted as parser accuracy gains.',
        'calibration_threshold_selection_used_these_outputs':False,'heldout_invocations':0})
    verify_frozen(['reports/search_v2c_c4_development_label_overrides.json'])
    print(json.dumps({'status':'PASS' if not violations and not differences else 'FAIL','cases':len(observed),'C4_metric_differences':differences,'mandatory_violations':violations}))

if __name__=='__main__':main()
