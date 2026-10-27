from pathlib import Path
def main():
    source=Path('scripts/search_v2c_c5er_evaluation_adapter.py').read_text(encoding='utf8')
    source=source.replace("and not x['field'].endswith('_exclusive')",'')
    with Path('scripts/search_v2c_c5er_evaluation_adapter_v2.py').open('x',encoding='utf8') as f:f.write(source)
    source=Path('scratch/search_v2c_c5er/test_evaluation_adapter.py').read_text(encoding='utf8').replace('search_v2c_c5er_evaluation_adapter','search_v2c_c5er_evaluation_adapter_v2')
    source+='''
def test_executed_exclusive_bound_difference_is_critical():
    g=case();g['expected_hard_constraints'].update(rating_min=4,rating_min_exclusive=True)
    g['metric_applicability'].update(rating_min={'status':'APPLICABLE'},rating_min_exclusive={'status':'APPLICABLE'})
    p=output();p['actual_plan'].update(rating_min=4,rating_min_exclusive=False)
    assert 'rating_min_exclusive' in score(g,p)['critical_executed_operand_mismatches']
'''
    with Path('scratch/search_v2c_c5er/test_evaluation_adapter_v2.py').open('x',encoding='utf8') as f:f.write(source)
if __name__=='__main__':main()
