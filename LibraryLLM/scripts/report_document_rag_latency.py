"""Build the A–R report from retained measurements, never invent timings."""
import hashlib
import json
import math
from pathlib import Path
import statistics
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reports'
def read(name):return json.loads((R/name).read_text(encoding='utf-8'))
def stats(values):
    return dict(n=len(values),min_ms=min(values),median_ms=statistics.median(values),p90_ms=sorted(values)[math.ceil(.9*len(values))-1],max_ms=max(values))
def metrics(row):
    rag=row['rag'];profile=row['profile'];stages=rag.get('timing_ms',{})
    calls=[dict(purpose=o['purpose'],**c) for o,c in zip(row['observation']['generations'],profile['qwen_calls'])]
    return dict(semantic_ms=stages.get('intent_analysis',0),retrieval_ms=stages.get('retrieval',0),
                evidence_validation_ms=stages.get('validation',0),answer_generation_ms=stages.get('generation',0),
                source_construction_ms=stages.get('response',0),serialization_ms=profile['stages_ms']['response_serialization'],
                client_total_ms=row['client_total_ms'],server_total_ms=profile['total_ms'],qwen_call_count=profile['qwen_call_count'],model_calls=calls)
def main():
    b=read('document_rag_baseline_raw.json');f=read('document_rag_final_raw.json')
    assert len(b['runs'])==len(f['runs'])==42 and f['real_state_unchanged']
    old={(r['case'],r['round']):r for r in b['runs']}
    comparisons=[]
    for row in f['runs']:
        base=old[row['case'],row['round']]
        comparisons.append(dict(case=row['case'],round=row['round'],
            semantic_equal=row['rag'].get('intent_data')==base['rag'].get('intent_data'),
            retrieval_order_equal=[x['chunk_ids'] for x in row['observation']['retrieval']]==[x['chunk_ids'] for x in base['observation']['retrieval']],
            validation_equal=row['observation']['validation']==base['observation']['validation'],
            fast_filter_equal=all(row['rag'].get(k)==base['rag'].get(k) for k in ['fast_filter_decision','fast_filter_signals','fast_filter_reasons']),
            verdict_equal=row['rag'].get('verdict')==base['rag'].get('verdict'),
            full_sources_equal=row['rag'].get('sources')==base['rag'].get('sources'),
            answer_byte_equal=row['rag']['answer']==base['rag']['answer']))
    assert all(all(r[k] for k in ['semantic_equal','retrieval_order_equal','validation_equal','fast_filter_equal','verdict_equal','full_sources_equal']) for r in comparisons)
    cases=[]
    for name in dict.fromkeys(r['case'] for r in f['runs']):
        before=[r for r in b['runs'] if r['case']==name];after=[r for r in f['runs'] if r['case']==name]
        cases.append(dict(case=name,question=after[0]['question'],document_id=after[0]['document_id'],categories=after[0]['categories'],
            baseline=stats([r['client_total_ms'] for r in before]),optimized=stats([r['client_total_ms'] for r in after]),
            semantic_baseline=before[0]['rag'].get('intent_data'),semantic_optimized=after[0]['rag'].get('intent_data'),
            baseline_runs=[metrics(r) for r in before],optimized_runs=[metrics(r) for r in after]))
    deps=[
      dict(field='intent',producer='Tier 1 grammar or Tier 2 IntentSchema',consumer='rag/evidence.py scoring; rag/reranker.py ordering; rag/fast_filter.py guards; full validator JSON',required='yes',fallback='original classifier',impact='Changes relevance, selected context and support decision'),
      dict(field='actor',producer='Tier 1 / Tier 2 literal slot',consumer='calculate_evidence_score actor terms and subject alignment; compute_alignment_signals actor presence; full validator JSON',required='nullable but material',fallback='original classifier/default None only when original schema allows',impact='Changes actor alignment, context ranking and actor support'),
      dict(field='action',producer='Tier 1 / Tier 2 literal slot',consumer='calculate_evidence_score action/event terms; compute_alignment_signals event/polarity checks; full validator JSON',required='nullable but material',fallback='original classifier',impact='Changes event matching, directional/causal evidence and support'),
      dict(field='target',producer='Tier 1 / Tier 2 literal slot',consumer='calculate_evidence_score combines target terms with action and object alignment; compute_alignment_signals target presence; full validator JSON',required='nullable but material',fallback='original classifier',impact='Changes object/target alignment and relationship direction'),
      dict(field='polarity',producer='IntentSchema positive/negative',consumer='evidence scoring, fast-filter negation/polarity and validator JSON',required='yes/default positive',fallback='original classifier',impact='Can reject negated/contradicted claims'),
      dict(field='temporal_relation',producer='Tier 1 grammar/Tier 2',consumer='fast-filter temporal before/after alignment; full validator JSON',required='nullable hint, still material',fallback='original classifier; preserve NONE versus null',impact='Can reject temporal conflicts'),
      dict(field='question_focus',producer='Tier 1 / Tier 2',consumer='generic-cache eligibility and complete JSON in validator prompt',required='no direct rank arithmetic, preserve nevertheless',fallback='original classifier',impact='Changing focus changed validator behavior in compact experiment'),
      dict(field='confidence',producer='IntentSchema constrained float [0,1]',consumer='Pydantic validates, then analyze_intent discards it',required='required model validation, absent in returned intent_data',fallback='retain original schema',impact='Not a downstream ranking value; defaults alone did not prove semantic equivalence'),
      dict(field='tier_used',producer='Python classifier branch',consumer='returned metadata and full JSON in evidence validator prompt',required='compatibility metadata',fallback='preserve legacy label',impact='Metadata can affect the model prompt; call-count telemetry reports actual skipped calls'),
    ]
    quality={
      'method':'Manual claim review against selected existing chunks, exact fallback answer comparison, six boundary equivalence checks over all 42 pairs; keyword tests supplement rather than replace review.',
      'rbac_definition':'Grounded role/permission/database explanation. Preserves the essential definition and examples; no added world facts. 53 generated tokens, natural EOS.',
      'roles':'Lists read, readWrite, dbAdmin, userAdmin and root from the document. Removes baseline mislabeling of readOnly and unsupported role/responsibility mixing. 26 generated tokens; question asks which roles, not a full permissions tutorial.',
      'indexing':'Preserves creating/listing/dropping indexes and required permissions. Omits verbose examples and unrelated username discussion. 30 generated tokens including EOS, natural completion.',
      'all_other_cases':'All 33 fallback answers are byte-identical to baseline, including refusals, quoted readWrite, accepted GRU/autoencoder definitions, temporal and implementation answers.',
      'known_baseline_limitations':'GRU selected passages disagree: hidden-state formula uses (1-z) old + z candidate, while a numerical example treats z=0.9 as retaining 90% old state. The original implementation answer also mixes reset/update equations and reaches its 320-token cap. It remains byte-identical; this task does not certify it as factually correct.',
      'rejected_quality_candidates':'Compact semantic schema changed RBAC/roles verdicts despite identical retrieved IDs and changed a GRU validation path. Initial short definition prompts lost reset-gate/reconstruction details and were reverted. Short implementation prompts mislabeled a reset-gate formula and were reverted.',
      'conclusion':'No meaningful new regression in this frozen corpus. Absolute correctness of every legacy answer is not claimed.'}
    ops_old=read('part3_repair_latency_final_raw.json')['summary']
    ops_control=read('document_rag_other_ops_control_baseline.json')
    ops_fast=read('document_rag_other_ops_control_fast.json')
    ops=[dict(case=r['case'],previous_warm_median_ms=ops_old[r['case']]['median_ms'],same_worker_baseline_ms=next(s['total_ms'] for s in ops_control['runs'] if s['case']==r['case']),
              final_warm_ms=r['total_ms'],qwen_calls=r['profile']['qwen_call_count'],status=r['status'],errors=r['errors']) for r in ops_fast['runs']]
    report=dict(decision='A. DOCUMENT RAG <=15S TARGET ACHIEVED WITH CORRECTNESS PRESERVED',
        decision_scope='Median target achieved; correctness preserved relative to frozen behavior. Stretch p90 missed and known baseline GRU quality limitations remain.',
        baseline=b['summary'],optimized=f['summary'],representative_rbac=next(c for c in cases if c['case']=='rbac_definition'),
        methodology={'questions':14,'documents':3,'warm_repetitions':3,'baseline_requests':42,'optimized_requests':42,'cache':'off for final; no repeated semantic-cache hits counted',
            'execution':'Sequential requests, one inference lock, one resident Qwen worker at any moment, no concurrent Qwen generates.',
            'worker_lifecycle':'Two sequential process lifetimes: initial baseline/compact trial worker stopped before replacement. All accepted candidate reloads preserve replacement PID 28144 and model id 1683290197904. No second simultaneous resident model.',
            'statistic':'Nearest-rank p90; client wall includes authentication, service overhead and serialization. Warmup excluded. Per-question p90 of three samples equals maximum.',
            'empty_case':'Explain RBAC has zero retrieved chunks in baseline and final; zero-call optimized timing preserves the original no-evidence result and is not presented as a supported answer.'},
        semantic_dependencies=deps,per_question=cases,equivalence=comparisons,prompt_audit=read('document_rag_prompt_audit.json'),
        cache_trial=read('document_rag_cache_trial_raw.json'),security=read('document_rag_security.json'),quality=quality,
        rejected_experiments={'compact_semantic':'document_rag_compact_trial_raw.json','early_answer_prompt':'document_rag_fast_trial_raw.json',
                              'implementation_quality':'document_rag_quality_trial_raw.json','implementation_followup':'document_rag_implementation_trial_raw.json'},
        semantic_output_observation={'baseline_max_generated_tokens':max(c['generated_tokens'] for r in b['runs'] for o,c in zip(r['observation']['generations'],r['profile']['qwen_calls']) if o['purpose']=='semantic'),
            'optimized_fallback_max_generated_tokens':max(c['generated_tokens'] for r in f['runs'] for o,c in zip(r['observation']['generations'],r['profile']['qwen_calls']) if o['purpose']=='semantic'),
            'cap_retained':400,'reason':'Original outputs naturally terminate; lowering the cap alone does not save tokens. Rejected compact transport cannot justify a production cap change.'},
        other_operations=ops,other_operation_state_unchanged=ops_control['real_state_unchanged'] and ops_fast['real_state_unchanged'],
        integrity=read('document_rag_integrity.json'),runtime=read('document_rag_profiles.jsonl.runtime.json'),
        production_confirmation=read('document_rag_production_confirmation_raw.json'),
        cleanup=json.loads((R/'document_rag_cleanup.json').read_text(encoding='utf-8-sig')),
        tests={'backend':'389 passed, 10 existing skipped (336 original/repair/contracts + 53 focused)',
               'extra_domain_contracts':'14 passed in initial broader 376-test run','frontend':111,'independent_backend':16,'independent_frontend':5,
               'build':'PASS','lint':'exit 0; 18 unchanged warnings','warning':'Existing FastAPI/Starlette httpx deprecation'},
        production_changes=['rag/document_latency.py new document-only adapter; same engine and model, no generator/validator replacement',
                            'rag/api.py top-level import and installation only; every original function/class AST unchanged'],
        remaining_bottleneck='Long legacy grounded answer generation for implementation/temporal questions; 320/276 tokens take approximately 32–44 seconds. Other fallback semantic calls still cost approximately 8–12 seconds. Validator unchanged, typically 1.5–2.5 seconds.',
        stop='No Part 4, retrieval experiment, new model/runtime/dependency, scoring change or account/circulation write.')
    assert report['optimized']['median_ms']<=15000
    (R/'document_rag_latency_final.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    def seconds(n):return f'{n/1000:.2f}'
    sections=['# Document RAG latency finalization',
      f"Decision **A**: warm median **{seconds(f['summary']['median_ms'])} s**; representative RBAC median **{seconds(report['representative_rbac']['optimized']['median_ms'])} s**, from **{seconds(report['representative_rbac']['baseline']['median_ms'])} s**. Stretch p90 **{seconds(f['summary']['p90_ms'])} s** remains above 18 s. Correctness preservation is relative to the frozen baseline; the existing GRU implementation answer has known quality defects.",
      '## A. Original exact call graph',
      '`assistant/api.py:install_assistant.chat` authenticates/current identity and validates action/context → `assistant/orchestrator.py:chat` / DOCUMENT_QUESTION tool routing → callback into `rag/api.py:ask` (RAGRequest, HTTP credentials) through threadpool → shared `engine.inference_lock` → `rag/services/book_access.py:authorize_selection` → `rag/qa.py:LuminaRAG.ask` (`profile_request`, `serialized_inference`, same RLock) → `rag/llm.py:analyze_intent` / `_analyze_intent_uncached` → `rag/reranker.py:search` / retriever MiniLM+FAISS and CrossEncoder → evidence ranking → `select_diverse_context` / `build_context` → `rag/fast_filter.py:run_fast_filter` → `rag/llm.py:validate_evidence` top-3 combined (and original partial second pass) → `build_prompt` / `build_compact_prompt` / original refusal prompt → `LuminaRLLM.generate` → deterministic deduped sources in `qa.py:ask` → unchanged assistant schemas/Pydantic/FastAPI serialization.',
      'Semantic slots affect evidence scores and ranked context before validation/answering. Combining semantic classification with answering after retrieval is therefore invalid; no single-pass experiment was run.',
      '## B. Semantic dependency analysis',
      '| Field | Producer | Consumers | Required / fallback | Correctness impact |\n|---|---|---|---|---|',
      *[f"| {d['field']} | {d['producer']} | {d['consumer']} | {d['required']}; {d['fallback']} | {d['impact']} |" for d in deps],
      '## C. Fields actually consumed',
      'Actual public/internal semantic dictionary: intent, actor, action, target, polarity, temporal_relation, question_focus, tier_used. IntentSchema additionally validates confidence then discards it. There is no object or causal_relation field to remove. Even question_focus/tier_used enter the complete validator JSON, so they cannot be treated as harmless unused fields. The JSON report records every baseline and final semantic dictionary.',
      '## D. Deterministic fast paths',
      'Four tightly bounded literal grammars: `Explain ACRONYM` (no expansion), `According to this PDF, what is noun phrase`, exact roles-described-in-this-document question, and `How is noun phrase implemented in ACRONYM`. Up to six literal words; original full IntentSchema validation and original returned slots/compatibility tier label. The implementation answer prompt remains original. Negation, causal/temporal clauses, multiple entities, quoted terms, ambiguous references and uncertain grammar fall through to the existing classifier. Previously accepted GRU/autoencoder definition paths remain unchanged. Global and book selections remain original.',
      '## E. Compact schema experiment and cache',
      'Rejected compact aliases i/a/v/o/p/t/f/c retained outside production in `document_rag_rejected_compact_candidate.py` and raw compact-trial evidence. Strict aliases mapped through the original full schema; optional null/default values were tested. Nonetheless RBAC and roles became NOT_SUPPORTED despite identical retrieved IDs; a GRU validation path also changed. The compact transport is removed from production, and installation rejects mode=compact. Original semantic cap remains 400; outputs naturally finish before it, so lowering the theoretical cap alone offers no proven speedup.',
      'Optional metadata-only cache: SHA-256 normalized question + document_id + code/classifier hash, maximum 128 entries, TTL 120 seconds, locked copies. Default fast mode disables it. Separate indexing trial: '+', '.join(f"run {r['round']}: {seconds(r['client_total_ms'])} s / {r['profile']['qwen_call_count']} calls" for r in report['cache_trial']['runs'])+'. First run uses original semantic inference; later hits are explicitly excluded from the final 42-request statistics. No private document text is cached.',
      '## F. Answer-prompt changes',
      'Compact grounding/style instructions only for conservative definition/topic questions outside the already accepted ordinary_book_intent path, normal/concise depth. Exact context retained byte-for-byte: every passage, header and source identifier. No question or passage duplication was found. Repeated filenames are retained to keep source association clear. Targets 60–100 tokens where useful, allows shorter complete answers, retains 320-token safety budget and natural EOS. Structured citations were already constructed by the backend; no public source schema changed. Refusals, causal/negative/temporal/quoted questions, detailed depth and implementation prompts remain original.',
      '## G. Token reductions',
      '| Case | Baseline answer input → final | Baseline output → final |\n|---|---|---|',
    ]
    for name in ['rbac_definition','roles','indexing']:
        before=next(r for r in b['runs'] if r['case']==name);after=next(r for r in f['runs'] if r['case']==name)
        oc=before['profile']['qwen_calls'][-1];nc=after['profile']['qwen_calls'][-1]
        sections.append(f"| {name} | {oc['input_tokens']} → {nc['input_tokens']} | {oc['generated_tokens']} → {nc['generated_tokens']} |")
    sections += [
      'Prompt audit: shared system 60 tokens; RBAC question 12, evidence body 860, source headers 143, complete context 1004. Instructions/format 623 → 211 tokens. All other component counts are in the JSON. Full warm tokenization costs 3.8–5.2 ms: no static prefix cache was introduced. Existing token-enforcer/trie cache remains. Overlapping deterministic metadata work would save sub-millisecond source formatting and add complexity; no Qwen pipelining was introduced.',
      '## H. Qwen calls',
      'RBAC/roles/GRU implementation: 3 → 2; acronym with empty retrieval: 1 → 0. Indexing retains 3 calls, with a shorter answer. All remaining classifier/validator call paths stay as baseline. Evidence validation is unchanged across all 42 paired observations, including checked IDs, mode, result and count. Single Qwen2.5-3B NF4 CUDA, luminar_sdpa, KV cache, one inference lock; no concurrent model generation.',
      '## I. Baseline latency',
      f"42 sequential warm requests: min {seconds(b['summary']['min_ms'])}, median {seconds(b['summary']['median_ms'])}, p90 {seconds(b['summary']['p90_ms'])}, max {seconds(b['summary']['max_ms'])} s. Representative RBAC is ~25.46 s. Warm startup and excluded warmup are distinct from request time.",
      '## J. Optimized latency',
      f"42 cache-free sequential warm requests: min {seconds(f['summary']['min_ms'])}, median {seconds(f['summary']['median_ms'])}, p90 {seconds(f['summary']['p90_ms'])}, max {seconds(f['summary']['max_ms'])} s. The median meets target; the tail does not improve to the stretch target. Empty-retrieval acronym timing preserves baseline behavior and is not an answered question.",
      '## K. 14 questions × 3 repetitions',
      '| Case | Before median s | After min s | After median s | After p90 s | After max s | Calls before → after |\n|---|---:|---:|---:|---:|---:|---|',
      *[f"| {c['case']} | {seconds(c['baseline']['median_ms'])} | {seconds(c['optimized']['min_ms'])} | {seconds(c['optimized']['median_ms'])} | {seconds(c['optimized']['p90_ms'])} | {seconds(c['optimized']['max_ms'])} | {c['baseline_runs'][0]['qwen_call_count']} → {c['optimized_runs'][0]['qwen_call_count']} |" for c in cases],
      'Every run includes semantic/retrieval/validation/answer/source-construction/serialization/client/server stages, per-call input/output tokens, actual Qwen call count and latency in the JSON report. Raw trace profiles and generation observations are retained. All 42 requests returned HTTP 200 with no errors. Three uploaded PDFs cover definitions, how/why, causal, actor, negative, multiple entities, acronym, ambiguity, quoted phrase and document reference questions.',
      '## L. Source/verdict equivalence',
      '42/42 semantic dictionaries, complete ranked retrieval order, validator observations, fast-filter decisions/signals, verdicts and full returned source objects are identical. Candidate count/context selection/embeddings/index/chunking/reranker/evidence code and original function bodies are unchanged. No unexpected retrieval divergence remains. All 33 fallback answer strings are byte-identical.',
      '## M. Answer quality',
      *[f"**{k}**: {v}" for k,v in quality.items()],
      '## N. Authorization/security',
      'All 13 read-only live probes passed: missing/invalid assistant identity 401, cross-user conversation 404, missing/traversal/absolute source 404, mismatched source IDs 400, book anonymous 401 and absent entitlement 403. Two distinct users can access the same uploaded document with source IDs restricted to that selection: existing uploads are shared/public. There is no owner-scoped cross-user upload denial to claim. One injection/source-boundary probe returned only selected-document sources and no account/book records; this supplements existing regressions and is not a proof of general injection immunity. Authorization remains before generation; no arbitrary file path is read from the selected ID.',
      '## O. Regressions and freeze',
      'Expanded backend 389 passed, 10 existing skips: 336 prior required/repair/independent checks plus 53 focused checks. Independent backend 16 passed; frontend 111 passed, independent frontend 5 passed, production build passed, lint exit 0 with 18 unchanged warnings. An initial broader run also passed the 14 unrelated domain contracts. New tests cover context exception/parallel isolation, original semantic fallback, rejected schema validation, 42-pair retrieval/validator/verdict/source/answer equivalence, metadata cache and real telemetry. One existing httpx deprecation remains.',
      '1208 files frozen (including 681 previous report files). Integrity comparison finds only `rag/api.py` changed among frozen files: two top-level installation lines, all existing function/class ASTs intact. New adapter adds no model loader and leaves llm.generate/validator/reranker identity intact. Existing assistant/frontend/auth/document service/book RAG/scoring and all prior report evidence remain byte-identical.',
      'After removing the rejected transport code, a fresh request through the shipped adapter took 8.894 s with exactly the same RBAC answer, semantic dictionary, validator observation and full sources as the final corpus. This confirmation is separate from, and does not replace, the 42-run statistics.',
      '## P. Other operations latency sanity',
      'One initial pass exposed cold recommendation-service caches. A warmed baseline/fast control on the same resident worker isolates environment variation from document-only code changes. No optimization of these operations was performed. Counts and status/error checks remain intact, and all 15 final warm requests are below 15 s. Single-request sanity timings are not new median estimates.',
      '| Operation | Previous median s | Same-worker original s | Final warm s | Qwen calls |\n|---|---:|---:|---:|---:|',
      *[f"| {o['case']} | {seconds(o['previous_warm_median_ms'])} | {seconds(o['same_worker_baseline_ms'])} | {seconds(o['final_warm_ms'])} | {o['qwen_calls']} |" for o in ops],
      '## Q. Final decision',
      '**A — DOCUMENT RAG <=15S TARGET ACHIEVED WITH CORRECTNESS PRESERVED**, scoped to median warm latency and no meaningful regression against the frozen behavior. Primary median PASS; stretch p90 FAIL/PARTIAL. Existing GRU answer defects are documented, not relabeled as correct. Real circulation/reading-list state stayed unchanged.',
      '## R. Remaining bottleneck and stop',
      report['remaining_bottleneck'],
      report['methodology']['worker_lifecycle'],
      'This narrow experiment stops here. No Part 4 or new retrieval work. Owned service cleanup is recorded in `document_rag_cleanup.json`. Reproduction: run the loopback harness with the same offline environment, baseline control and benchmark --mode baseline; then fast control and benchmark --mode fast. Output phase names must be new because collectors refuse evidence overwrite. Production runs `rag.api:app` and exposes no experiment-control route.',
    ]
    rendered=sections[0]
    for previous,section in zip(sections,sections[1:]):
        separator='\n' if previous.splitlines()[-1].startswith('|') and section.startswith('|') else '\n\n'
        rendered+=separator+section
    (R/'document_rag_latency_final.md').write_text(rendered+'\n',encoding='utf-8')
if __name__=='__main__':main()
