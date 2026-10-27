"""Rescore only saved final plans against inherited C3 gold. Zero parser calls."""
import json
from scripts.search_v2c_c4_evaluate import (R,read_json,read_rows,development_population,rescore,metrics_for,write,verify_frozen)

def main():
    verify_frozen()
    actual = {r['query_id']:r for r in read_rows(R/'search_v2c_c4_development_observations.jsonl')}
    overrides = read_json(R/'search_v2c_c3_development_label_overrides.json')['overrides']
    cases = [r for r in development_population() if not r.get('requires_native_execution')]
    assert len(actual) == len(cases) == 6529
    rows = [rescore({**case,**overrides.get(case['query_id'],{})},actual[case['query_id']],normalize_formats=True) for case in cases]
    write('search_v2c_c4_inherited_c3_label_metrics.json',{'view':'C4 retained final plans against frozen inherited C3 effective labels; no new C4 label corrections',
        'parser_calls':0,'population':6529,'metrics':metrics_for(rows),
        'false_filter_ids':[r['query_id'] for r in rows if r['false_filters']],
        'role':'Side-by-side transparency only. Current gate uses independently reviewed current contract; original labels and denominators remain retained.'})
    print(json.dumps({'parser_calls':0,'inherited_C3_false_filters':sum(bool(r['false_filters']) for r in rows)}))

if __name__ == '__main__':
    main()
