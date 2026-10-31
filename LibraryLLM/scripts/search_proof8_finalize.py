"""Close the standalone local experiment without claiming an incomplete cohort passed."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib, json, math, statistics, subprocess
import psutil

R = Path('reports')
REQUIRED = '''CURRENT_AVAILABLE_RAM CURRENT_AVAILABLE_VRAM MODEL_RESOURCE_GATE MODEL_WORKER_MEMORY_CAP MEMORY_RESERVE_PRESERVED MODEL_LOADING_SUCCESS MODEL_LOADING_DURATION LEARNED_PREDICTIONS_CAPTURED LEARNED_TYPED_ACCURACY LEARNED_EXECUTION_ACCURACY LEARNED_FALSE_EXECUTION LEARNED_MISSED_EXECUTION LEARNED_MANDATORY_OMISSIONS MODEL_PEAK_RAM MODEL_PEAK_VRAM MODEL_INFERENCE_P50 MODEL_INFERENCE_P95 DETERMINISTIC_BASELINE_COMPARISON SELECTED_ARCHITECTURE FRESH_INDEPENDENT_ACCEPTANCE PRODUCTION_READINESS REMAINING_BLOCKERS'''.split()


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(name, obj):
    with (R / ('search_proof8_' + name + '.json')).open('x', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def verify(files):
    failures = [p for p, expected in files.items() if not Path(p).is_file() or sha(p) != expected]
    return dict(entries=len(files), verified=not failures, failures=failures)


def rate(n, d):
    return dict(numerator=n, denominator=d, percent=100*n/d if d else None,
                status='OBSERVED_DEVELOPMENT_ONLY' if d else 'NOT_MEASURED_NO_APPLICABLE_OUTPUT')


def main():
    result = load(R/'search_proof8a3_comparison_results.json')
    caps = [load(R/(prefix+'model_capture.json')) for prefix in
            ['search_proof8_', 'search_proof8a2_', 'search_proof8a3_']]
    cfg = load(R/'search_proof8a3_configuration.json')
    serial = [x for x in caps[-1]['records'] if x.get('event') == 'prediction' and x.get('phase') == 'serial']
    ids = {x['id'] for x in serial}
    annotations = [x for x in result['annotation_records'] if x['id'] in ids]
    observed = [x for x in result['records'] if x['id'] in ids]
    mandatory = [x for x in annotations if x['mandatory_comparable']]
    spans = [x for x in result['predicted_span_records'] if x['id'] in ids]
    dimensions = {}
    for key in ['domain', 'operator', 'operand', 'role', 'modality', 'polarity', 'state', 'exact_source_span']:
        vals = [x['dimensions'][key] for x in annotations if key in x['dimensions']]
        dimensions[key] = rate(sum(vals), len(vals))
    observed_summaries = {}
    for name in ['deterministic', 'restricted', 'learned_proof']:
        typed = [x for x in observed if x['oracle']['decision'] is not None]
        blocked = [x for x in observed if x['oracle']['executable'] is False]
        valid = [x for x in observed if x['oracle']['executable'] is True]
        observed_summaries[name] = {
            'typed': rate(sum(x['candidates'][name]['typed_correct'] for x in typed), len(typed)),
            'execution': rate(sum(x['candidates'][name]['execution_correct'] for x in observed), len(observed)),
            'false_execution': rate(sum(x['candidates'][name]['executable'] for x in blocked), len(blocked)),
            'missed_valid': rate(sum(not x['candidates'][name]['executable'] for x in valid), len(valid))}
    samples = caps[-1]['process_tree_samples']
    gaps = [{'from_ms': a['elapsed_ms'], 'to_ms': b['elapsed_ms'], 'gap_ms': b['elapsed_ms']-a['elapsed_ms']}
            for a, b in zip(samples, samples[1:]) if b['elapsed_ms']-a['elapsed_ms'] > 3000]
    # The first runner CPU sample divides already-accrued startup CPU by an almost
    # zero interval. Preserve it in raw evidence; exclude it from derived peaks.
    cpu_peak = max(x['CPU_core_percent'] for x in samples[1:])
    processes = []
    for p in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline']):
        try:
            args = p.info['cmdline'] or []
            processes.append(dict(pid=p.pid, name=p.info['name'], RSS_bytes=p.info['memory_info'].rss,
                                  script_hint=next((Path(s).name for s in args if s.endswith('.py')), None),
                                  experiment_worker=any('search_proof8' in s and 'model_worker' in s for s in args)))
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            pass
    memory = psutil.virtual_memory()
    gpu_line = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.total,memory.free,memory.used,utilization.gpu',
                                        '--format=csv,noheader,nounits'], text=True).strip()
    total, free, used, util = map(float, gpu_line.split(','))
    gpu = dict(total_bytes=int(total*1024**2), free_bytes=int(free*1024**2), used_bytes=int(used*1024**2), utilization_percent=util)
    required_ram = cfg['worker_tree_memory_cap_bytes']+cfg['platform_RAM_reserve_bytes']+cfg['startup_margin_bytes']
    gate = dict(at_utc=datetime.now(timezone.utc).isoformat(), RAM=memory._asdict(), GPU=gpu,
                required_RAM_for_frozen_retry_bytes=required_ram,
                RAM_retry_gate='PASS' if memory.available >= required_ram else 'BLOCKED_CURRENT_HEADROOM',
                observed_loader_tree_peak_bytes=caps[-1]['peak_worker_tree_RSS_bytes'],
                observed_peak_plus_reserve_and_margin_bytes=caps[-1]['peak_worker_tree_RSS_bytes']+cfg['platform_RAM_reserve_bytes']+cfg['startup_margin_bytes'],
                experiment_workers_remaining=[p for p in processes if p['experiment_worker']],
                top_process_memory=sorted(processes, key=lambda p:p['RSS_bytes'], reverse=True)[:12],
                application_process_inventory=[p for p in processes if 'python' in p['name'].lower() or p['script_hint']],
                other_services_terminated=0, implicit_CPU_or_quantized_fallback=False)
    assert not gate['experiment_workers_remaining'], gate['experiment_workers_remaining']
    save('resume_resource_gate', gate)
    supplementary = dict(
        scope='2 observed outputs, not the 18-query intended cohort', observed_ids=sorted(ids),
        output_coverage=rate(len(serial), 18), observed_pipeline_metrics=observed_summaries,
        observed_annotation_dimensions=dimensions,
        predicted_source_substrings_valid=rate(sum(x['valid'] for x in spans), len(spans)),
        mandatory_units_omitted_or_changed=rate(sum(x['mandatory_omitted_or_changed'] for x in mandatory), len(mandatory)),
        contexts_with_mandatory_omission=rate(len({x['id'] for x in mandatory if x['mandatory_omitted_or_changed']}), len({x['id'] for x in mandatory})),
        schema_source_valid=rate(sum(x.get('schema_source_valid', False) for x in serial), len(serial)),
        JSON_object_outputs=rate(sum(x['model_JSON_object'] for x in observed), len(observed)),
        relationship_accuracy=rate(0, 0), negative_polarity_accuracy=rate(0, 0),
        hard_invention='NOT_FULLY_MEASURED: no complete absence oracle; no accepted hard filters because both outputs were rejected',
        completed_output_timeouts=rate(sum(x['status']=='TIMEOUT_SAFE_REJECTION' for x in serial), len(serial)),
        started_queries=3, completed_queries=2, parent_hard_timeout_queries=1,
        unstarted_queries=15, missing_output_queries=16,
        telemetry_gaps=gaps, interruption_cause='Unconfirmed; simultaneous CPU/GPU sampling gap, not evidence of continuous inference for that interval',
        CPU_peak_core_percent_corrected=cpu_peak, CPU_peak_host_percent_corrected=cpu_peak/(psutil.cpu_count() or 1),
        inherited_scoring_caveats=[
            'a3 comparison_results raw annotation omissions include absent outputs over all 18. Use this supplementary observed-only view for model quality.',
            'a3 comparison_results full-cohort learned metrics include 16 synthesized safe-clarification outcomes. They are workflow behavior, not 18 learned predictions.',
            'a3 comparison_results CPU peak includes an invalid first-sample interval. Use corrected peak excluding the initial sample.',
            'Attempts1/2 token-budget audit counted BatchEncoding keys (2), not tokens. Attempt3 fixes token count using input_ids.shape[-1].',
            'Per-dimension raw alignment uses source-span IoU and may misalign incorrect offsets; exact source/schema rejection remains authoritative.',
            'Warm latency has one completed observation; no throughput/concurrency/queue qualification.'])
    save('observed_only_analysis', supplementary)
    perf = result['performance']
    attempts = [dict(attempt=i+1, status=c['status'], loaded=any(x.get('event')=='loaded' for x in c['records']),
                     predictions=c['model_calls'], peak_tree_RAM_bytes=c['peak_worker_tree_RSS_bytes'],
                     minimum_available_RAM_bytes=c['minimum_available_RAM_bytes']) for i,c in enumerate(caps)]
    min_ram = min(c['minimum_available_RAM_bytes'] for c in caps)
    qa = {
        'CURRENT_AVAILABLE_RAM': dict(bytes=memory.available, resource_gate_artifact='reports/search_proof8_resume_resource_gate.json'),
        'CURRENT_AVAILABLE_VRAM': dict(bytes=gpu['free_bytes'], total_bytes=gpu['total_bytes']),
        'MODEL_RESOURCE_GATE': dict(initialization='SUCCEEDED_ATTEMPT3', latest_retry=gate['RAM_retry_gate'], required_RAM_bytes=required_ram, attempts=attempts),
        'MODEL_WORKER_MEMORY_CAP': dict(attempt3_RAM_bytes=cfg['worker_tree_memory_cap_bytes'], CUDA_allocator_bytes=cfg['gpu_memory_cap_bytes'], polling='100ms tree RSS / 500ms global GPU; transient overshoot possible'),
        'MEMORY_RESERVE_PRESERVED': dict(during_measured_attempts=min_ram >= cfg['platform_RAM_reserve_bytes'], minimum_available_RAM_bytes=min_ram, RAM_reserve_bytes=cfg['platform_RAM_reserve_bytes'], startup_margin_bytes=cfg['startup_margin_bytes'], attempt3_GPU_free_min_bytes=perf['global_GPU_minimum_free_bytes'], GPU_reserve_bytes=cfg['GPU_reserve_bytes']),
        'MODEL_LOADING_SUCCESS': dict(success=True, successful_attempts=1, attempts=3, actual_predictions=True),
        'MODEL_LOADING_DURATION': dict(worker_ms=perf['worker_load_event']['cold_process_startup_ms'], parent_ms=perf['cold_parent_spawn_to_loaded_ms'], observations=1, note='Cold process; OS file cache may be warm'),
        'LEARNED_PREDICTIONS_CAPTURED': dict(serial=2, planned=18, repeated_concurrency_probes=0, missing=16, scope='EXPOSED_DEVELOPMENT'),
        'LEARNED_TYPED_ACCURACY': dict(observed=observed_summaries['learned_proof']['typed'], full_workflow=result['summaries']['learned_proof']['typed'], caveat='Both observed outputs schema-rejected; full workflow substitutes clarification for 16 missing outputs; no raw six-class learned decision score'),
        'LEARNED_EXECUTION_ACCURACY': dict(observed=observed_summaries['learned_proof']['execution'], full_workflow=result['summaries']['learned_proof']['execution']),
        'LEARNED_FALSE_EXECUTION': dict(observed=observed_summaries['learned_proof']['false_execution'], full_workflow=result['summaries']['learned_proof']['false_execution'], caveat='No blocked-oracle query received a model prediction'),
        'LEARNED_MISSED_EXECUTION': dict(observed=observed_summaries['learned_proof']['missed_valid'], full_workflow=result['summaries']['learned_proof']['missed_valid']),
        'LEARNED_MANDATORY_OMISSIONS': supplementary['mandatory_units_omitted_or_changed'],
        'MODEL_PEAK_RAM': dict(attempt3_tree_bytes=perf['peak_process_tree_RAM_bytes'], all_attempts_peak_bytes=max(c['peak_worker_tree_RSS_bytes'] for c in caps)),
        'MODEL_PEAK_VRAM': {k:perf[k] for k in ['peak_model_CUDA_allocated_bytes','peak_model_CUDA_reserved_bytes','global_GPU_peak_used_bytes','global_GPU_minimum_free_bytes']},
        'MODEL_INFERENCE_P50': dict(serial_ms=perf['serial_inference_generation']['p50_ms'], serial_n=2, warm_ms=perf['warm_generation_excluding_first']['p50_ms'], warm_n=1, representative=False),
        'MODEL_INFERENCE_P95': dict(serial_ms=perf['serial_inference_generation']['p95_ms'], serial_n=2, warm_ms=perf['warm_generation_excluding_first']['p95_ms'], warm_n=1, representative=False),
        'DETERMINISTIC_BASELINE_COMPARISON': dict(control='Frozen7r1; standaloneV8 adds no new semantic contract', full_development=result['summaries'], observed_common_subset=observed_summaries),
        'SELECTED_ARCHITECTURE': 'Retain frozen7r1 deterministic proof pipeline for continued disabled development; Qwen not selected. Neither pipeline production-qualified by this experiment.',
        'FRESH_INDEPENDENT_ACCEPTANCE': dict(performed=False, count=0, reason='Exposed development data only; incomplete learned capture; separate baseV8 prompt deferred by user'),
        'PRODUCTION_READINESS': 'BLOCKED; no activation, application integration, deployment or Mongo qualification',
        'REMAINING_BLOCKERS': ['Insufficient current RAM for guarded retry', '16/18 model outputs missing after simultaneous telemetry gap and query hard timeout', '0/2 observed outputs satisfy schema/source contract', 'No complete serial or bounded concurrent throughput/queue measurement', 'No measured relationship/negation behavior in observed subset', 'No fresh independent acceptance; two pilot typed notice subtypes unresolved', 'Separate baseV8 semantic/qualification requirements awaiting user prompt', 'Native database/JWT integration unqualified under no-Mongo-writes constraint', 'Cached model research license does not qualify commercial production deployment'],
        'OPERATIONAL_FEASIBILITY': dict(serial_throughput=None, bounded_concurrent_throughput=None, queue_latency=None, status='NOT_MEASURED_INTERRUPTED', CPU_seconds=perf['worker_CPU_seconds'], CPU_peak_core_percent=cpu_peak, GPU_peak_utilization_percent=perf['global_GPU_peak_utilization_percent'], GPU_mean_utilization_percent=perf['global_GPU_mean_utilization_percent'], note='Sampled GPU metrics global; gap excludes inference and contention conclusions'),
        'RAW_EXTRACTION_METRICS': supplementary,
        'REGRESSION': dict(passed=1705, deselected_reviewed_legacy_nodes=6, evidence='reports/search_proof8_readiness_tests.xml', repeated=False),
        'SCOPE': 'Standalone V8 extra authorization; base prompt explicitly deferred by user',
        'SAFETY': dict(disabled=True, Mongo_writes=0, model_downloads=0, remote_inferences=0, training=False, private_data=False, production_activation=False, other_services_terminated=0),
    }
    assert all(k in qa for k in REQUIRED)
    save('final_qa', qa)
    pre = load(R/'search_proof8_preflight.json')
    model = load(R/'search_proof7_model_audit_verified.json')
    preservation = dict(at_utc=datetime.now(timezone.utc).isoformat(),
                        previous=verify(pre['protected_files']),
                        attempt_source_freezes={p.name:verify(load(p)['files']) for p in R.glob('search_proof8*comparison_freeze.json')},
                        cached_model=verify({str(Path(model['path'])/p):m['sha256'] for p,m in model['files'].items()}),
                        tracked_diff=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines(),
                        staged_diff=subprocess.check_output(['git','diff','--cached','--name-only'],text=True).splitlines(),
                        own_workers_remaining=gate['experiment_workers_remaining'], Mongo_writes=0, production_activation=False)
    assert preservation['previous']['verified'] and preservation['cached_model']['verified']
    assert all(x['verified'] for x in preservation['attempt_source_freezes'].values())
    assert not preservation['tracked_diff'] and not preservation['staged_diff']
    save('preservation', preservation)
    report = f'''# Standalone V8 local learned-extractor experiment

The cached Qwen2.5-3B-Instruct model **loaded successfully** on attempt3 using installed Accelerate per-shard BF16 dispatch. Two real DEVELOPMENT outputs were captured; both failed schema/source validation. The comparison remains **incomplete and unqualified**. Retain the frozen7r1 deterministic proof architecture for continued disabled development. Production readiness is **BLOCKED**.

## Scope and evidence

The user clarified that this addendum is standalone and that a separate prompt will follow. No unseen baseV8 semantic requirements were assumed. Frozen7r1 is the deterministic control, carried forward without semantic edits. Candidate `search-smarteng-disabled-proof-8-local` is disabled. Pinned Qwen revision `{cfg['revision']}`, nine cached files, runtime versions, prompt, ontology, schema, proof, source, scorer and population were frozen before capture in `search_proof8a3_comparison_freeze.json` and `search_proof8a3_configuration.json`. No downloads or training occurred.

## Measured attempts and resource gate

| Attempt | Result | Tree RAM peak | Model outputs |
|---|---|---:|---:|
| 1 | {attempts[0]['status']} | {attempts[0]['peak_tree_RAM_bytes']:,} bytes | 0 |
| 2 | {attempts[1]['status']} | {attempts[1]['peak_tree_RAM_bytes']:,} bytes | 0 |
| 3 | {attempts[2]['status']} after successful load | {attempts[2]['peak_tree_RAM_bytes']:,} bytes | 2 |

Attempt1 used a4GiB RAM cap; attempt2 used5.75GiB with sequential Transformers loading. The installed loader retained mmap handles for both shards. Attempt3 used installed Accelerate1.14.0 meta initialization and per-shard GPU dispatch of the same unmodified BF16 weights within the5.75GiB cap. No quantization or weight conversion was required. bitsandbytes was installed and inventoried; other quantization backends listed in the inventory were absent.

Attempt3 loaded in {perf['worker_load_event']['cold_process_startup_ms']/1000:.3f}s worker time ({perf['cold_parent_spawn_to_loaded_ms']/1000:.3f}s parent-to-loaded). CPU tree RAM peak was {perf['peak_process_tree_RAM_bytes']:,} bytes. CUDA allocated peak was {perf['peak_model_CUDA_allocated_bytes']:,}, reserved peak {perf['peak_model_CUDA_reserved_bytes']:,}; global GPU peak usage was {perf['global_GPU_peak_used_bytes']:,} bytes. Its minimum free VRAM was {perf['global_GPU_minimum_free_bytes']:,} bytes, above the1GiB reserve. Minimum available RAM across all attempts was {min_ram:,} bytes, above the2GiB reserve. Guards permit transient overshoot; they are sampled controls, not OS quotas. Two earlier attempts were terminated for crossing their caps and preserved.

The third query started but had no output. CPU telemetry contains a {gaps[0]['gap_ms']/1000:.3f}s gap, also visible in GPU telemetry; the parent stopped the worker for query hard timeout upon resuming. The gap's cause is unconfirmed. It must not be interpreted as continuous model computation or a representative latency result. All owned worker processes were cleaned up. No other application was terminated.

The final retry audit measured **{memory.available:,} bytes available RAM** and **{gpu['free_bytes']:,} bytes available VRAM**. The frozen RAM gate requires {required_ram:,} bytes (5.75GiB cap +2GiB reserve +0.5GiB margin). Current gate: **{gate['RAM_retry_gate']}**. Even the observed loader peak plus reserve/margin requires {gate['observed_peak_plus_reserve_and_margin_bytes']:,} bytes. No further worker was launched. Top process memory and Python/application role hints are preserved in `search_proof8_resume_resource_gate.json`; no large RAG process was identified from those hints, and live RAG concurrency was not exercised.

## Semantic comparison and denominator limits

| Pipeline | Typed on intended cohort | Execution | False execution | Missed valid |
|---|---:|---:|---:|---:|
| Frozen deterministic control | 16/16 | 18/18 | 0/8 | 0/10 |
| Restricted-language fallback | 0/16 | 8/18 | 0/8 | 10/10 |
| Learned proof workflow, including16 missing-output clarifications | 0/16 | 8/18 | 0/8 | 10/10 |

The last row is guarded workflow behavior, **not18 learned predictions**. Only queries01/02 have real model outputs. On this common observed subset, deterministic scored2/2 typed and2/2 execution; learned proof scored0/2 and0/2, missed2/2 valid executions, and has **no observed blocked-query denominator** for false execution. Both outputs were JSON objects (2/2) but schema/source-valid0/2, so neither reached proof compilation or authorized execution. Schema validation is the first gate of the same deterministic proof pipeline; it is never bypassed to manufacture a proof result. No model search, database query, scope choice or tool call occurred.

The model confused canonical domains with role names, used invalid role/polarity enums, stringified numeric operands, lost strict year comparison, and emitted incorrect character offsets. Predicted exact source substrings were {supplementary['predicted_source_substrings_valid']['numerator']}/{supplementary['predicted_source_substrings_valid']['denominator']} valid. Agreed mandatory units omitted or changed: {supplementary['mandatory_units_omitted_or_changed']['numerator']}/{supplementary['mandatory_units_omitted_or_changed']['denominator']} across the two observed contexts. Raw per-dimension source-span/domain/operator/operand/modality/polarity/state scores are in `search_proof8_observed_only_analysis.json`; its observed-only denominators supersede all18 annotation counts for statements about raw model quality. Invalid offsets make IoU alignment diagnostic rather than authoritative semantic matching. Relationship and negative-query accuracy are unmeasured (0 applicable observed outputs). There is no complete invention oracle; zero accepted hard filters is not a claim of zero raw invention.

The18 queries were independently authored/reviewed before exposure and are now exposed DEVELOPMENT data. Two notice subtypes remain unscored for typed accuracy. This is not fresh acceptance, and no fresh acceptance was attempted. Native scalar control agreement is29/29 on this small selected population; this does not establish generalization or live database correctness.

## Operational measurements

Two completed generation durations were {serial[0]['generation_ms']/1000:.3f}s and {serial[1]['generation_ms']/1000:.3f}s. Their descriptive p50 is {perf['serial_inference_generation']['p50_ms']/1000:.3f}s and p95 is {perf['serial_inference_generation']['p95_ms']/1000:.3f}s (n=2). Warm excluding first is {perf['warm_generation_excluding_first']['p50_ms']/1000:.3f}s (n=1); p95 at n=1 is merely that same observation, not tail-latency qualification. No serial-complete or two-caller-complete event exists. Serial/concurrent throughput and queue latency are **not measured**. The harness was configured for one model with two queued callers after the serial phase; that probe never ran.

Worker CPU time was {perf['worker_CPU_seconds']:.3f}s. Corrected peak sampled CPU use is {cpu_peak:.2f}% of one core; the initial sample is excluded because it divides startup CPU by an almost-zero interval. Global GPU peak sampled utilization was {perf['global_GPU_peak_utilization_percent']:.0f}%; global mean {perf['global_GPU_mean_utilization_percent']:.2f}% is gap-biased and does not establish model utilization or RAG contention. One of3 started queries was parent-aborted after the telemetry gap; neither of the2 completed outputs timed out. Sixteen planned outputs remain absent (1 started,15 unstarted). Attempts1/2 token-budget audit mistakenly counted BatchEncoding keys; attempt3 corrected it and measured943–965 input tokens, all below4096. Earlier evidence was preserved.

## Regression, preservation and next requirement

The reviewed regression ran1705 passing tests with6 disclosed legacy contract nodes deselected under the unchanged independently reviewed migration (`search_proof8_readiness_tests.xml`). The frozen semantic control was not changed. Historical evidence ({preservation['previous']['entries']} protected entries), all three source freezes and all nine cached model files were rehashed successfully. Tracked/staged diffs are empty. All new evidence is retained, including rejected outputs and interrupted runs. No production/parser/C4/EXACT/auth/library isolation mutation, Mongo write, index rebuild, deployment, remote inference or institutional data use occurred. Native database/JWT qualification remains limited by the no-writes constraint. The model's previously audited research license does not establish commercial deployment permission.

The experiment established a successful guarded loading path and captured actual failures. It did **not** complete the18-query learned comparison or operational qualification. Next work requires sufficient current RAM for the guarded full capture, schema/ontology extraction repair under a newly frozen development configuration, complete serial/two-caller measurements, and the separate baseV8 semantic requirements. After selection, freeze the normative contract/scorer/criteria before genuinely fresh independent acceptance. Neither pipeline is production-qualified by these results. See `search_proof8_final_qa.json` for all{len(REQUIRED)} requested QA fields.
'''
    with (R/'search_proof8_final_report.md').open('x', encoding='utf-8') as f:
        f.write(report)
    files = {}
    for folder, pattern in [(R,'search_proof8*'), (Path('scripts'),'search_proof8*.py'), (Path('scratch/search_proof8_local'),'*.py')]:
        for path in folder.glob(pattern):
            if path.is_file() and path.name not in ['search_proof8_freeze_manifest.json','search_proof8_freeze_verification.json']:
                files[str(path)] = sha(path)
    # Bind installed loader code inspected for this experiment, without modifying it.
    runtime_files = ['.venv/Lib/site-packages/transformers/core_model_loading.py',
                     '.venv/Lib/site-packages/transformers/modeling_utils.py',
                     '.venv/Lib/site-packages/accelerate/utils/modeling.py',
                     '.venv/Lib/site-packages/accelerate/big_modeling.py']
    for p in runtime_files:
        files[p] = sha(p)
    save('freeze_manifest', dict(candidate_id='search-smarteng-disabled-proof-8-local', files=files,
                                 FINAL='LIMITED_LOCAL_EXPERIMENT; QUALIFICATION_INCOMPLETE; PRODUCTION_BLOCKED',
                                 self_hash_policy='Manifest excluded from its entries; its hash is bound in verification'))
    frozen = verify(files)
    assert frozen['verified']
    save('freeze_verification', dict(frozen=frozen, manifest_sha256=sha(R/'search_proof8_freeze_manifest.json'),
                                     required_QA_fields=len(REQUIRED), all_present=all(k in qa for k in REQUIRED),
                                     preservation=preservation))
    print(json.dumps(dict(final='LIMITED_LOCAL_EXPERIMENT', model_loaded=True, predictions=len(serial),
                          retry_gate=gate['RAM_retry_gate'], protected=preservation['previous']['entries'],
                          frozen_entries=len(files), required_QA_fields=len(REQUIRED))))


if __name__ == '__main__':
    main()
