"""Metric contracts use synthetic plans, never benchmark answers."""
import pytest
from search.query_plan import QueryPlan
from search.query_confidence import decide
from scripts import search_v2c_c_evaluate as evaluate

SCOPES={'GLOBAL':{'subjects':['Fiction'],'capabilities':{'year':False}}}
def case(**kw):
 r={'query_id':'synthetic','family_id':'metric_test','split':'development','category':'unit','scope_type':'GLOBAL','query':'fiction','search_mode':'semantic','execution_allowed':True,'expected_decision':'EXECUTABLE','expected_subjects':['Fiction'],'expected_semantic_text':'','expected_soft_preferences':[],'expected_sort':None};r.update(kw);return r
def result(monkeypatch,p,c):
 monkeypatch.setattr(evaluate,'parse_query',lambda *a,**k:p)
 return evaluate.evaluate_case(c,SCOPES)
def test_legacy_mode_unspecified_sort_and_empty_soft_schema(monkeypatch):
 p=decide(QueryPlan('fiction','SMART',subjects=['Fiction']));assert result(monkeypatch,p,case())['exact']
def test_false_filter_is_not_missing_filter(monkeypatch):
 p=decide(QueryPlan('fiction','SMART',subjects=['Fiction'],rating_min=4))
 r=result(monkeypatch,p,case());assert r['false_filters']==[['rating_min','4.0',False]]
 p=decide(QueryPlan('fiction','SMART'));r=result(monkeypatch,p,case());assert r['hard_fn']==1 and not r['false_filters']
def test_contradiction_execution_is_unsafe_even_without_invented_atoms(monkeypatch):
 p=decide(QueryPlan('x','SMART',subjects=['Fiction']))
 r=result(monkeypatch,p,case(expected_decision='CONTRADICTORY',execution_allowed=False))
 assert r['unsafe_auto_parse'] and not r['false_filters']
def test_safe_literal_miss_is_separate_from_unsafe_hard_parse(monkeypatch):
 p=decide(QueryPlan('fiction 4','SMART',semantic_text='fiction 4'))
 r=result(monkeypatch,p,case(expected_decision='AMBIGUOUS',execution_allowed=False,expected_subjects=[]))
 assert not r['unsafe_auto_parse'] and r['safe_typed_decision_miss']
def test_invented_rating_on_ambiguous_input_is_unsafe(monkeypatch):
 p=decide(QueryPlan('fiction 4','SMART',rating_min=4))
 r=result(monkeypatch,p,case(expected_decision='AMBIGUOUS',execution_allowed=False,expected_subjects=[]));assert r['unsafe_auto_parse']
def test_native_case_cannot_be_counted_as_parser_security(monkeypatch):
 with pytest.raises(AssertionError):evaluate.evaluate_case(case(requires_native_execution=True),SCOPES)
def test_exclusive_comparator_changes_count_as_false_filter(monkeypatch):
 p=decide(QueryPlan('x','SMART',rating_min=3,rating_min_exclusive=False))
 r=result(monkeypatch,p,case(expected_subjects=[],expected_rating_min=3,rating_min_exclusive=True));assert r['false_filters'] and not r['comparator_correct']
def test_semantic_tokens_distinguish_technical_punctuation():
 assert evaluate.token_f1('C++','C')==0 and evaluate.token_f1('C#','C')==0
