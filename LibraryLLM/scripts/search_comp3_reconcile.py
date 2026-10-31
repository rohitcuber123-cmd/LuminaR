"""Preprediction normative reconciliation; adopts the blind definitive review."""
from pathlib import Path
from collections import Counter
import json,hashlib
from scripts.search_v2c_c5er_evaluation_adapter_v2 import check_gold,OPERANDS

R=Path('reports');P='search_comp3_'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    authorpath=R/(P+'authored_v2.jsonl');reviewpath=R/(P+'independent_review.json')
    author={x['case_id']:x for x in map(json.loads,authorpath.read_text(encoding='utf8').splitlines())}
    reviewed=json.loads(reviewpath.read_text(encoding='utf8'))
    assert not reviewed.get('uncertainties'), 'Independent normative uncertainties must be resolved before any scoring'
    review={x['case_id']:x for x in reviewed['rows']}
    assert len(author)==len(review)==150 and set(author)==set(review)
    stratum={'EXECUTABLE':'CLEAR_EXECUTABLE','EXECUTABLE_WITH_NOTICE':'SAFE_UNCERTAIN_EXECUTABLE','AMBIGUOUS':'AMBIGUOUS',
        'INCOMPLETE':'INCOMPLETE','UNSUPPORTED':'UNSUPPORTED','CONTRADICTORY':'CONTRADICTORY'}
    out=[];differences=[];decisions=[]
    fields=['expected_typed_decision','expected_executable','expected_hard_constraints','metric_applicability','expected_sort',
        'expected_semantic_remainder','expected_soft_preferences','unadapted_mandatory_assertions','semantic_justification']
    for case_id,a in author.items():
        b=review[case_id]
        for k in ['case_id','query_text','scope_type','workspace_type','search_mode']:assert a[k]==b[k],(case_id,k)
        missing=set(OPERANDS)-set(b['metric_applicability']);assert not missing,(case_id,missing)
        changes={k:{'author':a.get(k),'reviewer':b.get(k)} for k in fields if a.get(k)!=b.get(k)}
        if changes:differences.append({'case_id':case_id,'changes':changes,'resolution':'Adopt independent query-only normative review before any predictions; original author labels preserved.'})
        if a['expected_typed_decision']!=b['expected_typed_decision']:decisions.append({'case_id':case_id,'author':a['expected_typed_decision'],'reviewer':b['expected_typed_decision']})
        final={**a,**{k:b[k] for k in fields if k in b}}
        final['decision_stratum']=stratum[final['expected_typed_decision']]
        final['review_status']='AI_REVIEWED_INDEPENDENT'
        final['review_provenance']={'artifact_sha256':sha(reviewpath),'author_sha256':sha(authorpath),'prediction_access':False}
        check_gold(final);out.append(final)
    cells=Counter((g['scope_type'],g['decision_stratum']) for g in out)
    assert len(cells)==30 and min(cells.values())>0,'Fresh population must cover all30 scope/stratum cells'
    with (R/(P+'reviewed_population.jsonl')).open('x',encoding='utf8') as f:
        for g in out:f.write(json.dumps(g,ensure_ascii=False,sort_keys=True)+'\n')
    reconciliation={'status':'COMPLETE_DEFINITIVE','count':len(out),'human_assistance_count':0,'author_sha256':sha(authorpath),
        'review_sha256':sha(reviewpath),'semantic_decision_changes':decisions,'changes':differences,'unresolved_disagreements':[],
        '30_actual_cells':[{'scope':s,'stratum':t,'count':n} for (s,t),n in sorted(cells.items())],
        'all_cells_exactly_five':all(n==5 for n in cells.values()),'predictions_not_started':not (R/(P+'independent_prediction_started.json')).exists(),
        'gold_sha256':sha(R/(P+'reviewed_population.jsonl'))}
    assert reconciliation['predictions_not_started']
    with (R/(P+'review_reconciliation.json')).open('x',encoding='utf8') as f:json.dump(reconciliation,f,indent=2,ensure_ascii=False)
    print(json.dumps({'count':len(out),'decision_changes':decisions,'all_cells_exactly_five':reconciliation['all_cells_exactly_five']}))
if __name__=='__main__':main()
