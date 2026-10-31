"""Frozen notice applicability wrapper around the established strict scalar scorer."""
from scripts.search_v2c_c5er_evaluation_adapter_v2 import score as original_score, summary
from scripts.search_v2c_c5er_evaluation_adapter_v2 import mask_for,APPLICABLE,norm


def score(gold, prediction):
    r=original_score(gold,prediction)
    r['exact_subtype_applicable']=gold.get('notice_policy')!='OPTIONAL'
    r['exact_typed_correct']=r['typed_correct']
    if not r['exact_subtype_applicable']:
        allowed=gold['acceptable_decisions']
        assert set(allowed)=={'EXECUTABLE','EXECUTABLE_WITH_NOTICE'} and gold['expected_executable'] is True
        r['accepted_decisions']=allowed
        r['typed_correct']=r['valid_output'] and r['decision'] in allowed
        if r['typed_correct']:
            r['mismatches'].pop('decision',None)
        r['all_scored_dimensions_correct']=r['valid_output'] and not r['mismatches']
    # Complete native projection axes omitted by the legacy scalar list.
    # Only independently reviewed masks supply these oracles.
    raw=prediction.get('actual_plan',{}) if isinstance(prediction,dict) else {}
    if r['valid_output']:
        for field,default in [('physical_available_only',False),('include_terms',[])]:
            mask=mask_for(gold,field)
            if mask['status'] not in APPLICABLE:
                r['scoring_excluded_fields'][field]=mask;continue
            expected=default if mask['status']=='APPLICABLE_ABSENCE' else mask.get('resolved_value',gold['expected_hard_constraints'].get(field))
            actual=raw.get(field)
            typed=type(actual) is bool if field=='physical_available_only' else isinstance(actual,list) and all(isinstance(x,str) for x in actual)
            correct=typed and norm(actual)==norm(expected)
            r['assertions'].append(dict(field=field,expected=expected,actual=actual,correct=correct,mask=mask,partial=False))
            if not correct:
                r['mismatches'][field]=dict(expected=expected,actual=actual)
                if r['execution'] is True:r['critical_executed_operand_mismatches'].append(field)
        if r['execution'] is True and any(a['field']=='sort' and not a['correct'] for a in r['assertions']):
            r['critical_executed_operand_mismatches'].append('sort')
        r['all_scored_dimensions_correct']=not r['mismatches']
    return r
