"""Final A–AI decision and exact V5 file inventory. No routing/model calls."""
import json
from pathlib import Path
import sys
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from router_v5_evidence import write,digest

def read(name):return json.loads((ROOT/f'reports/assistant_router_v5_{name}.json').read_text(encoding='utf-8-sig'))
def fmt(value):return f'{value:.2f}%' if value is not None else 'unavailable'

def main():
    dev,sealed,old,concurrency,resources,live,reg,restored,safety,qwen,pressure,lock=[read(n) for n in [
        'dev','sealed_results','old_regression','concurrency','resources','live','regression','restored','safety_review','qwen_fallback','host_pressure','lock_isolation']]
    assert sealed['complete'] and old['complete'] and live['complete'] and restored['complete']
    assert restored['cached_encoder_hashes_unchanged'] and restored['frozen_runtime_hashes_unchanged']
    sm=sealed['metrics'];om={k:v['metrics'] for k,v in old['sets'].items()}
    baseline=read('baseline');manifest=json.loads((ROOT/'assistant/models/router_v5/manifest.json').read_text(encoding='utf8'))
    new=[]
    for folder in ['assistant','scripts','tests','evaluation','reports']:
        for path in (ROOT/folder).rglob('*'):
            relative=path.relative_to(ROOT).as_posix()
            if path.is_file() and 'router_v5' in relative and '__pycache__' not in relative and path.suffix not in {'.pyc','.pyo'} and relative not in baseline['frozen_files']:
                new.append(relative)
    modified={p:{'before':baseline['frozen_files'][p],'after':digest(ROOT/p)} for p in reg['changed_frozen_files']}
    inventory={'modified_existing':modified,'new_v5_files':{p:digest(ROOT/p) for p in sorted(new)},
               'source_files_modified':['assistant/api.py','assistant/profiling.py','assistant/semantic.py'],
               'runtime_artifact':'rag/private_documents/registry.sqlite: synthetic upload/delete, registry now empty',
               'note':'Inventory excludes Python caches and routine generated frontend dist/tsbuild outputs; these are not source changes. Report/decision inventory is generated before final decision write to avoid a circular self-hash.'}
    write('file_manifest',inventory)
    resources.update(live_worker_rss_observed_mb=842,live_worker_observation='Rounded psutil RSS for the sole live CPU worker, PID 3764, before the live matrix.',
        selected_cpu_benchmark=concurrency['micro_batching']['20'],
        host_live_min_available_mb=min(p['available_mb'] for p in pressure),
        host_live_max_commit_ratio=max(p['committed_bytes']/p['commit_limit_bytes'] for p in pressure),
        host_live_max_pages_input_per_sec=max(p['pages_input_per_sec'] for p in pressure),
        host_live_max_page_reads_per_sec=max(p['page_reads_per_sec'] for p in pressure),
        host_pressure_gate='FAIL: full-stack memory pressure/paging observed; CPU-worker RSS itself passes 1.3 GiB gate.',
        router_cuda_bytes=0,larger_generative_model_added=False,new_models_downloaded=False,
        stack_scope='One CPU router at a time; existing normal Search and RAG retain their own models. Search was stopped for offline evaluation, then restored for live tests.')
    write('resources',resources)
    def group(name):
        rows=[r for r in live['turns'] if r['group']==name]
        return f"{sum(r['pass'] for r in rows)}/{len(rows)}"
    def cats(rows):
        result={}
        for r in rows:
            key=r.get('context_kind',r.get('category','unknown'))
            out=result.setdefault(key,{'total':0,'correct':0,'accepted':0,'accepted_correct':0})
            out['total']+=1;out['correct']+=int(r['pass']);out['accepted']+=int(r['accepted']);out['accepted_correct']+=int(r['pass'] and r['accepted'])
        return result
    write('diagnostics',{'sealed_by_context':cats(sealed['cases']),'old_by_category':{k:cats(v['cases']) for k,v in old['sets'].items()},
                        'note':'Post-evaluation diagnosis only. No thresholds, exemplars, runtime or candidate weights changed.'})
    paired=qwen['paired_product_replay'];ablation=[]
    for method,entry in dev['ablations'].items():
        metrics=entry['metrics'];raw=entry['raw_top1']
        ablation.append(f"| {method} | {raw['correct']}/{raw['total']} ({100*raw['correct']/raw['total']:.2f}%) | {metrics['accepted']} | {fmt(metrics['accepted_precision_percent'])} | {fmt(metrics['coverage_percent'])} |")
    source_files=[p for p in sorted(new) if p.startswith(('assistant/router_v5/','scripts/','tests/','evaluation/','assistant/models/router_v5/'))]
    files='\n'.join(f'- `{p}`' for p in source_files)
    table='\n'.join(f"| {n} | {concurrency['no_batching'][str(n)]['p95_ms']:.2f} | {concurrency['micro_batching'][str(n)]['p95_ms']:.2f} |" for n in [1,5,10,20])
    doc=live['rag_coexistence']['document'];book=live['rag_coexistence']['book']
    report=f'''# LuminaR Router V5 — final decision

**FAIL. Do not promote V5, V4 or V3. `existing_qwen` is restored. Stop after this V5 evaluation.** No V6, classifier training, fine-tuning, larger Qwen or NLI download was started.

The small semantic registry is inspectable and CPU routing is fast. Its selective precision did not generalize and the shortlisted fallback is not reliable enough. Literal-span extraction still mistakes contextual phrases for book names. The full stack also experienced substantial host memory pressure.

## A–AI results

| Item | Final result |
|---|---|
| A. Status | **FAIL**: precision, coverage, hybrid, critical-context, fallback and fuzzy-title gates missed. |
| B. V4 lessons | CPU isolation, bounded queue, cancellation ownership, zero router CUDA, no admitted-route Qwen routing lock and shared HTTP transport preserved. V3/V4 evidence unchanged. |
| C. Binding | Structured arguments → reliable literal entities → selection → active previous comparison/recommendations → page → recent results/focus → extraction/clarification. Selection changes clear stale focus; explicit empty results do not revive it. |
| D. Registry | Definitions, five exemplars, negatives, existing intent mapping, source/argument requirements and confirmation flags. Separate positional/field/criterion banks. |
| E. Contracts | 29 action contracts. |
| F. Exemplars | Five per action, 145 total; auxiliary banks also five per label. No classification corpus/head fitting. |
| G. Retrieval | C: 0.70 max exemplar + 0.20 top-three exemplar mean + 0.10 definition cosine; per-action DEV-only score/margin gates. |
| H. CrossEncoder | Disabled in candidate. Full verifier improved raw DEV top-one matching but 20-way p95 was 1494.89 ms batched; compact form 1020.36 ms, both above hard gate. |
| I. Worker RSS | {resources['worker']['rss_mb']:.2f} MiB after initialization; selected benchmark 20-way RSS {concurrency['micro_batching']['20']['rss_mb']:.2f} MiB. Below 1.3 GiB. |
| J. DEV ablations | A/B/C/D and compact-D same 244-case DEV; details below. E hybrid {read('dev_hybrid')['metrics']['hybrid_correct']}/244 = {fmt(read('dev_hybrid')['metrics']['hybrid_accuracy_percent'])}. |
| K. Sealed precision | {sm['accepted_correct']}/{sm['accepted']} = **{fmt(sm['accepted_precision_percent'])}**, below 97%. |
| L. Sealed coverage | {sm['accepted']}/168 = **{fmt(sm['coverage_percent'])}**, below 60% target. |
| M. Sealed hybrid | {sm['hybrid_correct']}/168 = **{fmt(sm['hybrid_accuracy_percent'])}**, below 90%. |
| N. Critical context | {sm['critical_correct']}/{sm['critical_total']} = **{fmt(sm['critical_accuracy_percent'])}**, below 95%. |
| O. Old 116/121 | Strict hybrid {om['116']['hybrid_correct']}/116 = {fmt(om['116']['hybrid_accuracy_percent'])}; {om['121']['hybrid_correct']}/121 = {fmt(om['121']['hybrid_accuracy_percent'])}. These are exposed regression sets. |
| P. Account live | {group('account')}. Current loans/fees/reservations pass; recently-borrowed history fails. |
| Q. Comparison live | {group('comparison')}. General contrasts pass; preference ambiguity and rating comparison fail strict checks. |
| R. Previous context | {group('previous')}; all three natural follow-ups fail. |
| S. Page | {group('page')}; availability passes, author/related queries fail. |
| T. Discovery | {group('discovery')}; vampires Search fails, joint recommendation and related-book request pass. |
| U. Fuzzy titles | **5** bad contextual entity spans in sealed parse; **9** actual unwanted contextual title-resolution calls in old regression (3/6). Zero gate fails. |
| V. Unrelated Search | New sealed parse: zero fresh Search action mistakes. Old product fixtures: **9** unrelated Search calls through bad title resolution (3/6). Zero gate fails. |
| W. Fallback | {sm['fallback_count']}/168 = **{fmt(sm['fallback_rate_percent'])}**, above 40% target. |
| X. Shortlisted Qwen | Sealed fallback {sm['fallback_count'] and sm['hybrid_correct']-sm['accepted_correct']}/{sm['fallback_count']} = {fmt(sm['fallback_accuracy_percent'])}. Paired DEV product replay: {paired['shortlist_correct']}/{paired['total']} shortlisted vs {paired['full_qwen_correct']}/{paired['total']} full existing-Qwen; insufficient despite improvement in that sample. |
| Y. Qwen/100 | {sm['qwen_calls_per_100']:.2f} actual routing generations per 100 sealed requests. At most one routing generation, no retry. Generative RAG/prose remains separate. |
| Z. Concurrency | CPU scorer p95 1/5/10/20: 35.64/77.66/144.29/209.18 ms with selected 5 ms batching. Routing throughput only. |
| AA. Mixed load | {live['mixed_20']['accepted']} admitted, {live['mixed_20']['fallback']} fallback, {live['mixed_20']['busy']} busy, {live['mixed_20']['semantic_correct']}/20 semantically correct; end-to-end p95 {live['mixed_20']['p95_ms']:.2f} ms. Two real accounts, twenty conversations. |
| AB. CPU/RAM/GPU | Two worker CPU threads (~201% two-core usage in benchmark), router CUDA 0. Full-stack host available RAM fell to {resources['host_live_min_available_mb']} MiB; commit reached {100*resources['host_live_max_commit_ratio']:.2f}% and paging peaked at {resources['host_live_max_pages_input_per_sec']} pages/s. Memory-pressure gate fails. |
| AC. HTTP transport | Preserved single installation/lifespan AsyncClient, 40 max/20 keepalive, request bearer isolation. Regression passes. |
| AD. Tests | {reg['backend_passed']} backend passes, {reg['backend_skipped']} skips; {reg['frontend_passed']} frontend passes. 43 new V5 unit/executor checks. No test failures after fixture-separated runs. |
| AE. Build/lint | Build passes. Lint zero errors, 19 existing warnings. |
| AF. Exact files | Three existing source edits: `assistant/api.py`, `assistant/profiling.py`, `assistant/semantic.py`; new sources/data/artifacts listed below and every report/log/hash in `assistant_router_v5_file_manifest.json`. Empty private-document SQLite registry changed during synthetic upload/delete. |
| AG. Commands | Normal local start and experiment commands below. Current five services are running with default gateway restored. |
| AH. Production | Keep `existing_qwen`; preserve this rejected experiment as evidence. Do not deploy V5 or automatically start another model/router experiment. |
| AI. Limits | Small per-contract DEV support; manual author overlaps contract author; modest previous/changed/recommendation/short strata; field/position scoring weak; literal-span entity proof inadequate; legacy reading-list confirmation gap; two physical test accounts; host paging. |

## DEV comparison

Raw top-one accuracy is action-label matching, not accepted-route correctness. Admission additionally checks complete goal/identity/field/criterion/confirmation semantics. Thresholds use only DEV with at least four admitted support cases and 99% empirical precision; small support is not a statistical confidence guarantee.

| Method | Raw top-one action | Admitted | Admitted precision | Coverage |
|---|---|---|---|---|
{chr(10).join(ablation)}

E uses the chosen C thresholds unchanged: 50/50 admitted correctly, 20.49% coverage, 133/244 strict hybrid correctness, 79.51% fallback. Full-Qwen paired controls were stratified, at most two per contract, capped at forty. Prompt input averages were 560.95 versus 900.43 tokens. Original raw parser-only control scores are retained but are not a fair product comparison because existing Qwen leaves some IDs/goal tags to the executor. The paired product replay uses the same cached decisions with complete in-memory API fixtures and strict comparison goals. No additional model calls or threshold changes were made for that replay.

Position DEV binding accuracy: definition-only 63/94; safe structural defaults 74/94; tiny exemplar/definition scorer 62/94. Structural defaults cannot resolve general ordinals/OTHER. The selected path uses calibrated positional scoring, structural defaults where safe and fallback otherwise; it still fails natural-language conversational position quality.

## Frozen evaluation provenance

The registry meanings were frozen before pack authoring; 168 cases were sealed before the separate 244-case DEV pack existed; thresholds were fixed before the candidate seal. The sealed evaluation ran once, then the old sets ran without adjustment. Candidate/runtime/cache hashes remain unchanged.

Sealed SHA-256: `{manifest['sealed_sha256']}`.

Sources: 153 manually authored cases plus 15 reviewed offline existing-Qwen cases; rejected malformed/ambiguous/invented-title generations are retained. There are 160 no-focus and eight focused cases. Contexts: no context 59, page 45, selection 30, document four, authorized book four, current results eight, previous five, selection change five, recommendation three, four-book selection two, previous-focus one, one-book selection one and explicit empty result one. Seventeen turns have fewer than six words. These last conversational strata are modest and some transformations share a message. This is hash-sealed evidence, not perfectly independent human research.

New sealed scoring is parse-level and checks exact action, goal, IDs, supported fields, criterion presence/span, confirmation flag and continuation/filter arguments. It does not prove tool execution correctness. Old regression and live checks exercise the unchanged executor. Five new sealed entity failures would request inappropriate title resolution; nine old fixture cases actually do so and invoke unrelated Search. Underspecified refinement labels are retained as strict failures rather than changed after sealing.

## CPU and live concurrency

| Concurrency | Unbatched scorer p95 ms | 5 ms micro-batch p95 ms |
|---|---|---|
{table}

The held QwenGateway mutex test admitted 20/20 requests correctly, with zero routing lock acquisitions or generation and p95 {lock['p95_ms']:.2f} ms. It uses an injected model that forbids generation, so no duplicate GPU stack is loaded. Real GPU coexistence is measured separately below.

Live isolated comparison probes: 20/20 correct, no cross-user book references, 20 admitted. Full-response p95 was {live['isolation_20']['p95_ms']:.2f} ms; scorer p95 was approximately 117.68 ms. These repeat a DEV-admitted sentence to measure admission/load, and are not twenty independent natural-language successes or twenty physical user accounts. Core/auth/metadata transport plus host pressure make end-to-end time larger than pure scoring. Mixed load repeats some admitted probes and reports real semantic correctness, fallback and busy counts; it is not overall product capacity.

Document upload 200; cross-user ask 404; document answer 200; Book RAG answer 200. Twenty admitted account queries alongside each RAG request had server p95 {doc['server_p95_ms']:.2f} ms / {book['server_p95_ms']:.2f} ms. The synthetic document was deleted, and the restored registry/directory counts are both zero. Private data, tokens, emails and private chunks are not persisted in V5 evidence.

The cached [CrossEncoder L6 publisher model card](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2) specifies Apache-2.0 and MS MARCO relevance training, not entailment verification. No NLI model was downloaded. An unmeasured NLI model is not recommended automatically: measured full-stack paging and already-failed semantic/latency evidence do not establish that another model would meet this task's gates.

## Confirmation and restoration

Borrow, return and reserve were tested with write spies and mutations enabled: no execution before confirmation. The existing security/confirmation suite passes. Reading-list add/remove are different: the unchanged legacy executor writes immediately and ignores the V5 confirmation flag. Cached-decision replay demonstrates that gap in memory; no real reading-list mutation is requested by the live matrix. This prevents claiming universal mutation safety from a parser flag. Clear still requires its existing explicit UI action.

All five service readiness endpoints return 200 (Recommendation uses `/`, not `/health`). The restored typed comparison passes and both smoke profiles have no V5 telemetry. The restored natural page-availability query clarifies instead of answering; that existing-Qwen limitation is recorded and not repaired in this stopped experiment. A transient stale Windows LISTEN row initially blocked restart after the old process had stopped; the helper now waits for socket release and refuses duplicate services.

## Exact new source, evaluation and artifact files

Existing source edits are only the three listed under AF. All other baseline sources/models/datasets/reports remain byte-identical. The sole runtime-data difference is the cleaned private-document registry. The machine-readable file manifest includes all new report/log/evidence hashes as well as these files:

{files}

## Start/reproduction commands

Services are already running. From a stopped normal stack, use `D:\\SDC\\LibraryLLM` as working directory:

```powershell
.venv\\Scripts\\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
.venv\\Scripts\\python.exe -m uvicorn search.api:app --host 127.0.0.1 --port 8003
.venv\\Scripts\\python.exe -m uvicorn recommendation.api:app --host 127.0.0.1 --port 8004
$env:ASSISTANT_ROUTER_MODE='existing_qwen'
.venv\\Scripts\\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005
```

Run `npm run dev -- --host 127.0.0.1 --port 5173` from the frontend directory. Hidden, duplicate-checked service helpers are `scripts/serve_router_v5.ps1 -Mode dependencies`, `-Mode experimental-rag` and `-Mode restore-rag`. The experimental mode is preserved for review, not recommended for production. The sealed runner command was `.venv\\Scripts\\python.exe scripts/evaluate_router_v5.py --sealed-once`; its exclusive marker prevents a second evaluation. Do not clear that marker to retune or rerun this pack.

**Stop condition reached: V5 evaluated and rejected, default restored, no automatic follow-on experiment.**
'''
    (ROOT/'reports/assistant_router_v5_decision.md').write_text(report,encoding='utf8')
    write('completion',{'status':'FAIL','finished_at':datetime.now(timezone.utc).isoformat(),'sealed_metrics':sm,
        'default_mode':'existing_qwen','default_restored':True,'promoted':False,'stop_condition_reached':True,
        'runtime_unchanged_after_seal':True,'v3_v4_preserved':reg['v3_v4_unchanged'],'no_follow_on_experiment':True})
    # Final inventory must reflect resources/diagnostics/decision/completion
    # written above. Exclude only the manifest's own circular content hash.
    final_files=[]
    for folder in ['assistant','scripts','tests','evaluation','reports']:
        for path in (ROOT/folder).rglob('*'):
            relative=path.relative_to(ROOT).as_posix()
            if path.is_file() and 'router_v5' in relative and '__pycache__' not in relative and path.suffix not in {'.pyc','.pyo'} and relative not in baseline['frozen_files']:
                final_files.append(relative)
    inventory['new_v5_files']={p:digest(ROOT/p) for p in sorted(final_files) if p!='reports/assistant_router_v5_file_manifest.json'}
    inventory['self_path']='reports/assistant_router_v5_file_manifest.json'
    inventory['note']='Complete final V5 inventory excludes Python caches and routine generated frontend dist/tsbuild outputs. Only this inventory itself is excluded from its circular content hash.'
    write('file_manifest',inventory)
    print('FINAL V5 FAIL REPORT COMPLETE',flush=True)

if __name__=='__main__':main()
