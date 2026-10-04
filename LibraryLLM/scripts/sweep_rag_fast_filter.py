"""Replay frozen V8 adversarial evidence through the real deterministic filter."""
import ast
import json
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rag.fast_filter import compute_alignment_signals

tree = ast.parse((ROOT / 'scratch/run_v8_step6_final_eval.py').read_text(encoding='utf-8'))
cases = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == 'ADVERSARIAL_CASES' for t in n.targets))
results = []
for actor, event in [(1., .8), (.9, .7), (.8, .6), (.7, .5), (.6, .4)]:
    rows = []
    for c in cases:
        start = time.perf_counter()
        s = compute_alignment_signals(c['question'], c['intent_data'], c['evidence'])
        if s.polarity_mismatch or s.temporal_conflict or s.direction_inverted:
            decision = 'FAST_REJECT'
        elif s.actor_score >= actor and s.event_score >= event and s.polarity_aligned and s.temporal_aligned and s.relationship_check_passed and not s.mere_lexical_cooccurrence:
            decision = 'FAST_ACCEPT'
        else:
            decision = 'NEEDS_LLM_VALIDATION'
        rows.append({'id': c['id'], 'expected': c['expected_supported'], 'decision': decision,
                     'latency_ms': (time.perf_counter() - start) * 1000})
    results.append({'actor': actor, 'event': event, 'rows': rows,
        'false_accepts': sum(not r['expected'] and r['decision'] == 'FAST_ACCEPT' for r in rows),
        'false_rejects': sum(r['expected'] and r['decision'] == 'FAST_REJECT' for r in rows),
        'validator_calls': sum(r['decision'] == 'NEEDS_LLM_VALIDATION' for r in rows),
        'mean_ms': sum(r['latency_ms'] for r in rows) / len(rows)})
(ROOT / 'reports/rag_latency_threshold_sweep.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(json.dumps([{k: v for k, v in r.items() if k != 'rows'} for r in results], indent=2))
