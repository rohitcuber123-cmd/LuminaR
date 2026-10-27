from copy import deepcopy
import pytest
from scripts.search_v2c_c5er_evaluation_adapter import score,check_gold

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
