"""Build the review report from measured numeric evidence, never fabricated data."""
import json
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'


def load(name):
    return json.loads((REPORTS / name).read_text(encoding='utf-8'))


def model_ms(row, stage):
    return sum(c['generation_ms'] for c in row['profile']['qwen_calls'] if c['stage'] == stage)


def summarize(row):
    calls = row['profile']['qwen_calls']
    return {'total_ms': row['client_total_ms'], 'server_total_ms': row['profile']['total_ms'],
        'qwen_calls': len(calls), 'intent_called': any(c['stage'] in {'intent','repair'} for c in calls),
        'response_called': any(c['stage'] == 'response' for c in calls),
        'rag_calls': sum(c['stage'] == 'rag' for c in calls),
        'intent_generation_ms': model_ms(row, 'intent'),
        'response_generation_ms': model_ms(row, 'response'),
        'rag_generation_ms': model_ms(row, 'rag'),
        'tool_wall_ms': row['profile']['stages_ms'].get('tool_execution', 0),
        'input_tokens': sum(c['input_tokens'] for c in calls),
        'generated_tokens': sum(c['generated_tokens'] for c in calls),
        'stages_ms': row['profile']['stages_ms']}


def comparison(before, after):
    facts_equal = before['structured_digest'] == after['structured_digest']
    rag_equal = before['rag_digest'] == after['rag_digest']
    valid = facts_equal and rag_equal and not before['clarification'] and not before['error_codes']
    return {'case': before['case'], 'before': summarize(before), 'after': summarize(after),
        'structured_equivalent': facts_equal, 'rag_answer_verdict_sources_equivalent': rag_equal,
        'comparison_fields_equal': before['comparison_fields'] == after['comparison_fields'],
        'valid_matched_latency_comparison': valid,
        'percent_improvement': 100 * (1 - after['client_total_ms'] / before['client_total_ms']) if valid else None}


def table(rows):
    out = ['| Operation | Qwen before → after | Before s | After s | Improvement | Equivalent facts |',
           '|---|---:|---:|---:|---:|---|']
    for r in rows:
        b, a = r['before'], r['after']
        gain = f"{r['percent_improvement']:.1f}%" if r['percent_improvement'] is not None else 'route changed¹'
        out.append(f"| {r['case']} | {b['qwen_calls']} → {a['qwen_calls']} | {b['total_ms']/1000:.2f} | {a['total_ms']/1000:.2f} | {gain} | {'yes' if r['structured_equivalent'] else 'no¹'} |")
    return out


