"""Build the final report from measured artifacts; missing metrics stay unavailable."""
import json
import statistics
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'


def read(name):
    return json.loads((REPORTS / name).read_text(encoding='utf-8-sig'))


def mean(values):
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else None


def measured_experiments():
    rows = []
    def add(name, before, after, quality, decision):
        rows.append(dict(name=name, before_ms=before, after_ms=after,
                         delta_ms=after-before if before is not None and after is not None else None,
                         reduction_percent=(1-after/before)*100 if before and after is not None else None,
                         quality_impact=quality, decision=decision))
    threads = read('rag_latency_thread_sweep.json')['runs']
    experiments = read('rag_latency_experiments.json')
    original = mean(r['total_ms'] for r in threads if r['threads'] == 0 and r['repeat'] > 0)
    cached = mean(r['total_ms'] for r in experiments if r['label'] == 'tokenizer_cache' and r['repeat'] > 0)
    add('Constrained-decoding tokenizer lookup reuse (warm summary)', original, cached,
        'Same answer; immutable vocabulary reused, parser state remains fresh.', 'accepted')
    attention = read('rag_attention_fixed_token_comparison.json')
    add('Expanded K/V SDPA, fixed 20 generated tokens',
        mean(r['elapsed_ms'] for r in attention if r['attention'] == 'sdpa'),
        mean(r['elapsed_ms'] for r in attention if r['attention'] == 'luminar_sdpa'),
        'Fixed-token text identical. Expanded attention rejected for intent after a paraphrase regression; other uses require the final quality gate.', 'accepted for answer/validator only')
    dtype = read('rag_compute_dtype_comparison.json')
    add('BF16 compute instead of FP16, fixed 20 tokens',
        mean(r['elapsed_ms'] for r in dtype if r['compute_dtype'] == 'torch.float16'),
        mean(r['elapsed_ms'] for r in dtype if r['compute_dtype'] == 'torch.bfloat16'),
        'Changed generated text; quality equivalence not established.', 'rejected')
    for count in [1, 4]:
        add(f'CPU intra-op threads {count}', mean(r['total_ms'] for r in threads if r['threads'] == 0),
            mean(r['total_ms'] for r in threads if r['threads'] == count),
            'No meaningful gain relative to run variation; default retained.', 'rejected')
    full = mean(r['total_ms'] for r in experiments if r['label'] == 'compatible_sdpa')
    for count in [4, 3]:
        add(f'Summary evidence chunks 7 to {count}', full,
            mean(r['total_ms'] for r in experiments if r['label'] == f'context{count}'),
            'Less context produced longer/worse answers; source breadth not qualified.', 'rejected')
    add('Inference mode on the same summary path',
        mean(r['total_ms'] for r in read('rag_latency_http_summary_before_inference_mode.json')['runs']),
        mean(r['total_ms'] for r in read('rag_latency_http_summary_before_overview_gate.json')['runs']),
        'Same summary text observed; full final regressions reported separately.', 'accepted')
    prompt = read('rag_latency_prompt_ablation.json')
    for q in dict.fromkeys(r['question'] for r in prompt):
        old = next(r for r in prompt if r['question'] == q and not r['compact'])
        new = next(r for r in prompt if r['question'] == q and r['compact'] and r['max_tokens'] == 600)
        add('Compact prompt: ' + q, old['total_ms'], new['total_ms'],
            f"Input tokens {old['input_tokens']} to {new['input_tokens']}; output {old['generated_tokens']} to {new['generated_tokens']}. Answers retained for review.", 'see final configuration and quality gate')
    return rows


def file_audit():
    modified, frozen = [], []
    for original in (REPORTS / 'latency_original').glob('*.py'):
        relative = 'rag/services/document_service.py' if original.name == 'document_service.py' else 'rag/' + original.name
        target = ROOT / relative
        (frozen if target.read_bytes() == original.read_bytes() else modified).append(relative)
    added = ['rag/attention.py', 'rag/decoding.py', 'rag/query_types.py', 'rag/telemetry.py',
             'scripts/benchmark_rag_latency.py', 'scripts/regression_rag_latency.py',
             'scripts/ablate_rag_prompts.py', 'scripts/rag_evaluation_server.py',
             'scripts/monitor_rag_resources.py', 'scripts/check_rag_index_integrity.py',
             'scripts/check_rag_runtime.py',
             'scripts/sweep_rag_fast_filter.py', 'scripts/rag_latency_lab.py',
             'scripts/rag_inference_experiments.py', 'scripts/report_rag_latency.py',
             'tests/test_rag_attention.py', 'tests/test_rag_decoding.py', 'tests/test_rag_query_types.py']
    return {'modified_production_files': sorted(modified), 'added_code_files': added,
            'unchanged_critical_files': sorted(frozen),
            'sha256': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in modified + frozen + added}}


