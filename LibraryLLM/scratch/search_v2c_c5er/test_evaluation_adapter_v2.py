from copy import deepcopy
import pytest
from scripts.search_v2c_c5er_evaluation_adapter_v2 import score,check_gold

def case():return {'case_id':'MASK-CONTRACT','scope_type':'GLOBAL','decision_stratum':'INCOMPLETE','expected_typed_decision':'INCOMPLETE','expected_executable':False,
    'expected_hard_constraints':{'subjects':['History']},'metric_applicability':{'hard_constraints.subjects':{'status':'PARTIALLY_APPLICABLE'},
        'hard_constraints.author_text':{'status':'UNRESOLVED'},'hard_constraints.exclude_terms':{'status':'APPLICABLE_ABSENCE'},
        'language':{'status':'N/A'},'semantic_remainder':{'status':'N/A'}},'expected_semantic_remainder':[{'kind':'optional','text':'concise'}]}
def output():return {'typed_decision':'EXECUTABLE','executable':True,'actual_plan':{'subjects':['History','Physics'],'author_text':'invented','exclude_terms':[],'language':'French','semantic_text':'concise'}}
def test_prefixed_partial_unknown_and_inapplicable():
    r=score(case(),output())
    assertions={a['field']:a for a in r['assertions']}
    assert assertions['subjects']['correct'] and assertions['exclude_terms']['correct']
    assert 'author_text' not in assertions and 'language' not in assertions and 'semantic_text' not in assertions
    assert 'execution_allowed' in r['mismatches'] and 'decision' in r['mismatches']
def test_absence_does_not_hide_invented_negative():
    p=output();p['actual_plan']['exclude_terms']=['extra'];r=score(case(),p)
    assert 'exclude_terms' in r['mismatches'] and 'exclude_terms' in r['critical_executed_operand_mismatches']
def test_conflicting_alias_masks_fail_before_scoring():
    g=case();g['metric_applicability']['subjects']={'status':'UNRESOLVED'}
    with pytest.raises(AssertionError):check_gold(g)
def test_both_only_not_exclusive_format_normalization():
    g=case();g['expected_hard_constraints'].update(formats=['BOTH'],exclusive_formats=['BOTH'])
    g['metric_applicability'].update(formats={'status':'APPLICABLE'},exclusive_formats={'status':'APPLICABLE'})
    p=output();p['actual_plan'].update(formats=['ONLINE','PHYSICAL'],exclusive_formats=['ONLINE','PHYSICAL'])
    a={x['field']:x['correct'] for x in score(g,p)['assertions']}
    assert a['formats'] and not a['exclusive_formats']

def test_executed_exclusive_bound_difference_is_critical():
    g=case();g['expected_hard_constraints'].update(rating_min=4,rating_min_exclusive=True)
    g['metric_applicability'].update(rating_min={'status':'APPLICABLE'},rating_min_exclusive={'status':'APPLICABLE'})
    p=output();p['actual_plan'].update(rating_min=4,rating_min_exclusive=False)
    assert 'rating_min_exclusive' in score(g,p)['critical_executed_operand_mismatches']

def test_both_equivalent_mask_aliases():
    g=case();g['metric_applicability'].update(formats={'status':'APPLICABLE','resolved_value':['BOTH']})
    g['metric_applicability']['hard_constraints.formats']={'status':'APPLICABLE','resolved_value':['ONLINE','PHYSICAL']}
    p=output();p['actual_plan']['formats']=['ONLINE','PHYSICAL']
    assert next(a['correct'] for a in score(g,p)['assertions'] if a['field']=='formats')

def test_partial_scalar_and_explicit_null_alias_are_invalid():
    g=case();g['metric_applicability']['sort']={'status':'PARTIALLY_APPLICABLE'}
    with pytest.raises(AssertionError):check_gold(g)
    g=case();g['expected_hard_field_masks']={'subjects':None}
    with pytest.raises(AssertionError):check_gold(g)

def test_invalid_executed_blocked_row_stays_false_execution():
    from scripts.search_v2c_c5er_evaluation_adapter_v2 import summary
    p=output();p['typed_decision']='INVALID';p['actual_plan']={}
    result=summary([score(case(),p)])
    assert result['false_execution']['numerator']==result['false_execution']['denominator']==1
    assert result['typed_accuracy']['denominator']==result['execution_accuracy']['denominator']==1
    assert result['execution_accuracy']['numerator']==0 and result['invalid_outputs']==1

@pytest.mark.parametrize('malformed',[None,[],"plan",{'formats':7},{'subjects':['History',7]},{'subjects':[{'term':'History'}]}])
def test_malformed_plan_cannot_drop_blocked_gold(malformed):
    from scripts.search_v2c_c5er_evaluation_adapter_v2 import summary
    p=output();p['actual_plan']=malformed
    r=score(case(),p);s=summary([r])
    assert not r['valid_output'] and s['contexts']==1 and s['false_execution']['numerator']==s['false_execution']['denominator']==1

def test_malformed_assessment_is_invalid_not_exception():
    p=output();p['assessment']=[]
    assert not score(case(),p)['valid_output']

def test_known_absent_sort_requires_native_default_and_unknown_has_no_oracle():
    g=case();g['expected_sort']=None;g['metric_applicability']['sort']={'status':'APPLICABLE_ABSENCE'}
    p=output();p['actual_plan']['sort']='TITLE'
    assert 'sort' in score(g,p)['mismatches']
    g['expected_sort']='TITLE'
    with pytest.raises(AssertionError):check_gold(g)
    g=case();g['metric_applicability']['semantic_remainder']={'status':'UNRESOLVED','resolved_value':'invented'}
    with pytest.raises(AssertionError):check_gold(g)
