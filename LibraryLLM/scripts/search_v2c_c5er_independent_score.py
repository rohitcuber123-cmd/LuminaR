"""Independent acceptance scoring for C5E-R candidate V4.

Uses evaluation adapter V2; no parser calls or gold mutations.
"""
import sys
from pathlib import Path
if str(Path.cwd()) not in sys.path:
    sys.path.insert(0, str(Path.cwd()))

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib, json

from scripts.search_v2c_c5er_evaluation_adapter_v2 import score, summary, OPERANDS, LISTS, rate, KINDS

R = Path('reports')
P = 'search_v2c_c5er_independent_'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def load(p):
    return json.loads(Path(p).read_text(encoding='utf8'))

def rows(p):
    return [json.loads(s) for s in Path(p).read_text(encoding='utf8').splitlines() if s.strip()]

def write(n, v):
    with (R / (P + n)).open('x', encoding='utf8') as f:
        json.dump(v, f, indent=2, ensure_ascii=False, sort_keys=True)

def main():
    config = load(R / (P + 'parser_configuration.json'))
    freeze = load(R / 'search_v2c_c5er_candidate_freeze.json')
    assert all(sha(p) == h for p, h in freeze['files'].items())

    complete = load(R / (P + 'prediction_complete.json'))
    predpath = R / (P + 'predictions.jsonl')
    assert sha(predpath) == complete['prediction_sha256']
    assert complete['parser_calls'] == config['prediction_calls_planned'] and complete['retries'] == 0 and not complete['isolation_denials']

    population = Path(config['gold_population_path'])
    assert sha(population) == config['gold_population_sha256']

    write('scoring_started.json', {
        'at_utc': datetime.now(timezone.utc).isoformat(),
        'predictions_sha256': sha(predpath),
        'gold_access_after_completed_capture': True,
        'parser_calls': 0
    })

    def prohibit(frame, event, arg):
        if event == 'call' and frame.f_code.co_name == 'parse_query':
            raise RuntimeError('No parser calls during scoring')
    sys.setprofile(prohibit)

    gold_rows = rows(population)
    gold = {x['case_id']: x for x in gold_rows}
    pred = rows(predpath)
    assert len(gold) == len(pred) == 150 and set(gold) == {p['case_id'] for p in pred}

    scored = []
    fields = defaultdict(list)
    unadapted = []
    provenance = []

    for p in pred:
        g = gold[p['case_id']]
        actual = p.get('actual_plan', {})
        res = score(g, p)
        scored.append(res)

        for a in res['assertions']:
            fields[a['field']].append(a['correct'])

        q = g['query_text']
        notices = actual.get('decision', {}).get('repair_notices', []) if isinstance(actual, dict) else []
        verified = []
        for notice in notices:
            span = notice.get('source_span')
            good = isinstance(span, list) and len(span) == 2 and 0 <= span[0] < span[1] <= len(q) and q[span[0]:span[1]] == notice.get('from') and bool(notice.get('to'))
            verified.append(good)
        provenance.append({
            'case_id': g['case_id'],
            'notice_count': len(notices),
            'valid_source_provenance': sum(verified),
            'all_valid': all(verified)
        })

        for a in g.get('unadapted_mandatory_assertions', []):
            unadapted.append({'case_id': g['case_id'], 'assertion': a, 'status': 'PRESERVED_UNADAPTED_NOT_SCORED'})

    sys.setprofile(None)

    with (R / (P + 'scored_observations.jsonl')).open('x', encoding='utf8') as f:
        for x in scored:
            f.write(json.dumps(x, ensure_ascii=False, sort_keys=True) + '\n')

    overall = summary(scored)
    cells = [
        {'scope': scope, 'stratum': stratum, **summary([x for x in scored if x['scope'] == scope and x['stratum'] == stratum])}
        for scope in sorted({x['scope'] for x in scored})
        for stratum in sorted({x['stratum'] for x in scored})
    ]

    metrics = {
        'population': 'C5E-R fresh independent acceptance; 150 contexts across 30 cells',
        'overall': overall,
        '30_scope_stratum_cells': cells,
        'per_field': {k: rate(sum(v), len(v)) for k, v in sorted(fields.items())},
        'source_provenance': provenance,
        'unadapted_assertions': unadapted,
        'structured_advisory_accuracy': {'status': 'N/A', 'reason': 'No established structured-object to display-string oracle'},
        'scope_actor_accuracy': {'status': 'N/A', 'reason': 'Supplied context, not parser predictions'},
        'finite_sample_only': True,
        'norm_source': 'Evaluation adapter V2; strict prefixed scalar masks, formats-only BOTH equivalence',
        'gold_sha256': sha(population),
        'predictions_sha256': sha(predpath),
        'scorer_sha256': sha(__file__),
        'parser_calls_in_scoring': 0,
        'critical_execution_failures': [x['case_id'] for x in scored if x['expected_execution'] is False and x['execution'] is True],
        'missed_execution_cases': [x['case_id'] for x in scored if x['expected_execution'] is True and x['execution'] is False]
    }
    write('metrics.json', metrics)

    failures = {
        'rows': [x for x in scored if x['mismatches']],
        'total_failures': len([x for x in scored if x['mismatches']]),
        'all_failures_retained': True,
        'no_candidate_revision_or_retest': True,
        'classification': 'Operand mismatches under frozen field masks and strict unadjudicated representation differences. No equivalence invented.'
    }
    write('failures.json', failures)

    write('scoring_complete.json', {
        'at_utc': datetime.now(timezone.utc).isoformat(),
        'scored': len(scored),
        'parser_calls': 0,
        'metrics_sha256': sha(R / (P + 'metrics.json'))
    })

    print(json.dumps({
        'typed': overall['typed_accuracy'],
        'execution': overall['execution_accuracy'],
        'false_execution': overall['false_execution'],
        'missed_execution': overall['missed_execution']
    }))

if __name__ == '__main__':
    main()
