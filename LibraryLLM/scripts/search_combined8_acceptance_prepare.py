"""Bind independently reviewed normative gold and structural eligibility before primary."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import hashlib,json
from scripts.search_v2c_c5er_evaluation_adapter_v2 import check_gold,OPERANDS,mask_for,APPLICABLE

R=Path('reports');P='search_combined8_'
def load(n):return json.loads((R/(P+n+'.json')).read_text(encoding='utf-8'))
def rows(n):return [json.loads(s) for s in (R/(P+n+'.jsonl')).read_text(encoding='utf-8').splitlines()]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(n,d):
    with (R/(P+n+'.json')).open('x',encoding='utf-8') as f:json.dump(d,f,indent=2,ensure_ascii=False)


def main():
    source=load('source_freeze');assert all(sha(p)==h for p,h in source['files'].items())
    authored=rows('authored');review=rows('independent_review');mapping=load('reviewer_id_map')
    reviewed={mapping[x['review_id']]:x for x in review}
    assert set(reviewed)=={g['case_id'] for g in authored}
    structural=load('authored_sealed_structural_isolation')
    forbidden={x['new_case_id'] for x in structural['colliding_new_rows'] if x['required_action']=='DISCARD_NEW_CASE'}
    forbidden.update(x['new_case_id'] for x in load('authored_structural_isolation')['additional_exposed_collisions'])
    final=[];changes=[];excluded=[]
    keys=['expected_typed_decision','expected_executable','expected_hard_constraints','metric_applicability','expected_sort','expected_semantic_remainder','expected_soft_preferences','expected_source_roles','expected_completion','semantic_justification','notice_policy','acceptable_decisions','expected_unadapted_mandatory_assertions','expected_notices']
    for g in authored:
        r=reviewed[g['case_id']]
        assert all(k in r for k in ['expected_typed_decision','expected_executable','expected_hard_constraints','metric_applicability','semantic_justification'])
        if g['case_id'] in forbidden:
            excluded.append(dict(case_id=g['case_id'],reason='DISCARDED_STRUCTURAL_COLLISION_BEFORE_PRIMARY'));continue
        if r.get('exclude_from_acceptance'):
            excluded.append(dict(case_id=g['case_id'],reason=r.get('exclusion_reason','Unresolved normative source semantics')));continue
        q={k:v for k,v in g.items() if k not in keys}
        q.update({k:r[k] for k in keys if k in r})
        q['decision_stratum']=q['expected_typed_decision'];q['review_status']='INDEPENDENT_AI_REVIEWED_BEFORE_PRIMARY';q['independent_review_id']=r['review_id']
        assert len(q['query_text'])<=500 and q['query_text']==g['query_text']
        check_gold(q)
        if q['expected_executable']:
            assert all(mask_for(q,f)['status'] in ['APPLICABLE','APPLICABLE_ABSENCE'] for f in set(OPERANDS)|{'physical_available_only','include_terms'}),(q['case_id'],'Incomplete executable native oracle')
            assert q['metric_applicability'].get('sort',{}).get('status') in ['APPLICABLE','APPLICABLE_ABSENCE']
        if q.get('notice_policy')=='OPTIONAL':assert set(q['acceptable_decisions'])=={'EXECUTABLE','EXECUTABLE_WITH_NOTICE'} and q['expected_executable']
        diffs={k:dict(author=g.get(k),reviewer=r.get(k)) for k in keys if k in r and g.get(k)!=r.get(k)}
        if diffs:changes.append(dict(case_id=q['case_id'],changes=diffs))
        final.append(q)
    # Review reconciliation is recorded before population isolation and prediction.
    with (R/(P+'reviewed_population.jsonl')).open('x',encoding='utf-8') as f:
        for g in final:f.write(json.dumps(g,ensure_ascii=False,sort_keys=True)+'\n')
    save('review_reconciliation',dict(contexts=len(final),author_contexts=len(authored),changed_records=len(changes),changes=changes,excluded=excluded,
                                    author_and_reviewer_blind_to_predictions=True,original_author_preserved=True,reviewer_gold_is_prospective=True,human_reviewers=0,
                                    unresolved_disagreements='Excluded with reasons; never forced to candidate outputs'))
    print(json.dumps(dict(reviewed_population_created=len(final),changed_records=len(changes),excluded=len(excluded))))


if __name__=='__main__':main()
