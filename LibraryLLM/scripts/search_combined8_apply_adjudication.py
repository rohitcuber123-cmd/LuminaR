"""New prospective source-adjudicated gold; original author/reviewer artifacts untouched."""
from pathlib import Path
import json,hashlib
from scripts.search_v2c_c5er_evaluation_adapter_v2 import check_gold,OPERANDS,mask_for

R=Path('reports');P='search_combined8_'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    original=[json.loads(s) for s in (R/(P+'reviewed_population.jsonl')).read_text(encoding='utf-8').splitlines()]
    adj=json.loads((R/(P+'blind_source_adjudication.json')).read_text(encoding='utf-8'))
    by={x['case_id']:x for x in adj['rows']};assert len(by)==51
    final=[];updates=[]
    for g in original:
        q=dict(g);a=by.get(g['case_id'])
        if a:
            assert g['query_text']==a['query_text'] and hashlib.sha256(g['query_text'].encode()).hexdigest()==a['input_query_sha256']
            assert not a['exclude_from_acceptance']
            for key in ['expected_typed_decision','expected_executable','expected_hard_constraints','notice_policy','acceptable_decisions']:
                q[key]=a[key]
            q['metric_applicability']={**g['metric_applicability'],**a['metric_applicability']}
            q['decision_stratum']=q['expected_typed_decision']
            q['semantic_justification']=a['decision_rationale']
            q['source_adjudication']='reports/search_combined8_blind_source_adjudication.json'
            q['expected_unadapted_mandatory_assertions']=a['unadapted_source_assertions']
            updates.append(g['case_id'])
        check_gold(q)
        if q['expected_executable']:
            assert all(mask_for(q,f)['status'] in ['APPLICABLE','APPLICABLE_ABSENCE'] for f in set(OPERANDS)|{'physical_available_only','include_terms'})
        final.append(q)
    with (R/(P+'reviewed_population_r1.jsonl')).open('x',encoding='utf-8') as f:
        for g in final:f.write(json.dumps(g,sort_keys=True,ensure_ascii=False)+'\n')
    with (R/(P+'review_reconciliation_final.json')).open('x',encoding='utf-8') as f:
        json.dump(dict(status='SOURCE_ONLY_RECONCILIATION_COMPLETE_BEFORE_PRIMARY',contexts=len(final),adjudicated=updates,
                       author_and_reviewer_originals_preserved=True,source_queries_changed=0,whole_case_exclusions=5,
                       scalar_uncertainties='Explicit N/A/UNRESOLVED masks with source-only rationale; blocked decisions remain strict',
                       author_acknowledgement='reports/search_combined8_author_reconciliation.json',
                       adjudication_sha256=sha(R/(P+'blind_source_adjudication.json')),new_gold_sha256=sha(R/(P+'reviewed_population_r1.jsonl')),
                       candidate_predictions_visible=False,human_reviewers=0),f,indent=2)
    print(json.dumps(dict(contexts=len(final),adjudicated=len(updates),queries_changed=0,predictions_seen=False)))

if __name__=='__main__':main()
