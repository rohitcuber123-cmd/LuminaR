"""Evaluate V9 prototype on:
1. The 72-query reviewed development cohort (reports/search_arch9_dev_reviewed.jsonl)
2. All 205 exposed V8 primary cases (reports/search_combined8_reviewed_population_r1.jsonl)
Save predictions and comprehensive evaluation summaries.
"""
import sys, json, time, hashlib
sys.path.insert(0, '.')
from pathlib import Path
from dataclasses import asdict
from collections import Counter
from scripts.search_combined8_score_adapter import score
from scripts.search_v2c_c5er_evaluation_adapter_v2 import summary
from scratch.search_architecture_v10.parser import parse_query, validate, executable, assess

R = Path('reports')

def eval_cohort(name, gold_path, out_prefix):
    caps = json.loads((R / 'search_v2c_c5a_capability_matrix.json').read_text(encoding='utf-8'))['scopes']
    gold = [json.loads(line) for line in (R / gold_path).read_text(encoding='utf-8').splitlines()]
    
    predictions = []
    latencies = []
    
    for g in gold:
        st = time.perf_counter()
        c = caps[g['scope_type']]
        p = validate(parse_query(g['query_text'], c['subjects'], g['search_mode']), c['capabilities'])
        elapsed = (time.perf_counter() - st) * 1000
        latencies.append(elapsed)
        predictions.append({
            'case_id': g['case_id'],
            'status': 'CAPTURED',
            'typed_decision': p.decision['decision_type'],
            'executable': executable(p),
            'actual_plan': asdict(p),
            'assessment': assess(p),
            'elapsed_ms': elapsed
        })
        
    results = [score(g, p) for g, p in zip(gold, predictions)]
    sum_stats = summary(results)
    
    # Stratify by length bucket if available
    stratified_length = {}
    for g, p, r in zip(gold, predictions, results):
        bucket = g.get('author_length_bucket')
        if not bucket:
            qlen = len(g['query_text'])
            bucket = 'short' if qlen <= 60 else 'medium' if qlen <= 150 else 'long' if qlen <= 300 else 'very_long'
        if bucket not in stratified_length:
            stratified_length[bucket] = {'total': 0, 'typed_correct': 0, 'exec_correct': 0, 'false_exec': 0, 'missed_exec': 0}
        st = stratified_length[bucket]
        st['total'] += 1
        if r['typed_correct']: st['typed_correct'] += 1
        if r['execution_correct']: st['exec_correct'] += 1
        if r['expected_execution'] is False and r['execution'] is True: st['false_exec'] += 1
        if r['expected_execution'] is True and r['execution'] is not True: st['missed_exec'] += 1

    # Stratify by family
    stratified_family = {}
    for g, p, r in zip(gold, predictions, results):
        fam = g.get('family_id') or g.get('reviewed_family') or 'unknown'
        if fam not in stratified_family:
            stratified_family[fam] = {'total': 0, 'typed_correct': 0, 'exec_correct': 0, 'false_exec': 0, 'missed_exec': 0}
        sf = stratified_family[fam]
        sf['total'] += 1
        if r['typed_correct']: sf['typed_correct'] += 1
        if r['execution_correct']: sf['exec_correct'] += 1
        if r['expected_execution'] is False and r['execution'] is True: sf['false_exec'] += 1
        if r['expected_execution'] is True and r['execution'] is not True: sf['missed_exec'] += 1

    report = {
        'cohort': name,
        'total_cases': len(gold),
        'summary': sum_stats,
        'latency_ms': {
            'mean': sum(latencies) / len(latencies),
            'p50': sorted(latencies)[len(latencies) // 2],
            'p95': sorted(latencies)[int(len(latencies) * 0.95)],
            'max': max(latencies)
        },
        'stratified_by_length': stratified_length,
        'stratified_by_family': stratified_family,
        'confusion': dict(Counter(g['expected_typed_decision'] + ' -> ' + p['typed_decision'] for g, p in zip(gold, predictions))),
        'critical_executed_operands': [r for r in results if r['critical_executed_operand_mismatches']],
        'false_executions': [r for r in results if r['expected_execution'] is False and r['execution'] is True],
        'missed_executions': [r for r in results if r['expected_execution'] is True and r['execution'] is not True],
        'failures': [r for r in results if not r['typed_correct'] or not r['execution_correct'] or r['critical_executed_operand_mismatches']]
    }
    
    # Write predictions
    pred_path = R / f'{out_prefix}_predictions.jsonl'
    with pred_path.open('x', encoding='utf-8') as f:
        for p in predictions:
            f.write(json.dumps(p, ensure_ascii=False) + '\n')
            
    # Write report
    res_path = R / f'{out_prefix}_results.json'
    with res_path.open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    print(f"=== {name} ===")
    print(f"Total: {len(gold)}")
    print(f"Typed Accuracy: {sum_stats['typed_accuracy']}")
    print(f"Execution Accuracy: {sum_stats['execution_accuracy']}")
    print(f"False Execution: {sum_stats['false_execution']}")
    print(f"Missed Execution: {sum_stats['missed_execution']}")
    print(f"Critical Operands: {len(report['critical_executed_operands'])}")
    print(f"Latency p50: {report['latency_ms']['p50']:.2f}ms, p95: {report['latency_ms']['p95']:.2f}ms")
    return report

def main():
    print("Evaluating 72-query reviewed dev cohort...")
    eval_cohort('search_arch10_dev72', 'search_arch9_dev_reviewed.jsonl', 'search_arch10_dev72')
    print("\nEvaluating 205 exposed V8 cases...")
    eval_cohort('search_arch10_v8exposed205', 'search_combined8_reviewed_population_r1.jsonl', 'search_arch10_v8exposed205')

if __name__ == '__main__':
    main()
