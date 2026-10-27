"""Frozen independently authored predicate/eligibility review, not output mirroring."""
import json,re
from pathlib import Path
import pytest
from search.query_plan import parse_query,matches
from search.query_session import refine,item_edit_key
from search.query_confidence import executable
from search.query_interaction import transformer

R=Path(__file__).resolve().parents[1]/'reports'
INPUT=json.loads((R/'search_v2c_c4_review_query_only_input.json').read_text())
ADDITIONAL=json.loads((R/'search_v2c_c4_additional_review_query_input.json').read_text())
QUERIES={r['review_id']:r for r in INPUT['queries']+ADDITIONAL['queries']}
AUTHORED=json.loads((R/'search_v2c_c4_blind_contract_authored.json').read_text())['records']
CONTRACT=json.loads((R/'search_v2c_c4_reviewed_contract.json').read_text())
def norm(value):
    if isinstance(value,list):return sorted(norm(v) for v in value)
    if isinstance(value,str):return ' '.join(value.casefold().split())
    return value
def build(record):
    row=QUERIES[record['review_id']]
    facets=INPUT['CANONICAL_REVIEW']['subjects'] if row['scope']=='CANONICAL_REVIEW' else INPUT['scopes'][row['scope']]['subjects']
    if row.get('prior_query'):
        prior=parse_query(row['prior_query'],facets);plan,_=refine(prior,row['query'],facets)
    else:plan=parse_query(row['query'],facets,row['mode'])
    action=row.get('post_action')
    if isinstance(action,dict):
        plan=parse_query(row['query'],facets,row['mode'],omit=[item_edit_key('subject',action['remove_subject']),item_edit_key('exclude',action['remove_excluded_subject'])])
    elif action:
        plan=transformer({'query':row['query'],'mode':'SMART','filters':{},'omit':[]},{'operation':'subject','action':'exclude','subjects':['Romance']},None)(plan,facets,{})
    return plan

@pytest.mark.parametrize('record',AUTHORED,ids=lambda r:r['review_id'])
def test_frozen_independent_contract(record):
    plan=build(record);expected=CONTRACT['records'][record['review_id']]
    for key,value in expected.items():
        actual=plan.decision['decision_type'] if key=='decision' else executable(plan) if key=='executable' else getattr(plan,key)
        assert norm(actual)==norm(value),(key,value,actual)
    for example in record['eligibility_examples']:
        if example['eligible'] is None:continue
        candidate=dict(example['candidate'])
        if 'author' in candidate:candidate['authors']=[candidate.pop('author')]
        if 'isbn' in candidate:
            value=candidate.pop('isbn');compact=re.sub(r'[-\s]','',value)
            candidate['isbn_13' if len(compact)==13 else 'isbn_10']=value
        if 'rating' in candidate:candidate['rating_count']=1
        assert matches(plan,candidate) is example['eligible'],example['reason']
