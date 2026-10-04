"""Replay frozen V8 datasets against the single real evaluation API process."""
import argparse
import ast
import json
import sys
import time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rag.fast_filter import run_fast_filter


def dataset(filename, variable):
    tree = ast.parse((ROOT / 'scratch' / filename).read_text(encoding='utf-8'))
    return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == variable for t in n.targets))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suite', choices=['intent', 'validator', 'e2e', 'baseline'], required=True)
    p.add_argument('--resume', action='store_true')
    p.add_argument('--attention', choices=['sdpa', 'luminar_sdpa'])
    p.add_argument('--output')
    p.add_argument('--compact', action='store_true')
    p.add_argument('--max-tokens', type=int)
    args = p.parse_args()
    sources = {'intent': ('run_v8_step7_intent_regression.py', 'TEST_QUERIES'),
               'validator': ('run_v8_step6_final_eval.py', 'ADVERSARIAL_CASES'),
               'e2e': ('run_v8_step7_e2e_generation.py', 'TEST_SUITE'),
               'baseline': ('run_v8_step6_final_eval.py', 'BASELINE_QUERIES')}
    cases = dataset(*sources[args.suite])
    output = ROOT / (args.output or f'reports/rag_latency_{args.suite}_regression.json')
    rows = json.loads(output.read_text(encoding='utf-8')) if args.resume and output.exists() else []
    completed = {r['id'] for r in rows}
    session = requests.Session()

    def evaluate(operation, question, **kwargs):
        response = session.post('http://127.0.0.1:8005/__latency/evaluate', json={
            'operation': operation, 'question': question, 'attention': args.attention,
            'compact_prompt': True if args.compact else None, 'max_tokens': args.max_tokens,
            **kwargs}, timeout=600)
        response.raise_for_status()
        return response.json()

    for case in cases:
        if case['id'] in completed:
            continue
        started = time.perf_counter()
        if args.suite == 'intent':
            response = evaluate('intent', case['query'])
            actual = response['intent_data']
            row = {**case, 'actual': actual, 'correct': actual['intent'] == case['expected_intent'], 'profile': response.get('profile')}
            actor = str(actual.get('actor') or '').lower()
            expected = case['expected_actor']
            row['actor_match'] = (expected in actor or actor in expected) if actor and expected else actor == expected
            row['polarity_match'] = actual.get('polarity') == case['expected_polarity']
        elif args.suite == 'validator':
            items = [{'text': case['evidence']}]
            ff = run_fast_filter(case['question'], case['intent_data'], items)
            validation = None
            if ff['decision'] == 'NEEDS_LLM_VALIDATION':
                validation = evaluate('validate', case['question'], intent_data=case['intent_data'], evidence=items)
                supported = validation['verdict'] == 'SUPPORTED'
            else:
                supported = ff['decision'] == 'FAST_ACCEPT'
            row = {**case, 'fast_filter': ff, 'validation': validation,
                   'actual_supported': supported, 'correct': supported == case['expected_supported']}
        else:
            result = evaluate('ask', case['query'], work_id=case['work_id'])
            row = {**case, 'result': result}
            if args.suite == 'e2e':
                answer = result.get('answer', '').lower()
                verdict = result.get('verdict', 'NOT_SUPPORTED')
                unsupported = any(t in answer for t in ['does not support the premise', 'not establish', 'never', 'no evidence', 'false']) or verdict == 'NOT_SUPPORTED'
                if not case['is_premise_valid']:
                    classification = 'UNSUPPORTED' if unsupported or 'not' in answer else 'HALLUCINATED'
                elif verdict == 'NOT_SUPPORTED':
                    classification = 'UNSUPPORTED'
                else:
                    classification = 'CORRECT' if any(t.lower() in answer for t in case['ground_truth_fact'].split() if len(t) > 3) else 'PARTIALLY_CORRECT'
                row['actual_classification'] = classification
        row['latency_ms'] = (time.perf_counter() - started) * 1000
        row['measured_at_unix'] = time.time()
        row['configuration'] = {'attention_override': args.attention,
                                'compact_prompt_override': args.compact,
                                'max_tokens_override': args.max_tokens}
        rows.append(row)
        output.write_text(json.dumps(rows, indent=2), encoding='utf-8')
        print(args.suite, case['id'], row.get('correct', row.get('actual_classification', 'complete')), round(row['latency_ms']), flush=True)


if __name__ == '__main__':
    main()
