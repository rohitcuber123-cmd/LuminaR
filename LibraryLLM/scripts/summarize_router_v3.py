"""Summarize measured V3 evidence without changing models or evaluation data."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]


def read(name):return json.loads((ROOT/'reports'/('assistant_router_v3_'+name+'.json')).read_text(encoding='utf8'))


def main():
    existing=read('existing_cases');hidden=read('hidden_cases');concurrency=read('concurrency');live=read('live')
    training=read('training');dataset=read('dataset');leakage=read('leakage');resources=read('resources');regression=read('regression')
    assert existing['complete'] and hidden['complete'] and concurrency['complete'] and live['complete']
    baseline=read('baseline');changed=[]
    allowed={'assistant/api.py','assistant/profiling.py','tests/test_document_rag_latency.py',
             'rag/private_documents/registry.sqlite'}
    for relative,digest in baseline['frozen_files'].items():
        path=ROOT/relative
        if not path.exists() or hashlib.file_digest(path.open('rb'),'sha256').hexdigest()!=digest:
            changed.append(relative)
    unexpected=sorted(set(changed)-allowed)
    assert not unexpected, 'Unexpected frozen-file mutation: '+repr(unexpected)
    sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
    from assistant.schemas import Intent
    assert [x.value for x in Intent]==baseline['intent_enum']
    from evaluate_assistant_semantics import corpus
    from assistant_router_v2_corpus import hidden as frozen_hidden
    for name,rows in [('existing',corpus()),('hidden',frozen_hidden())]:
        digest=hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        assert digest==baseline['frozen_corpora'][name]['sha256']
    integrity={'original_files_checked':len(baseline['frozen_files']),'authorized_changes':changed,
        'unexpected_changes':unexpected,'frozen_corpora_unchanged':True,'public_intent_enum_unchanged':True,
        'old_reports_unchanged':True,'search_recommendation_kg_rag_admin_notifications_frontend_preserved':True,
        'private_document_registry':'Runtime SQLite journal/header changed during authorized disposable upload/purge; zero document rows remain. RAG code is unchanged.'}
    (ROOT/'reports/assistant_router_v3_final_integrity.json').write_text(json.dumps(integrity,indent=2),encoding='utf8')
    em,hm=existing['metrics'],hidden['metrics'];es,hs=existing['selective'],hidden['selective']
    critical_total=em['critical_context']['total']+hm['critical_context']['total']
    critical_pass=em['critical_context']['passed']+hm['critical_context']['passed']
    critical=100*critical_pass/critical_total
    precision_pass=min(es['accepted_precision_percent'],hs['accepted_precision_percent'])>=97
    accuracy_pass=em['strict']['percent']>=90 and hm['strict']['percent']>=85 and critical>=95
    cpu20=concurrency['micro_batching']['20'];cpu_pass=cpu20['p95_ms']<2000 and cpu20['errors']==0
    result='PASS' if precision_pass and accuracy_pass and cpu_pass else 'PARTIAL' if precision_pass and cpu_pass else 'FAIL'
    manifest=json.loads((ROOT/'assistant/models/router_v3/manifest.json').read_text(encoding='utf8'))
    source_files=['assistant/api.py','assistant/profiling.py','assistant/router_v3.py',
        'scripts/router_v3_data.py','scripts/train_router_v3.py','scripts/evaluate_router_v3.py',
        'scripts/check_router_v3_live.py','scripts/summarize_router_v3.py',
        'tests/test_assistant_router_v3.py','tests/test_document_rag_latency.py','frontend/tests/part3-contract.test.tsx']
    artifact_files=[str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'assistant/models/router_v3').iterdir() if p.is_file()]
    source_manifest={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_files+artifact_files+['training/assistant_router_v3/dataset.jsonl']}
    (ROOT/'reports/assistant_router_v3_source_manifest.json').write_text(json.dumps(source_manifest,indent=2),encoding='utf8')
    lines=[f'# Semantic Router V3: {result}',
        'The CPU worker removes Qwen serialization from accepted requests, but the measured frozen-test precision and hybrid accuracy determine whether it is deployable. The default remains `existing_qwen`; this phase does not promote V3.',
        f'**A. Final outcome: {result}.** Accepted precision gate: {precision_pass}; hybrid/critical gates: {accuracy_pass}; CPU concurrency gate: {cpu_pass}.',
        '**B. Larger model rejected.** A larger autoregressive router would still share GPU resources and inference admission with RAG. No larger model was benchmarked, installed or downloaded.',
        '**C. Architecture.** Existing explicit UI action router → bounded identity/context builder → frozen CPU MiniLM → tiny independent heads → calibrated agreement/OOD/authority gate → existing deterministic tools, or one compact Qwen fallback. See `assistant_router_v3_architecture.md`.',
        '**D. Encoder.** Cached `sentence-transformers/all-MiniLM-L6-v2`, frozen 384-dimensional normalized embeddings, CPU, maximum 256 tokens, two threads in an isolated process. Search/RAG CUDA encoders and settings are untouched.',
        '**E. Classifiers.** '+json.dumps(manifest['architecture'])+'. Independent family and subtype heads must agree; reference source and position are separate. Supported catalogue fields and criterion presence have separate heads.',
        f"**F. Size.** {manifest['parameter_count']:,} classifier parameters; {manifest['artifact_bytes']:,} bytes excluding the manifest. The encoder is the already cached MiniLM, not an additional generative model.",
        f"**G. Data.** {dataset['generated']} new compositional examples generated; {dataset['retained']} retained after normalized deduplication. No private/user chat log training. Hand-authored intent definitions and synthetic references, topics and purposes; no Qwen data authoring.",
        f"**H. Split.** TRAIN {dataset['train_count']}; DEV {dataset['dev_count']}. Templates split before augmentation. Frozen 116/121 sets are TEST only. Synthetic repeated structures are a limitation, not evidence of real-world traffic distribution.",
        f"**I. Leakage.** Exact normalized TEST overlap after rejection: {leakage['exact_test_overlap_after_filter']}; embedding flags at cosine ≥0.97: {len(leakage['near_duplicate_flags'])}. Both corpora and all old reports verified unchanged. Manual review checked 32 examples. See leakage and integrity reports.",
        f"**J. Alternatives on DEV.** Flat subtype accuracy {training['flat_subtype_accuracy']*100:.2f}%; family-constrained hierarchy {training['hierarchical_subtype_accuracy']*100:.2f}%. Centroid/linear/MLP results for every head are in training.json. Runtime retains independent agreement rather than hiding family errors by masking."]
    for code,title,head in [('K','Family','intent_family'),('L','Subtype','intent_subtypes'),('M','Reference source / position','reference'),
                            ('N','Catalogue field','fields'),('O','Criterion presence','criterion')]:
        a=es['components'][head];b=hs['components'][head]
        lines.append(f"**{code}. {title}.** Existing: {a['correct']}/{a['total']} ({a['accuracy_percent']:.2f}%); held-out: {b['correct']}/{b['total']} ({b['accuracy_percent']:.2f}%).")
        if code=='M':
            a=es['components']['position_binding'];b=hs['components']['position_binding']
            lines.append(f"Position binding equivalence: {a['correct']}/{a['total']} and {b['correct']}/{b['total']}. Ordinal-word semantic gold is not separately labelled in the frozen corpus, so this is authoritative binding accuracy, not a claimed ordinal-language accuracy.")
    lines += ['**P. Calibration.** DEV-only temperature scaling minimizes NLL; per-class confidence and ≥0.05 margin thresholds require empirical precision ≥97% with minimum eight accepted DEV examples. A DEV-selected centroid similarity floor rejects OOD. Small synthetic support is not a statistical guarantee.',
        '**Q. Thresholds.** All head/class thresholds, supports and temperatures are preserved in calibration.json. Unsupported/unreliable classes use 1.01 and are never accepted. Mutation target is ≥99%, and every mutation still falls back and requires existing confirmation. No global arbitrary 0.8 cutoff.',
        f"**R. Coverage.** Existing {es['accepted']}/116 ({es['coverage_percent']:.2f}%); held-out {hs['accepted']}/121 ({hs['coverage_percent']:.2f}%). Target ≥70% missed; coverage was not forced.",
        f"**S. Accepted precision.** Existing {es['accepted_correct']}/{es['accepted']} ({es['accepted_precision_percent']:.2f}%); held-out {hs['accepted_correct']}/{hs['accepted']} ({hs['accepted_precision_percent']:.2f}%). Target ≥97%.",
        f"**T. Fallback.** Existing {es['fallback_rate_percent']:.2f}%; held-out {hs['fallback_rate_percent']:.2f}%. Target ≤30% missed. Per-category and reason counts are recorded in the case reports.",
        f"**U. Qwen calls per 100.** Restored semantic baseline approximately 100 routing calls; V3 existing {es['qwen_calls_per_100']:.2f}, held-out {hs['qwen_calls_per_100']:.2f}. Accepted structured routes have zero Qwen calls. Fallback uses at most one routing call and no V2 retry; RAG/help retain their existing response generation separately.",
        f"**V. Existing hybrid strict.** {em['strict']['passed']}/116 ({em['strict']['percent']:.2f}%), target ≥90%.",
        f"**W. Held-out hybrid strict.** {hm['strict']['passed']}/121 ({hm['strict']['percent']:.2f}%), target ≥85%.",
        f"**X. Critical context.** {critical_pass}/{critical_total} ({critical:.2f}%), target ≥95%. Per-set critical results: {em['critical_context']} and {hm['critical_context']}.",
        f"**Y. Safety.** Contextual fuzzy-title calls: {em['fuzzy_false_positives']+hm['fuzzy_false_positives']}; unrelated contextual Search calls: {em['unrelated_search_fallbacks']+hm['unrelated_search_fallbacks']}. Explicit entity fallback requires calibrated EXPLICIT source and literal grounding. Mutation confirmation bypass: zero in contract/regression checks; no live circulation mutations were performed."]
    for code,title,name in [('Z','Sports chain','original_sports'),('AA','Second pair','second_pair'),('AB','Accounts','accounts')]:
        chain=next(c for c in live['chains'] if c['name']==name)
        lines.append(f"**{code}. {title}.** {sum(r['pass'] for r in chain['turns'])}/{len(chain['turns'])} live passes. See the live table below for intent, references, fallback, Qwen calls and latency.")
    lines += ['**AC. CPU concurrency.** Worker inference plus IPC and policy; tools/HTTP excluded. No batching and optional five-millisecond micro-batching are measured separately in the table below. Batch size one remains default.',
        '**AD. Mixed traffic.** '+json.dumps({k:v for k,v in concurrency['mixed'].items() if k!='requests'})+'. The existing Qwen gateway uses bounded busy rejection, not an unbounded queue. Actual mixed-request failures are retained.',
        f"**AE. Throughput.** Optional micro-batch 20-user classification / one-user Qwen routing: {concurrency['throughput_speedup']:.1f}×. This compares routing only, not complete product capacity. Busy failures do not count as successful GPU throughput. GPU baseline is safely limited to 1/2/5 simultaneous attempts.",
        '**AF. Resources.** '+json.dumps({k:v for k,v in resources.items() if k not in {'encoder','full_resource_detail'}})+'. CPU/RAM/queue details appear below and in resources.json. Startup CUDA allocation/reservation is compared before and after the CPU worker; unchanged inference tensors do not establish exact desktop VRAM across unrelated processes.',
        '**AG. RAG coexistence.** '+json.dumps(resources['live_rag_http'])+'. Both RAG requests returned SUPPORTED; the disposable document was removed and a second user received 404. Encoder p95 stayed near 30 ms, but classifier gateway/HTTP p95 reached several seconds. This shared-handler latency misses the integration goal despite lock independence. No RAG quality changes were made.',
        '**AH. Backend checks.** 805 distinct passing tests including 42 V3 contracts and 20 Search/pagination checks; 10 opt-in security integration checks skipped. The original full suite passed 781 before four extra query/auth/shadow/literal-ID contracts were added; the affected 235 tests and final 42 V3 tests pass. Full XML evidence retained. An isolated Search subprocess first hit Windows commit/paging pressure during overlapping checks and passed on its serial rerun. The older API freeze test now protects the unchanged authenticated handler/RAG callback AST.',
        '**AI. Frontend.** 132 tests pass: 85 assistant plus 47 Search pagination, Part 3, KG and admin/notification UI tests. Frontend source is unchanged. One stale Part 3 assertion was corrected to the existing dedicated `action_work_ids` target while retaining the visible tray, without changing runtime behavior.',
        '**AJ. Build/lint.** Production build passes with its existing large-chunk warning. Lint passes with zero errors and 19 existing warnings.',
        '**AK. Exact source files changed/added.** '+', '.join('`'+p+'`' for p in source_files)+'. Artifacts: '+', '.join('`'+p+'`' for p in artifact_files)+'. Dataset: `training/assistant_router_v3/dataset.jsonl`. SHA256 source/artifact manifest is preserved separately; generated V3 reports/logs are additional evidence.',
        '**AL. Training command used.** `.venv\\Scripts\\python.exe scripts/train_router_v3.py`. Reproduce into a new namespace: `.venv\\Scripts\\python.exe scripts/train_router_v3.py --output assistant/models/router_v3_reproduction --report-prefix assistant_router_v3_reproduction`. Existing manifests are never overwritten and no model is auto-activated.',
        '**AM. Start commands.** From `D:\\SDC\\LibraryLLM`: set `$env:ASSISTANT_ROUTER_MODE="existing_qwen"`; clear `$env:ASSISTANT_ROUTER_V2_VARIANT`; set `$env:ASSISTANT_ROUTER_V2_RETRY="0"`; run `.venv\\Scripts\\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005 --workers 1`. For explicit experiment only change mode to `router_v3` or `router_v3_shadow`. Existing dependencies: `backend.main:app` on 8002, `search.api:app` on 8003 and `recommendation.api:app` on 8004 using the same uvicorn command. Frontend: `npm run dev -- --host 127.0.0.1 --port 5173` from `frontend`.',
        '**AN. Production recommendation.** Keep `existing_qwen` active. Do not promote this classifier artifact. CPU discriminative routing is still the suitable concurrency direction, but this synthetic dataset/calibration does not meet correctness gates. No larger router or automatic fine-tuning is recommended or performed.',
        '**AO. Limitations.** Synthetic template/context distribution differs from natural TEST language; many training contexts have a single focus, while real trays may have none. Position generalization and some classes fail despite optimistic DEV calibration. Low empirical support causes LOANS/HISTORY and other classes to abstain. Criterion continuation, complex filters, pagination and content remain Qwen fallback. Source/head classification cannot extract novel entities or free-form criteria. Book-RAG/pending flags are supported inputs but current compact context does not supply all of them; authenticated HTTP remains authoritative. Performance samples are synthetic and routing-only; the approximately 744× figure uses one successful single-request GPU baseline and is not a stable production-capacity estimate. Shared HTTP handler tails remain slow during RAG. Live pass criteria check public intent, authoritative references, fields and explicit clarification; live free-text criterion meaning was not separately persisted/reviewed. Frozen strict evaluation includes semantic goals and a manual criterion review. Default batching remains off. Search health remains its pre-existing stale-index state. A Qwen timeout caused a temporary busy episode, and an observer/report-file transport error was recovered without model or threshold changes; original affected evidence is archived.']
    lines += ['\n## Frozen case results by category\n', '| Set | Category | Requests | Accepted | Accepted correct | Fallback | Hybrid correct |','|---|---|---:|---:|---:|---:|---:|']
    for name,selected in [('116',es),('121',hs)]:
        for category,c in selected['categories'].items():
            lines.append(f"| {name} | {category} | {c['requests']} | {c['accepted']} | {c['accepted_correct']} | {c['fallback']} | {c['hybrid_correct']} |")
    lines += ['\n## CPU concurrency\n','| Batching | Concurrent | Requests | Median ms | P95 ms | Requests/sec | Errors | Accepted | CPU % | Worker RSS MB |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for key in ['no_batching','micro_batching']:
        for n in ['1','5','10','20']:
            b=concurrency[key][n]
            lines.append(f"| {key} | {n} | {b['requests']} | {b['median_ms']:.1f} | {b['p95_ms']:.1f} | {b['throughput_per_sec']:.1f} | {b['errors']} | {b['accepted_routes']} | {b['cpu_percent_worker']:.1f} | {b['rss_mb_worker']:.1f} |")
    lines += ['\n## Live chains\n','| Chain | Message | Intent | Resolved public books | CPU accepted | Qwen calls | ms | Pass |','|---|---|---|---|---|---:|---:|---|']
    for c in live['chains']:
        for row in c['turns']:
            message=row['message'].replace('|','/')
            lines.append(f"| {c['name']} | {message} | {row['actual_intent']} | {', '.join(row['resolved_ids'])} | {row['classifier_accepted']} | {row['qwen_calls']} | {row['latency_ms']:.1f} | {row['pass']} |")
    lines += ['\n## Integrity and transport recovery\n',json.dumps(integrity,indent=2),
        'The initial timeout/stale-observer records are preserved in `assistant_router_v3_initial_transport_failure`. Final case reports retain initial valid responses, remeasure only transport failures/unfinished cases, and use request-local telemetry. No frozen TEST results changed weights, training examples or DEV thresholds. Each new evaluation request has at most one Qwen routing call.']
    (ROOT/'reports/assistant_router_v3_decision.md').write_text('\n\n'.join(lines).replace('\n\n|','\n|'),encoding='utf8')
    print(result,em['strict'],hm['strict'],'accepted',es['accepted_precision_percent'],hs['accepted_precision_percent'],flush=True)


if __name__=='__main__':main()