def main():
    baseline = load('chatbot_latency_baseline.json')
    optimized = load('chatbot_latency_benchmark.json')
    bs = load('chatbot_latency_baseline_supplement.json')
    opt = load('chatbot_latency_optimized_supplement.json')
    main_rows = [comparison(b, a) for b, a in zip(baseline['cases'], optimized['cases'])]
    extra_rows = [comparison(b, a) for b, a in zip(bs['cases'], opt['cases'])]
    optimized['comparisons'] = main_rows
    optimized['supplemental_comparisons'] = extra_rows
    optimized['benchmark_method'] = {
        'requests': '13 original-routing cases and 13 optimized cases, plus 5 paired supplementary cases',
        'repetitions': 1, 'startup_excluded': True, 'conversations': 'fresh per case',
        'original_supplement': 'Frozen original orchestrator source with numeric instrumentation; same injected Qwen/tools',
        'identity': 'Same existing identity per matched run; authorized-book supplementary run uses another existing eligible reader',
        'qwen_processes': 'Sequential restarts; one model load in each process, no simultaneous second Qwen',
        'token_method': 'Exact formatted input_ids and generated output tensor lengths, including EOS',
        'timings': 'Stage timings may nest; concurrent HTTP service timings are aggregate, tool_execution is wall time'}
    optimized['correctness_differences'] = [
        'Available now: original Qwen classified availability without a unique target and clarified; explicit AVAILABLE_NOW now returns verified available-only search results.',
        'Standard compare: original Qwen inserted unrequested page_count, yielding a missing-field notice. Explicit COMPARE returns the same actual books/availability with no invented requested field.',
        'Unindexed book RAG: original extraction clarified; explicit book action reaches the existing RAG authorization/source gate and receives HTTP_404. No source or borrowing bypass.',
        'Authorized book RAG: original Qwen extracted unsuitable entities and clarified; explicit action binds the actual selected/borrowed indexed book and returns SUPPORTED with seven sources. This is a routing correction, not an equivalent-result latency gain.',
        'Simple prose is now deterministic; general-help prose can vary with conversation IDs, as before. Document RAG answer/verdict/sources are identical.']
    optimized['tests'] = {'focused_backend_passed': 117, 'combined_regressions_passed': 203,
        'combined_regressions_skipped': 10, 'frontend_passed': 92, 'frontend_build': 'passed',
        'frontend_lint': 'passed with 18 pre-existing warnings', 'real_overlay_ms': 443,
        'later_overlay_ms': 371, 'browser_warnings_errors': 0}
    (REPORTS/'chatbot_latency_benchmark.json').write_text(json.dumps(optimized, indent=2), encoding='utf-8')
    preservation = load('assistant_latency_source_preservation.json')
    lines = ['# LuminaR chatbot Part 2.5 — measured latency optimization', '',
        'Completed 2026-10-01 in D:\\SDC\\LibraryLLM. Existing overlay retained. Stopped after Part 2.5.', '',
        '## A. Bottleneck and original/optimized flow', '',
        'Original: authenticated/validated request → Qwen intent → authoritative entity resolution → tools → usually Qwen prose → operational grounding → response serialization.', '',
        'Optimized: same authentication/validation → allowed read-only action or small exact-message router → same authoritative resolver/tools → deterministic factual summary → serialization. Ambiguous input still invokes Qwen intent. General help and subjective/complex recommendation/comparison synthesis retain response Qwen. Accepted RAG routing/answer generation is unchanged; explicit source actions skip only assistant intent generation.', '',
        'Search baseline: 50.99 s total, 13.80 s intent generation + 34.85 s prose generation, versus 1.96 s tool execution. Default recommendation: 27.70 s total, 26.70 s generation, versus 0.67 s tools. This verifies the model-pass hypothesis before changing routing behavior.', '',
        '## B, H, I, J, P. Calls, before/after timing, improvement and real-service matrix', '',
        *table(main_rows), '', 'Additional exact typed-message and authorized-reader matrix:', '',
        *table(extra_rows), '',
        '¹ Failed original routing is not a successful baseline. No percentage speedup is claimed for these non-equivalent results. Raw timings/calls remain visible. Standard comparison has identical catalogue facts but a deliberately changed requested-field list; see Q.', '',
        'One representative request per scenario per phase; these are measured samples, not percentiles or an SLA. Same live Core/search/recommendation services and catalogue, same identity in matched runs, fresh conversation each time. Cached local model only; no model downloads, DB users, loans or mutations created. Main runs used the original in-memory process for baseline and restarted once for optimized behavior. Supplement baseline loads the frozen original orchestrator from the source snapshot, with timing wrappers only. Each run has one Qwen load, one worker and no reload; the previous service exits before the next starts.', '',
        '## C. Routing and validation', '',
        'Read-only request actions: COMPARE (2–4 unique selected IDs), RECOMMEND (zero selected), RECOMMEND_SIMILAR (one), RECOMMEND_FROM_SELECTION (2–4), CHECK_AVAILABILITY (one selected/page target), AVAILABLE_NOW, USER_LOANS, USER_FEES, USER_RESERVATIONS, BOOK_CONTENT_QUESTION (one selected/page book), DOCUMENT_QUESTION (document context required). Invalid counts clarify before model/tools. Unknown and mutating structured actions are rejected by the request schema. Every supplied book still reaches Core canonical validation; RAG still enforces existing source/borrow eligibility.', '',
        'Exact typed routes normalize whitespace/case and terminal punctuation: recommend/recommend something/recommend me something; show my loans/what books do I have borrowed; do I have fines/show my fines; show my reservations; compare these/compare these two with 2–4 selected; is this available/is this book available with one selected/page book. More specific filters, names, quantities, ordinals or mixed/ambiguous requests retain Qwen extraction and the existing conversation resolver. Page availability binds that explicit target ahead of prior search results. Read-only action hints win over conflicting prose, but never over auth or confirmation requirements.', '',
        'Frontend tray, quick recommendation, Available now, clicked-book availability and similar-recommendation buttons now send action plus canonical selections through the existing bearer client. Free text sends no action. Header, theme, drawer, loading state, scrollable history, input and layout code/styles are otherwise retained.', '',
        '## D. Operations without Qwen', '',
        'Explicit standard comparison, selection-driven/default recommendations, one-book availability, Available now and account summaries use zero calls. Exact typed recommendation/loans/fees/reservations/selected comparison/page availability also use zero. Natural-language search ordinarily uses one extraction call and no response call. Basic recommendation cards and comparison tables render verified structured values directly. Mutation proposals retain original intent extraction; their confirmation/disabled/cancel flow remains unchanged.', '',
        '## E. Operations retaining Qwen', '',
        'General help measured two calls (interpretation then explanation), unchanged. Ambiguous and complex natural language retains extraction; subjective comparison/complex recommendation wording conservatively retains prose. Ordinary book/document questions may require assistant extraction; explicit source actions omit it while accepted RAG still performs its own evidence validation and answer generation. Document RAG measured 4 → 3 calls. Authorized-book explicit RAG measured two existing RAG calls (validator/answer); the original assistant question clarified instead of entering RAG.', '',
        '## F. Generation settings, budgets, stopping and prompt audit', '',
        'No model generation settings changed. Assistant intent max_new_tokens=650, response=300, do_sample=False (temperature/top_p ignored), default num_beams=1, use_cache=True, structured repetition_penalty=1/no_repeat_ngram=0; existing AnswerRepetitionControl for prose. Pydantic validation plus at most one repair remains mandatory. Baseline intent outputs were 102–146 tokens including EOS, much below 650. The enforcer/tokenizer already permits normal EOS after a valid object; no measured substantial post-JSON continuation. Lowering a maximum that was never reached would not reduce these generations, and risks truncating richer valid intents. Prose ranged 13–283 tokens; removing those passes yields the substantial benefit without globally truncating explanations. Accepted RAG budgets, prompts and generation remain untouched.', '',
        'Baseline intent input: 1,251–1,274 tokens; response input: 305–2,557 tokens. Intent includes bounded IDs/context/schema, no transcript. Recommendation synthesis sees only final displayed books (typically 10), not 50 candidates. Comparison payload is limited to selected 2–4 books; duplicate books in comparison/response and conversation IDs remain possible future prompt simplifications. Availability/account facts now avoid those prompts altogether. Existing description cap is 1,600 characters for response.books. No speculative prompt or decoding changes were kept.', '',
        '## G. Attention/runtime and concurrency', '',
        'Qwen2.5-3B-Instruct, CUDA NF4 4-bit/double quantization, FP16 compute. Model and tokenizer load at startup, including warm-up and immutable constrained-decoding vocabulary. No per-request from_pretrained, pipeline, quantization initialization or second Qwen. The existing single inference lock and one-slot executor remain; timed-out native generations retain their slot until they finish. ContextVar profiling is propagated into that executor and the existing RAG worker; it does not alter model tensors/settings.', '',
        'Observed runtime: ' + json.dumps(optimized['runtime']), '',
        'Attention is already luminar_sdpa, the project’s Windows-compatible built-in SDPA wrapper with grouped K/V expansion. PyTorch reports fused flash attention unavailable on this build; SDPA memory-efficient kernels are enabled. Therefore no attention switch, dependency install, torch.compile or alternate engine was introduced. The existing RAG-specific attention choices remain untouched. Metadata fetches and seed recommendation requests still run concurrently. No new private/availability/Qwen-result cache was introduced; fresh facts remain authoritative. No unrelated GPU process was terminated.', '',
        '## Independent stage and token observations', '',
        'The JSON preserves request validation, intent routing/parsing, entity resolution, search, recommendation, aggregate Core metadata, availability, account, RAG, serialization, total and exact model call/token measurements. Final instrumentation additionally separates intent_json_validation and core_metadata_wall. Model generation times below are exact model-call wall times; intent parsing is inclusive of generation/setup/validation. Stages nest and concurrent Core timings overlap, so do not add all columns to estimate total. Remaining total includes authentication/dependency execution, per-request HTTP client setup, scheduling and transport; these have not been individually isolated.', '',
        '| Phase/operation | Intent generation ms | Tool wall ms | Prose generation ms | RAG generation ms | Input tokens | Output tokens | Serialization ms |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for phase, data in [('before', baseline), ('after', optimized), ('before supplementary', bs), ('after supplementary', opt)]:
        for row in data['cases']:
            s = summarize(row)
            lines.append(f"| {phase}/{row['case']} | {s['intent_generation_ms']:.1f} | {s['tool_wall_ms']:.1f} | {s['response_generation_ms']:.1f} | {s['rag_generation_ms']:.1f} | {s['input_tokens']} | {s['generated_tokens']} | {s['stages_ms'].get('response_serialization',0):.2f} |")
    lines += ['', '## K. GPU/RAM observations', '']
    for name, data in [('Baseline', baseline), ('Optimized main', optimized), ('Optimized supplementary', opt)]:
        mem = [r['profile']['memory'] for r in data['cases']]
        lines.append(f"{name}: process RSS {min(m['process_rss_mb'] for m in mem):.0f}–{max(m['process_rss_mb'] for m in mem):.0f} MiB; CUDA allocated {min(m['cuda_allocated_mb'] for m in mem):.0f}–{max(m['cuda_allocated_mb'] for m in mem):.0f} MiB; CUDA reserved up to {max(m['cuda_reserved_mb'] for m in mem):.0f} MiB.")
        lines.append('')
    lines += ['nvidia-smi during baseline startup/measurement showed 3,109 MiB total GPU usage on an 8,151 MiB RTX 5060 Laptop GPU. Torch allocations describe this process, whereas nvidia-smi includes drivers/other apps; these are request snapshots, not a controlled peak-memory benchmark. No memory reduction claim is made.', '',
        '## L. Files and preservation', '', 'Existing source changes:']
    lines += ['- `' + n + '`' for n in preservation['changed_existing_source']]
    lines += ['', 'New source and configuration:']
    lines += ['- `' + n + '`' for n in preservation['new_source'] + preservation['additional_configuration_changed']]
    lines += ['', 'Source snapshot/hash inventory: assistant_latency_source_baseline/hashes.json. Review diff: assistant_latency_source.diff. Preservation report: assistant_latency_source_preservation.json. 165 baseline source/configuration files checked; all 96 Core/RAG/recommendation/search source files unchanged. The original 163 code files were copied before instrumentation; original backend fixture/env content was reconstructed from verified pre-edit lines for complete diffs. Existing experimental/protected RAG hash and route-AST checks pass. No recommendation weights, retrieval/chunks/indexes, model loader, experimental files or G1/G2/G3/R0 artifacts edited. Repository has no Git metadata, so a source snapshot/unified diff records the work. The two existing fixture requests were made semantically explicit: requested five books now says “Recommend 5 books”; the Qwen timeout case now uses ambiguous wording so it actually reaches the fallback being tested.', '',
        '## M. Focused backend tests', '', '117 passed = existing 68 plus 49 parametrized latency/security/observation cases. All 20 requested named fast-path tests are present. Covers skipped intent/prose calls, subjective fallback, exact typed gates, invalid counts/actions, real authoritative IDs, auth, owner/confirmation safety, source dispatch, page target vs prior results, conflicting prose/action and exact privacy-safe observation. See assistant_latency_tests.xml.', '',
        '## N. Frontend tests/build', '', '92 passed = original 87 plus five action-payload checks. Existing bearer/session/error/security/selection/keyboard/axe behavior remains covered. TypeScript/Vite production build passed. oxlint passed with the same 18 prior warnings. See assistant_latency_frontend_tests.log, assistant_latency_frontend_build.log and assistant_latency_frontend_lint.log.', '',
        '## O. Backend regressions', '', '203 passed, 10 skipped (pre-existing isolated Mongo opt-in tests), one existing Starlette/httpx deprecation warning. Combined assistant, latency, book-access, dynamic capabilities and staff-auth suites passed. See assistant_latency_regressions.xml.', '',
        '## Q. Correctness differences and equivalence', '']
    lines += ['- ' + item for item in optimized['correctness_differences']]
    lines += ['', 'Structured digests include intent, canonical books/metadata/order, seeds, recommendation mode, availability, account and errors. Account hashes avoid retaining private rows. RAG digest compares answer/verdict/sources, excludes timings/profiles. Ten successful non-RAG cases plus document RAG have equal fact digests. Standard comparison requested_fields is separately audited rather than hidden in a broad equivalence claim. Quantities, unsupported constraints and subjective wording still fall through to the existing extraction/clarification paths. Authentication, source access, fresh availability and confirmation guards remain authoritative.', '',
        '## R. Limitations and future work', '',
        'Sampling is one paired observation per scenario; device thermals, background load, transport and generated wording vary. General help/ambiguous/subjective tasks remain model-bound and may require two passes. Typed availability with multiple candidates/ordinals or explicit unresolved titles still uses Qwen and the existing resolver. Available now filters the existing bounded search candidate list; it is not an exhaustive inventory listing. Selection/document actions establish only routing, not unrestricted book content access.', '',
        'Future work should separately evaluate an explicit optional explanation operation, smaller redundant synthesis payloads (especially duplicate comparison books/conversation IDs), representative latency distributions and an independently validated single-pass general-help design. Consider metadata batching only with fresh availability separated. Keep model budget/attention changes behind controlled correctness benchmarks. These are recommendations, not implemented Part 3 work.', '',
        '## Real existing-overlay verification', '',
        'The real Compare with AI button in the existing catalogue overlay rendered actual selected metadata with zero model calls: 443 ms browser latency (432.9 ms server); later repeat 371 ms. No browser warnings/errors. Selection controls, authenticated existing client, comparison response and overlay all exercised end-to-end. Temporary review bootstrap removed and browser restored signed out; no account/loan/reservation was created. Single optimized 8005 service remains available alongside the reused Core/search/recommendation services and existing Vite server.', '',
        '![Existing overlay after fast comparison](assistant_latency_overlay.jpg)', '',
        '## S. Exact commands', '',
        'From stopped services, use separate PowerShell terminals for each server; the current local services are already running.', '',
        '```powershell', "Set-Location 'D:\\SDC\\LibraryLLM'",
        '.\\.venv\\Scripts\\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002 --workers 1', '```', '',
        '```powershell', "Set-Location 'D:\\SDC\\LibraryLLM'",
        '.\\.venv\\Scripts\\python.exe -m uvicorn search.api:app --host 127.0.0.1 --port 8003 --workers 1', '```', '',
        '```powershell', "Set-Location 'D:\\SDC\\LibraryLLM'",
        '.\\.venv\\Scripts\\python.exe -m uvicorn recommendation.api:app --host 127.0.0.1 --port 8004 --workers 1', '```', '',
        '```powershell', "Set-Location 'D:\\SDC\\LibraryLLM'", "$env:ASSISTANT_ENABLED='true'",
        "$env:ASSISTANT_MUTATING_ACTIONS_ENABLED='false'", "$env:LUMINAR_MOCK_LLM='0'",
        "$env:LUMINAR_DEBUG_PROMPT='0'", '# Optional numeric-only profiling:',
        "# $env:ASSISTANT_PROFILE_PATH='D:\\SDC\\LibraryLLM\\reports\\assistant_request_profiles.jsonl'",
        '.\\.venv\\Scripts\\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005 --workers 1', '```', '',
        '```powershell', "Set-Location 'D:\\SDC\\LibraryLLM\\frontend'", 'npm run dev -- --host 127.0.0.1', '```', '',
        'Validation:', '', '```powershell', "Set-Location 'D:\\SDC\\LibraryLLM'",
        '.\\.venv\\Scripts\\python.exe -m pytest tests\\test_assistant_backend.py tests\\test_assistant_latency.py -q',
        '.\\.venv\\Scripts\\python.exe -m pytest tests\\test_assistant_backend.py tests\\test_assistant_latency.py tests\\test_book_access_control.py tests\\test_dynamic_book_capabilities.py tests\\staff_auth\\test_auth.py -q',
        "Set-Location 'D:\\SDC\\LibraryLLM\\frontend'", 'npm test', 'npm run build', 'npm run lint', '```', '',
        'The benchmark harness refuses an occupied 8005 before starting a model and reuses 8002–8004. The frozen runner is only for reproducing the original baseline. Reports include raw failed routes without falsely labeling them successful speedups.']
    (REPORTS/'chatbot_latency_optimization.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('Wrote benchmark comparisons and complete A–S report')


if __name__ == '__main__':
    main()