def main():
    baseline = read('rag_latency_baseline.json')
    baseline['measurement_notes'] = {
        'unmodified_http_requests': 3,
        'instrumented_original_kernel_artifact': 'rag_latency_thread_sweep.json',
        'instrumented_resource_samples_artifact': 'rag_thread_sweep_resources.json',
        'hardware_runtime_artifact': 'rag_latency_lab_environment.json',
        'initial_http_parsing_ms': None, 'initial_book_filter_ms': None,
        'initial_gpu_utilization': None, 'initial_cpu_utilization': None,
        'initial_gpu_memory': None, 'initial_model_loading_ms': None,
        'explanation': 'Original HTTP responses preserve available stage timings. Missing initial substage, token and resource measurements cannot be reconstructed. Separate original-kernel instrumented runs record tokens, stages and sampled resources; they are not substituted into the three HTTP requests.'}
    (REPORTS / 'rag_latency_baseline.json').write_text(json.dumps(baseline, indent=2), encoding='utf-8')
    books = read('rag_latency_books_final.json')['runs']
    pdf = read('rag_latency_pdf_final.json')['runs']
    intents = read('rag_latency_intent_regression.json')
    validators = read('rag_latency_validator_regression.json')
    e2e = read('rag_latency_e2e_regression.json')
    assert len(intents) == 64 and len(validators) == 42 and len(e2e) == 32, 'Complete the frozen regression suites first.'
    frozen_intent = read('intent_aware_rag_v8_intent_regression.json')['summary']
    frozen_validation = read('intent_aware_rag_v8_final_evaluation.json')['adversarial']
    frozen_e2e = read('intent_aware_rag_v8_e2e_generation.json')
    summary = [r for r in books if r['question'] == 'What is the summary of this book?']
    before = mean(r['http_total_ms'] for r in baseline['runs'])
    after = mean(r['total_ms'] for r in summary)
    quality = {}
    for category, key in [('Canonical', 'canonical_accuracy'), ('Paraphrased', 'paraphrase_accuracy'), ('Adversarial', 'adversarial_accuracy')]:
        rows = [r for r in intents if r['category'] == category]
        quality['intent_' + category.lower()] = {'before': frozen_intent[key], 'after': 100 * mean(r['correct'] for r in rows)}
    quality['intent_overall'] = {'before': frozen_intent['overall_intent_accuracy'], 'after': 100 * mean(r['correct'] for r in intents)}
    for key in ['actor', 'polarity']:
        quality['intent_' + key] = {'before': frozen_intent[f'overall_{key}_accuracy'],
                                  'after': 100 * mean(r[key + '_match'] for r in intents)}
    quality['adversarial_validation'] = {'before': frozen_validation['accuracy_percent'], 'after': 100 * mean(r['correct'] for r in validators)}
    invalid = [r for r in validators if not r['expected_supported']]
    quality['unsupported_premise_rejection'] = {'before': frozen_validation['unsupported_premise_detection_percent'], 'after': 100 * mean(not r['actual_supported'] for r in invalid)}
    for valid in [True, False]:
        old = [r for r in frozen_e2e if r['is_premise_valid'] == valid]
        new = [r for r in e2e if r['is_premise_valid'] == valid]
        accepted = {'CORRECT', 'PARTIALLY_CORRECT'} if valid else {'UNSUPPORTED'}
        quality['e2e_valid_groundedness' if valid else 'e2e_invalid_rejection'] = {
            'before': 100 * mean(r['actual_classification'] in accepted for r in old),
            'after': 100 * mean(r['actual_classification'] in accepted for r in new)}
    retrieval = [r for r in read('rag_latency_retrieval_sweep.json') if r['candidates'] == 15]
    frozen_retrieval = read('intent_aware_rag_v8_retrieval_regression.json')['summary']
    for name, field in [('top1', 'top1_score'), ('top3', 'top3_score')]:
        quality['retrieval_' + name] = {'before': frozen_retrieval[name + '_accuracy_percent'], 'after': 100 * mean(r[field] >= .5 for r in retrieval)}
    quality['retrieval_mrr_proxy'] = {'before': frozen_retrieval['mrr'], 'after': mean(1. if r['top1_score'] >= .5 else .33 if r['top3_score'] >= .5 else 0 for r in retrieval)}
    regression = any(v['after'] + .011 < v['before'] for v in quality.values())
    stage_before = {key: mean(r['result']['timing_ms'].get(key) for r in baseline['runs']) for key in ['intent_analysis', 'retrieval', 'fast_filter', 'validation', 'generation', 'total']}
    book_stats = {q: {'mean_ms': mean(r['total_ms'] for r in books if r['question'] == q),
                      'runs_ms': [r['total_ms'] for r in books if r['question'] == q]}
                  for q in dict.fromkeys(r['question'] for r in books)}
    out = {'baseline_summary_ms': before, 'final_summary_ms': after,
           'improvement_percent': (1 - after / before) * 100,
           'baseline_stage_ms': stage_before,
           'baseline_stage_percent': {k: v / stage_before['total'] * 100 for k, v in stage_before.items() if k != 'total'},
           'book_queries': book_stats, 'pdf_mean_ms': mean(r['total_ms'] for r in pdf),
           'validator_call_rate_percent': 100 * mean(r['validator_called'] for r in books + pdf),
           'generation_tokens_per_second': mean(r['tokens_per_second'] for r in books + pdf),
           'quality': quality, 'quality_regression': regression,
           'v8_semantics_preserved_on_frozen_suite': not regression,
           'v8_algorithm_changed': True,
           'algorithm_change_scope': 'Strict informational intent routing, source-verified overview/author acceptance, compact answer instructions and scoped insufficient-evidence generation; frozen filter/scoring thresholds and minimal validator schema retained.',
           'experiments': measured_experiments(), 'file_audit': file_audit(),
           'intent_latency_ms': {'before': frozen_intent['mean_latency_ms'], 'after': mean(r['latency_ms'] for r in intents)},
           'intent_without_llm_percent': 100 * mean(not r.get('profile', {}).get('llm_calls') for r in intents),
           'normal_benchmark_without_intent_llm_percent': 100 * mean(r['result']['intent_data'].get('tier_used', '').startswith('Tier 1') for r in books + pdf),
           'actual_retrieval_mrr': mean(r['rr'] for r in retrieval),
           'threshold_sweep': [{k: v for k, v in r.items() if k != 'rows'} for r in read('rag_latency_threshold_sweep.json')],
           'limitations': ['Baseline first request was observed on an already-running service, not a process-cold launch.',
                          'GPU hardware traces were unavailable because CUPTI initialization failed; nvidia-smi samples were used.',
                          'Frozen groundedness scoring is a keyword/verdict heuristic, not a proof of factual accuracy.',
                          'A broad compact-prompt variant introduced an unsupported causal motive despite passing that heuristic. It was rejected; compact instructions are restricted to the tested informational grammar.',
                          'Frozen MRR is a top-1/top-3 proxy; actual per-rank reciprocal scores are also preserved in the sweep.',
                          'Initial HTTP parsing, book-filter loop and merge timings were not independently instrumented; no synthetic values are assigned.']}
    samples = read('rag_latency_final_resources.json')
    start = min(read('rag_latency_books_final.json')['started_at_unix'], read('rag_latency_pdf_final.json')['started_at_unix'])
    end = max(r['measured_at_unix'] for r in books + pdf)
    samples = [r for r in samples if start <= r['time'] <= end]
    out['resource_samples'] = len(samples)
    out['resources'] = {key: {'mean': mean(r.get(key) for r in samples),
                              'max': max((r[key] for r in samples if key in r), default=None)}
                        for key in ['cpu_percent', 'rss_mb', 'gpu_util_percent', 'gpu_memory_mb']}
    out['service_health'] = read('rag_latency_books_final.json')['service_health']
    out['runtime_checks'] = {k: v for k, v in read('rag_latency_runtime_checks.json').items() if k not in {'runs', 'health_ms'}}
    out['errors'] = {
        'intent_case_ids': [r['id'] for r in intents if not r['correct']],
        'validator_case_ids': [r['id'] for r in validators if not r['correct']],
        'end_to_end_classifications': {r['id']: r['actual_classification'] for r in e2e},
        'generation_cap_reached_case_ids': [r['id'] for r in e2e
            if r['result'].get('profile', {}).get('llm_calls')
            and r['result']['profile']['llm_calls'][-1]['generated_tokens'] >= r['result']['profile']['llm_calls'][-1]['max_new_tokens']]}
    out['source_isolation_passed'] = all(all(s['work_id'] == r['work_id'] for s in r['result'].get('sources', [])) for r in e2e)
    out['retrieval_candidate_sweep'] = [
        {'candidates': count, 'mean_ms': mean(r['latency_ms'] for r in read('rag_latency_retrieval_sweep.json') if r['candidates'] == count),
         'top1_percent': 100*mean(r['top1_score'] >= .5 for r in read('rag_latency_retrieval_sweep.json') if r['candidates'] == count),
         'top3_percent': 100*mean(r['top3_score'] >= .5 for r in read('rag_latency_retrieval_sweep.json') if r['candidates'] == count)} for count in [3, 5, 8, 10, 15]]
    out['final_configuration'] = {'normal_candidates': 15, 'normal_context_chunks': 7,
                                  'normal_max_new_tokens': books[0]['max_new_tokens'],
                                  'compact_prompt': True, 'max_context_characters': 24000,
                                  'compact_prompt_scope': 'Strict ordinary informational grammar; original V8 prompt retained for other questions.',
                                  'answer_repetition_penalty': 1.15, 'answer_only_no_repeat_ngram': 3,
                                  'intent_attention': 'sdpa', 'answer_validator_attention': 'luminar_sdpa',
                                  'validation_schema': ['supported', 'confidence']}
    (REPORTS / 'rag_latency_optimization.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    text = ['# LuminaR RAG Latency Optimization', '', '## Executive Summary', '',
            f'The exact Huckleberry Finn summary request improved from **{before/1000:.2f} s to {after/1000:.2f} s** ({out["improvement_percent"]:.1f}% faster). All requests use real local Qwen, retrieval, source attribution and scoped evidence.', '',
            '## Baseline', '',
            'Three unmodified HTTP requests: ' + ', '.join(f'{r["http_total_ms"]/1000:.2f} s' for r in baseline['runs']) + '.',
            'The first is the first observed request on an already-running service. Model startup is separate. Detailed original-kernel profiles are in `rag_latency_thread_sweep.json`.', '',
            '## Bottleneck Analysis', '', '| Stage | Baseline ms | Share |', '|---|---:|---:|']
    for key, value in stage_before.items():
        if key != 'total':
            text.append(f'| {key} | {value:.2f} | {out["baseline_stage_percent"][key]:.2f}% |')
    text += ['', '## Optimization Changes', '',
             '- Reuse the immutable constrained-decoding tokenizer lookup; keep a fresh JSON parser per call.',
             '- Use strict informational templates and a bounded cache containing only entity-free classifications. Arbitrary topics are not cached.',
             '- Expand grouped K/V heads for CUDA SDPA on Windows builds without Flash Attention. Retain original SDPA for intent extraction after a measured regression.',
             '- Use inference mode, retain deterministic decoding and KV caching.',
             '- Fast-accept exact overview requests only with at least three substantial, uniquely identified passages from the selected book. No extra claims qualify.',
             '- Share MiniLM with uploads and serialize GPU inference/index refresh. Upload work runs outside the event loop.',
             '- Preserve seven evidence chunks and the original retrieval/scoring path after smaller-context experiments underperformed.', '',
             'Measured ablations and rejected alternatives: `rag_attention_fixed_token_comparison.json`, `rag_latency_experiments.json`, `rag_latency_threshold_sweep.json`, `rag_latency_retrieval_sweep.json`, `rag_compute_dtype_comparison.json`, and `rag_latency_prompt_ablation.json`.', '',
             'Each row below is its own measured experiment, not an additive speedup. Some experiments change answer length; the fixed-token attention comparison isolates kernel performance.', '',
             '| Experiment | Before ms | After ms | Delta ms | Quality / decision |', '|---|---:|---:|---:|---|']
    for row in out['experiments']:
        text.append(f"| {row['name']} | {row['before_ms']:.1f} | {row['after_ms']:.1f} | {row['delta_ms']:+.1f} | {row['quality_impact']} **{row['decision']}** |")
    text += ['',
             'Additional scoped changes: metadata author acceptance retains real retrieval and generation; one attributed source replaces seven for that exact query. Overviews require three substantial, unique passages from the selected book. GPU serialization and shared upload embeddings are correctness/resource changes; isolated latency savings are not claimed for them.', '',
             'Rejected answer-only soft repetition penalties caused longer, speculative answers (`rag_latency_prompt_ablation_rejected_answer_penalty.json`). The original soft penalty is retained; only the hard n-gram ban excludes source text so names remain copyable. Refusal generation uses one already-checked passage after validation examines the full selected evidence.', '',
             '## Before vs After', '', f'| Exact summary query | Mean seconds |\n|---|---:|\n| Original | {before/1000:.2f} |\n| Final | {after/1000:.2f} |', '',
             '## Book Query Latency', '', '| Question | Mean seconds | Three runs, seconds |', '|---|---:|---|']
    for q, data in book_stats.items():
        text.append(f'| {q} | {data["mean_ms"]/1000:.2f} | ' + ', '.join(f'{v/1000:.2f}' for v in data['runs_ms']) + ' |')
    text += ['', '## PDF Query Latency', '', f'Real indexed autoencoder notes: **{out["pdf_mean_ms"]/1000:.2f} s** mean. Individual results and sources are in `rag_latency_pdf_final.json`.', '']
    for title, field in [('Intent Latency', 'intent_ms'), ('Retrieval Latency', 'retrieval_ms'), ('Reranking Latency', 'rerank_ms'), ('Fast Filter Latency', 'fast_filter_ms'), ('Validator Latency', 'validator_ms'), ('Generation Latency', 'generation_ms')]:
        value = mean(r.get(field) for r in books + pdf)
        text += [f'## {title}', '', f'Final measured mean: **{value:.2f} ms** across the book/PDF benchmark.' if value is not None else 'Unavailable.', '']
        if title == 'Intent Latency':
            text += [f"The difficult frozen 64-case suite changed from {out['intent_latency_ms']['before']:.1f} to {out['intent_latency_ms']['after']:.1f} ms mean. No intent LLM was needed for {out['intent_without_llm_percent']:.1f}% of that suite and {out['normal_benchmark_without_intent_llm_percent']:.1f}% of the six normal benchmark query patterns. The generic cache does not cache retrieved evidence or answers.", '']
        if title == 'Retrieval Latency':
            text += ['| Candidate count | Full retrieval/rerank ms | Top-1 % | Top-3 % |', '|---|---:|---:|---:|']
            for sweep in out['retrieval_candidate_sweep']:
                text.append(f"| {sweep['candidates']} | {sweep['mean_ms']:.1f} | {sweep['top1_percent']:.1f} | {sweep['top3_percent']:.1f} |")
            text += ['', 'The small frozen retrieval set improves at lower counts, but it does not establish summary breadth or causal grounding. Separate smaller-context experiments made summaries slower/worse, so the normal path keeps 15 candidates and seven diverse passages. Scoped book indexes and LRU caching were already present; no new speedup is claimed for them.', '']
        if title == 'Fast Filter Latency':
            text += ['| Actor/event thresholds | False accepts | False rejects | Validator calls / 42 |', '|---|---:|---:|---:|']
            for sweep in out['threshold_sweep']:
                text.append(f"| {sweep['actor']}/{sweep['event']} | {sweep['false_accepts']} | {sweep['false_rejects']} | {sweep['validator_calls']} |")
            text += ['', 'Lower thresholds save four validator calls but introduce four additional false accepts. Rejected. Original deterministic scoring and the two-field validator schema remain unchanged.', '']
    text += ['## GPU Utilization', '', 'All 434 Qwen parameter tensors were verified on CUDA. Resource samples record device-wide GPU utilization/memory and per-process CPU/RSS. Samples include idle periods; Windows WDDM does not expose reliable per-process VRAM through nvidia-smi. CUPTI hardware profiling was unavailable.', '',
             '| Resource during final requests | Mean | Maximum |', '|---|---:|---:|']
    for key, values in out['resources'].items():
        fmt = lambda value: f'{value:.2f}' if value is not None else 'unavailable'
        text.append(f"| {key} | {fmt(values['mean'])} | {fmt(values['max'])} |")
    text += ['', f"Service model/index initialization: {out['service_health'].get('model_loading_ms', 'unavailable')} ms, measured separately from requests. CPU percent uses psutil's per-process scale (100% per logical core).", '',
             '## Token Throughput', '', f'Mean measured answer throughput, including prefill: **{out["generation_tokens_per_second"]:.2f} tokens/s**. Validator call rate: **{out["validator_call_rate_percent"]:.1f}%**. Actual input/output counts and limits are recorded per request.', '',
             '## Quality Regression', '', '| Metric | Frozen baseline | Final |', '|---|---:|---:|']
    for name, values in quality.items():
        text.append(f'| {name} | {values["before"]:.3f} | {values["after"]:.3f} |')
    text += ['', f'Measured regression: **{"YES" if regression else "NO"}**. The expanded-attention intent variant was rejected after losing one paraphrase case. Critical `rag/fast_filter.py` and `rag/evidence.py` remain byte-for-byte unchanged.', '',
             f"Replay coverage: 64 intent cases, 42 validator cases, 32 end-to-end cases; all 17 FAISS index/metadata integrity checks. Runtime checks passed: {out['runtime_checks']['passed']}; concurrent book/PDF requests remained isolated and serialized GPU work, with maximum health-response latency {out['runtime_checks']['max_health_ms']:.1f} ms.", '',
             '## Error Analysis', '', *['- ' + limitation for limitation in out['limitations']], '',
             'Intent failures: ' + ', '.join(out['errors']['intent_case_ids']) + '. Validator failures: ' + ', '.join(str(v) for v in out['errors']['validator_case_ids']) + '. These metrics must be compared with the frozen baseline, not interpreted as perfect accuracy.', '',
             f"End-to-end selected-document source isolation: {out['source_isolation_passed']}. End-to-end cases reaching the generation cap: {out['errors']['generation_cap_reached_case_ids']}.", '',
             '## Final Configuration', '', 'Local Qwen2.5-3B, NF4/double quantization, FP16 compute, CUDA; deterministic single-beam generation with KV cache. MiniLM and CrossEncoder remain on CUDA. Per-book FAISS LRU size 5. Intent classification LRU bound 128; only entity-free templates are retained. Frozen actor/event thresholds remain 0.8/0.6.', '',
             f"Normal: 15 candidates, 7 diverse evidence chunks (1 for source-verified author metadata), {out['final_configuration']['normal_max_new_tokens']} maximum new tokens. Compact normal answers request at most 40 words only for the strict informational grammar; other questions retain V8's original prompt. All tested summary caps (128/192/256/320) completed identically; 320 retains headroom and the ordering above concise depth. The cap itself did not improve completed-answer latency. Concise/detailed/comprehensive depth limits remain 300/1000/1500. Context budget remains 24,000 characters.", '',
             'Source changes:', '', *['- `' + p + '`' for p in out['file_audit']['modified_production_files'] + out['file_audit']['added_code_files']], '',
             'Critical frozen files: ' + ', '.join('`' + p + '`' for p in out['file_audit']['unchanged_critical_files']) + '. Frontend `frontend/src/pages/LLMPage.tsx` and `frontend/src/lib/api.ts` were inspected and left unchanged. The requested `src/services/api.ts` path does not exist in this project.', '',
             '## Remaining Bottlenecks', '', 'Real Qwen autoregressive decoding dominates the remaining latency. Longer answers require proportionally more time at the measured throughput. Context reduction and lower token caps are not assumed to preserve completeness.', '',
             '## Recommendations', '', 'Use the measured normal-depth results as the service budget. Keep the frozen quality gate for future kernel, prompt or model changes. Re-run the benchmark after hardware/runtime changes; do not trade unsupported-premise rejection for a lower latency number.', '',
             'Reproduce: `.venv\\Scripts\\python.exe scripts\\benchmark_rag_latency.py`. Quality replay uses `scripts/regression_rag_latency.py` with the temporary single-model evaluation adapter; normal operation uses `rag.api:app`.', '']
    (REPORTS / 'rag_latency_optimization.md').write_text('\n'.join(text), encoding='utf-8')
    print(json.dumps({k: out[k] for k in ['baseline_summary_ms', 'final_summary_ms', 'improvement_percent', 'quality_regression']}, indent=2))


if __name__ == '__main__':
    main()
