from copy import deepcopy
from scripts.search_combined8_score_adapter import score,summary


def fixture():
    g=dict(case_id='synthetic-scorer-check',scope_type='GLOBAL',decision_stratum='EXECUTABLE',expected_typed_decision='EXECUTABLE',expected_executable=True,
           expected_hard_constraints={'rating_min':4,'rating_min_exclusive':True},expected_sort='RELEVANCE',
           metric_applicability={'rating_min':{'status':'APPLICABLE'},'rating_min_exclusive':{'status':'APPLICABLE'},'author_text':{'status':'APPLICABLE_ABSENCE'}})
    p=dict(typed_decision='EXECUTABLE',executable=True,actual_plan={'rating_min':4,'rating_min_exclusive':True,'author_text':None},assessment={})
    return g,p


def test_optional_notice_never_relaxes_a_hard_operator():
    g,p=fixture();g.update(notice_policy='OPTIONAL',acceptable_decisions=['EXECUTABLE','EXECUTABLE_WITH_NOTICE'])
    p['typed_decision']='EXECUTABLE_WITH_NOTICE'
    r=score(g,p)
    assert r['typed_correct'] and not r['exact_subtype_applicable'] and not r['exact_typed_correct']
    assert r['all_scored_dimensions_correct']
    p['actual_plan']['rating_min_exclusive']=False
    r=score(g,p)
    assert not r['all_scored_dimensions_correct'] and 'rating_min_exclusive' in r['critical_executed_operand_mismatches']


def test_invented_author_is_critical_even_with_correct_decision():
    g,p=fixture();p['actual_plan']['author_text']='invented'
    r=score(g,p)
    assert r['typed_correct'] and 'author_text' in r['critical_executed_operand_mismatches']


def test_missing_output_stays_in_positive_denominator():
    g,p=fixture();s=summary([score(g,{})])
    assert s['typed_accuracy']['numerator']==0 and s['typed_accuracy']['denominator']==1
    assert s['missed_execution']['numerator']==s['missed_execution']['denominator']==1


def test_invalid_blocked_output_does_not_receive_execution_credit():
    g,p=fixture();g.update(expected_typed_decision='UNSUPPORTED',expected_executable=False)
    r=score(g,{'typed_decision':'UNSUPPORTED','executable':False})
    assert not r['valid_output'] and not r['execution_correct'] and not r['typed_correct']


def test_false_execution_cannot_be_hidden_by_partial_scalar_agreement():
    g,p=fixture();g.update(expected_typed_decision='UNSUPPORTED',expected_executable=False)
    s=summary([score(g,p)])
    assert s['false_execution']['numerator']==s['false_execution']['denominator']==1


def test_physical_availability_and_sort_are_critical_native_axes():
    g,p=fixture()
    g['expected_hard_constraints']['physical_available_only']=True
    g['metric_applicability']['physical_available_only']={'status':'APPLICABLE'}
    g['expected_sort']='NEWEST';g['metric_applicability']['sort']={'status':'APPLICABLE'}
    p['actual_plan'].update(physical_available_only=False,sort='RATING')
    r=score(g,p)
    assert {'physical_available_only','sort'} <= set(r['critical_executed_operand_mismatches'])
