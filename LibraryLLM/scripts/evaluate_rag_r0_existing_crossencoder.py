"""R0: frozen DEV candidates, one untouched local CE, raw logits only."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rag.evaluation.metrics import aggregate, evaluate_query, overlaps

TRAIN = ROOT / 'datasets/training'
REPORTS = TRAIN / 'reports'
CORPUS = ROOT / 'datasets/rag_experiments/chunking_v1/tokens_220'
MODEL_ID = 'cross-encoder/ms-marco-MiniLM-L-6-v2'
CE_CACHE = Path('C:/Users/balak/.cache/huggingface/hub/models--cross-encoder--ms-marco-MiniLM-L-6-v2')
OUT = REPORTS / 'rag_r0_existing_crossencoder.json'
SCORES = TRAIN / 'evaluation/rag_r0_crossencoder_scores.parquet'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2), encoding='utf-8')


def dev_evaluable(questions):
    """Filter before constructing any model input, including unlabelled DEV."""
    return [q for q in questions if q['split'] == 'DEV'
            and any(p['relevance_grade'] == 2 for p in q['accepted_passages'])]


def validate_candidates(candidates, k=50):
    if len(candidates) != k or len({c['chunk_id'] for c in candidates}) != k:
        raise RuntimeError('Candidate count/membership invalid; STOP')
    if [c['rank'] for c in candidates] != list(range(1, k + 1)):
        raise RuntimeError('Dense ranks invalid; STOP')


def rerank_raw(candidates, scores):
    validate_candidates(candidates)
    if len(scores) != len(candidates) or not all(math.isfinite(float(s)) for s in scores):
        raise RuntimeError('CE score count or finite-score check failed; STOP')
    rows = [{**c, 'dense_rank': c['rank'], 'dense_score': c['similarity'],
             'ce_score': float(s)} for c, s in zip(candidates, scores)]
    # Identifier tie-break is identical for both pools and independent of dense score/rank.
    rows.sort(key=lambda c: (-c['ce_score'], c['chunk_id']))
    for rank, row in enumerate(rows, 1):
        row['ce_rank'] = rank
    if Counter(c['chunk_id'] for c in candidates) != Counter(c['chunk_id'] for c in rows):
        raise RuntimeError('Candidate membership changed; STOP')
    return rows


def score_pools(questions, pools, texts, scorer, batch_size=16):
    """Cache only identical (query_id, chunk_id) pairs; no labels enter scoring."""
    queries = dev_evaluable(questions)
    unique = {}
    for system in ('A', 'G3'):
        for q in queries:
            candidates = pools[system][q['query_id']]['top50']
            validate_candidates(candidates)
            for c in candidates:
                key = (q['query_id'], c['chunk_id'])
                pair = (q['question'], texts[c['chunk_id']])
                if key in unique and unique[key] != pair:
                    raise RuntimeError('Cached pair text mismatch; STOP')
                unique[key] = pair
    keys = list(unique)
    scores = []
    for start in range(0, len(keys), batch_size):
        batch = [unique[key] for key in keys[start:start + batch_size]]
        result = list(scorer.predict_raw(batch))
        if len(result) != len(batch):
            raise RuntimeError('Scorer output count mismatch; STOP')
        scores.extend(float(x) for x in result)
    cache = dict(zip(keys, scores))
    ranked, rows = {}, []
    for system in ('A', 'G3'):
        ranked[system] = {}
        for q in queries:
            candidates = pools[system][q['query_id']]['top50']
            ordered = rerank_raw(candidates, [cache[(q['query_id'], c['chunk_id'])] for c in candidates])
            for c in ordered:
                rows.append({'retriever': system, 'query_id': q['query_id'],
                             'work_id': q['work_id'], 'chunk_id': c['chunk_id'],
                             'dense_rank': c['dense_rank'], 'dense_score': c['dense_score'],
                             'ce_rank': c['ce_rank'], 'ce_score': c['ce_score'],
                             'cross_encoder_fingerprint': scorer.fingerprint})
            ranked[system][q['query_id']] = ordered
    return ranked, rows, {'logical_pair_count': len(rows), 'actual_scored_pair_count': len(keys),
                         'duplicate_pair_reuses': len(rows) - len(keys),
                         'encoded_query_ids': [q['query_id'] for q in queries],
                         'same_cross_encoder_fingerprint': scorer.fingerprint}


def top50_invariants(dense, ce):
    passed = (dense['metrics']['hit']['50'] == ce['metrics']['hit']['50']
              and dense['metrics']['recall']['50'] == ce['metrics']['recall']['50']
              and dense['no_gold_top50'] == ce['no_gold_top50'])
    if not passed:
        raise RuntimeError('R0 Top50 metric invariant failed; STOP')
    return True


def stats(values):
    import numpy as np
    if not values:
        return {'count': 0, 'mean': None, 'median': None, 'p10': None, 'p90': None, 'min': None, 'max': None}
    return {'count': len(values), 'mean': statistics.mean(values), 'median': statistics.median(values),
            'p10': float(np.percentile(values, 10)), 'p90': float(np.percentile(values, 90)),
            'min': min(values), 'max': max(values)}


def movement(before, after, names=('IMPROVED', 'REGRESSED', 'UNCHANGED')):
    a = before if before is not None else math.inf
    b = after if after is not None else math.inf
    return names[0] if b < a else names[1] if b > a else names[2]


def system_result(questions, ranked, chunks):
    metrics = {q['query_id']: evaluate_query(q, [c['chunk_id'] for c in ranked[q['query_id']]], chunks)
               for q in questions}
    return {'metrics': aggregate(metrics.values()),
            'no_gold_top50': sum(m['first_rank'] is None for m in metrics.values()),
            'per_query_metrics': metrics}


def frozen_paths():
    """Includes prior ledgers, all G3 outputs, baseline/control artifacts and CE cache."""
    from scripts.gooaq_g3_controls import verify
    safety = verify()
    pre = read(REPORTS / 'rag_g3_gooaq_preflight.json')
    paths = {ROOT / p for p in pre['historical_before_sha256']}
    paths.update(Path(pre['base_snapshot']) / p for p in pre['base_snapshot_sha256'])
    prod = read(ROOT / 'datasets/rag_experiments/chunking_v1/reports/production_before_sha256.json')
    paths.update(ROOT / p for p in prod)
    paths.update([ROOT / 'rag/evaluation/rag_retrieval_eval_v1.json',
                  ROOT / 'rag/evaluation/source_map_v1.json', TRAIN / 'manifests/control_v1.json'])
    paths.update(p for p in CORPUS.rglob('*') if p.is_file())
    for folder in [TRAIN / 'generic/gooaq_g3', TRAIN / 'hf_cache/gooaq_g3',
                   TRAIN / 'models/minilm_g3_gooaq_50k_smoke', TRAIN / 'models/minilm_g3_gooaq_50k_full',
                   TRAIN / 'checkpoints/minilm_g3_gooaq_50k_smoke', TRAIN / 'checkpoints/minilm_g3_gooaq_50k_full',
                   TRAIN / 'evaluation_indexes/minilm_g3_gooaq_50k', CE_CACHE]:
        paths.update(p for p in folder.rglob('*') if p.is_file())
    for folder in [ROOT / 'scripts', ROOT / 'tests', TRAIN / 'manifests', REPORTS]:
        paths.update(p for p in folder.iterdir() if p.is_file() and ('g3' in p.name or 'baseline_a' in p.name))
    ledger = {str(p): sha(p) for p in sorted(paths)}
    g3 = read(REPORTS / 'rag_g3_gooaq_final.json')
    assert g3['decision'] == 'B. GOOAQ G3 IS NEUTRAL / INCONCLUSIVE'
    assert sha(Path(g3['training']['model_path']) / 'model.safetensors') == g3['training']['model_weights_sha256']
    from scripts.gooaq_g3_controls import DATA
    assert sha(DATA / 'manifest.json') == g3['final_data_manifest_sha256']
    assert sha(DATA / 'source_manifest.json') == g3['source_manifest_sha256']
    for item in read(DATA / 'manifest.json')['files'].values():
        assert sha(item['path']) == item['sha256']
    index = TRAIN / 'evaluation_indexes/minilm_g3_gooaq_50k'
    assert sha(index / 'faiss.index') == g3['index']['index_sha256']
    assert sha(index / 'embeddings.npy') == g3['index']['embeddings_sha256']
    for wid, item in g3['index_integrity']['books'].items():
        assert sha(index / 'books' / f'{wid}.index') == item['sha256']
    return ledger, safety


def verify_ledger(ledger):
    changed = [p for p, digest in ledger.items() if not Path(p).exists() or sha(p) != digest]
    if changed:
        raise RuntimeError(f'Historical/CE/production changes; STOP: {changed}')
    # Also detect new files in the CE cache; local-only loading must not download.
    ce_files = {str(p) for p in CE_CACHE.rglob('*') if p.is_file()}
    if ce_files != {p for p in ledger if Path(p).is_relative_to(CE_CACHE)}:
        raise RuntimeError('CE cache membership changed; STOP')
    return {'verified_file_count': len(ledger), 'historical_files_changed': 0,
            'cross_encoder_cache_changes': 0, 'production_files_changed': 0}


def load_frozen_candidates(questions, chunks):
    paths = {'A': REPORTS / 'rag_g3_baseline_reproduction.json',
             'G3': TRAIN / 'evaluation_indexes/minilm_g3_gooaq_50k/dense_dev_evaluation.json'}
    dev = [q for q in questions if q['split'] == 'DEV']
    expected = {q['query_id'] for q in dev}
    assert len(dev) == 30 and len(dev_evaluable(questions)) == 29
    pools = {}
    for system, path in paths.items():
        saved = read(path)
        pools[system] = {q['query_id']: q for q in saved['queries']}
        assert set(pools[system]) == expected
        for q in dev:
            row = pools[system][q['query_id']]
            assert row['split'] == 'DEV' and row['work_id'] == q['work_id']
            validate_candidates(row['top50'])
            for c in row['top50']:
                chunk = chunks[c['chunk_id']]
                assert chunk['work_id'] == q['work_id']
                assert (chunk['start'], chunk['end']) == (c['source_start'], c['source_end'])
            recomputed = evaluate_query(q, [c['chunk_id'] for c in row['top50']], chunks)
            assert recomputed == row['metrics']
    old = {q['query_id']: q for q in read(REPORTS / 'baseline_a_previous.json')['queries'] if q['split'] == 'DEV'}
    assert set(old) == expected
    assert all([c['chunk_id'] for c in old[q]['top50']] == [c['chunk_id'] for c in pools['A'][q]['top50']] for q in expected)
    prior = read(REPORTS / 'rag_g3_gooaq_eval.json')
    for system, field in [('A', 'a'), ('G3', 'g3')]:
        assert aggregate(row['metrics'] for row in pools[system].values()) == prior[field]
    for q in prior['per_query']:
        assert pools['G3'][q['query_id']]['metrics']['first_rank'] == q['g3_first_gold_rank']
    return pools, {'source': 'loaded authoritative saved DEV Top50; no retriever encoded',
                   'A': {'path': str(paths['A']), 'sha256': sha(paths['A']), 'exact_historical_DEV_ID_match': True},
                   'G3': {'path': str(paths['G3']), 'sha256': sha(paths['G3']), 'frozen_G3_hash_and_metrics_match': True},
                   'DEV_queries': 30, 'evaluable_queries': 29, 'candidate_count_per_query': 50}


def analyze(questions, pools, ranked, chunks, books):
    queries = dev_evaluable(questions)
    systems, per_query, separation, review, margin_by_query = {}, [], {}, [], {}
    for system in ('A', 'G3'):
        dense = {q['query_id']: pools[system][q['query_id']]['top50'] for q in queries}
        systems[f'{system} dense'] = system_result(queries, dense, chunks)
        systems[f'{system}+CE'] = system_result(queries, ranked[system], chunks)
        top50_invariants(systems[f'{system} dense'], systems[f'{system}+CE'])
        accepted, incorrect, margins = [], [], []
        margin_by_query[system] = {}
        for q in queries:
            spans = [p for p in q['accepted_passages'] if p['relevance_grade'] == 2]
            def is_accepted(c):
                return any(overlaps(chunks[c['chunk_id']], p) for p in spans)
            ordered = ranked[system][q['query_id']]
            good = [c for c in ordered if is_accepted(c)]
            bad = [c for c in ordered if not is_accepted(c)]
            accepted.extend(c['ce_score'] for c in good)
            incorrect.extend(c['ce_score'] for c in bad)
            if good and bad:
                margins.append(good[0]['ce_score'] - bad[0]['ce_score'])
            margin_by_query[system][q['query_id']] = {
                'best_accepted_ce_score':good[0]['ce_score'] if good else None,
                'best_nonaccepted_ce_score':bad[0]['ce_score'] if bad else None,
                'margin':good[0]['ce_score']-bad[0]['ce_score'] if good and bad else None}
            ce_rank = good[0]['ce_rank'] if good else None
            if ce_rank and ce_rank > 10:
                review.append({'retriever': system, 'query_id': q['query_id'],
                               'book': books[q['work_id']]['title'], 'question': q['question'],
                               'dense_accepted_rank': systems[f'{system} dense']['per_query_metrics'][q['query_id']]['first_rank'],
                               'ce_accepted_rank': ce_rank, 'accepted_candidate': good[0],
                               'best_nonaccepted_candidate': bad[0], 'top5': ordered[:5],
                               'margin': good[0]['ce_score'] - bad[0]['ce_score']})
        separation[system] = {'accepted': stats(accepted), 'nonaccepted': stats(incorrect),
                              'best_accepted_minus_best_nonaccepted': stats(margins)}
    for q in queries:
        ranks = {name: systems[name]['per_query_metrics'][q['query_id']]['first_rank'] for name in systems}
        row = {'query_id': q['query_id'], 'work_id': q['work_id'], 'book': books[q['work_id']]['title'],
               'question': q['question'], 'ranks': ranks,
               'A_movement': movement(ranks['A dense'], ranks['A+CE']),
               'G3_movement': movement(ranks['G3 dense'], ranks['G3+CE']),
               'practical_movement': movement(ranks['A+CE'], ranks['G3+CE'], ('BETTER', 'WORSE', 'SAME'))}
        per_query.append(row)
    counts = {field: dict(Counter(q[field] for q in per_query)) for field in ['A_movement', 'G3_movement', 'practical_movement']}
    thresholds = {}
    for system in ('A', 'G3'):
        thresholds[system] = {}
        for k in [1, 3, 5, 10, 20]:
            ranks = [(q['ranks'][f'{system} dense'], q['ranks'][f'{system}+CE']) for q in per_query]
            thresholds[system][f'CE_RECOVERED_TO_TOP{k}'] = sum((a is None or a > k) and b is not None and b <= k for a, b in ranks)
            thresholds[system][f'CE_DEMOTED_OUT_OF_TOP{k}'] = sum(a is not None and a <= k and (b is None or b > k) for a, b in ranks)
    diagnostics = {}
    for qid in ['v8_06', 'pp_05', 'v8_10', 'pp_02', 'time_05']:
        q = next(q for q in queries if q['query_id'] == qid)
        spans = [p for p in q['accepted_passages'] if p['relevance_grade'] == 2]
        diagnostics[qid] = {'rank_comparison': next(x for x in per_query if x['query_id'] == qid), 'pools': {}}
        for system in ('A', 'G3'):
            ordered = ranked[system][qid]
            good = [c for c in ordered if any(overlaps(chunks[c['chunk_id']], p) for p in spans)]
            bad = [c for c in ordered if not any(overlaps(chunks[c['chunk_id']], p) for p in spans)]
            diagnostics[qid]['pools'][system] = {'best_accepted': good[0] if good else None,
                                                'best_nonaccepted': bad[0] if bad else None,
                                                'margin': good[0]['ce_score'] - bad[0]['ce_score'] if good and bad else None,
                                                'top10': ordered[:10]}
            dense_first = next(c for c in ordered if c['dense_rank'] == 1)
            diagnostics[qid]['pools'][system]['dense_rank1_candidate'] = dense_first
            diagnostics[qid]['pools'][system]['dense_rank1_is_accepted'] = any(overlaps(chunks[dense_first['chunk_id']], p) for p in spans)
            diagnostics[qid]['pools'][system]['accepted_minus_dense_rank1_ce_margin'] = good[0]['ce_score']-dense_first['ce_score'] if good else None
    return {'systems': systems, 'per_query': per_query, 'movement_counts': counts,
            'threshold_counts': thresholds, 'score_separation': separation, 'per_query_score_margins':margin_by_query,
            'candidate_failure_counts': {s: systems[f'{s} dense']['no_gold_top50'] for s in ('A', 'G3')},
            'poor_rank_review_cases': review, 'diagnostics': diagnostics, 'top50_invariants_passed': True}


def initial_decision(report):
    a = report['systems']['A+CE']['metrics'];g = report['systems']['G3+CE']['metrics']
    deltas = [g['mrr'] - a['mrr']] + [g['hit'][str(k)] - a['hit'][str(k)] for k in [5, 10, 20]]
    extra_ranks = [report['diagnostics'][q]['rank_comparison']['ranks']['G3+CE'] for q in ['v8_06', 'pp_05']]
    if all(d >= 0 for d in deltas) and any(d > 0 for d in deltas) and any(r is not None and r <= 20 for r in extra_ranks):
        return "A. G3'S EXTRA TOP50 COVERAGE IS USEFUL AFTER EXISTING RERANKING"
    if all(d <= 0 for d in deltas) and any(d < 0 for d in deltas):
        return 'C. A+CE REMAINS BETTER THAN G3+CE'
    return 'D. R0 MIXED / INCONCLUSIVE'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--retrievers', required=True, choices=['baseline,g3'])
    parser.add_argument('--candidate-k', required=True, type=int, choices=[50])
    parser.add_argument('--cross-encoder', required=True, choices=[MODEL_ID])
    parser.add_argument('--raw-cross-encoder-only', required=True, action='store_true')
    parser.add_argument('--split', required=True, choices=['dev'])
    args = parser.parse_args()
    for path in [OUT, SCORES, OUT.with_suffix('.md'), REPORTS/'rag_r0_preflight.json']:
        if path.exists():
            raise FileExistsError(f'R0 output already exists; will not overwrite: {path}')
    started = time.perf_counter()
    ledger, prior_safety = frozen_paths()
    revision = (CE_CACHE / 'refs/main').read_text().strip()
    snapshot = CE_CACHE / 'snapshots' / revision
    config = read(snapshot / 'config.json')
    assert config['num_hidden_layers'] == 6 and config['hidden_size'] == 384
    assert config['architectures'] == ['BertForSequenceClassification'] and len(config['id2label']) == 1
    fingerprint = {str(p.relative_to(snapshot)): sha(p) for p in snapshot.rglob('*') if p.is_file()}
    weight_hash = fingerprint['model.safetensors']
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['HF_DATASETS_OFFLINE'] = '1'
    import numpy as np
    import psutil
    import pyarrow as pa
    import pyarrow.parquet as pq
    import torch
    from sentence_transformers import CrossEncoder
    chunks = {r['chunk_id']: {'start': r['source_start_char'], 'end': r['source_end_char'],
                              'work_id': r['work_id'], 'text': r['text']}
              for r in pq.read_table(CORPUS / 'chunks.parquet', columns=['chunk_id', 'work_id', 'text',
                                                                      'source_start_char', 'source_end_char']).to_pylist()}
    questions = read(ROOT / 'rag/evaluation/rag_retrieval_eval_v1.json')['questions']
    pools, reproduction = load_frozen_candidates(questions, chunks)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    free, total = torch.cuda.mem_get_info() if device == 'cuda' else (None, None)
    if device == 'cuda' and free < 3 * 1024**3:
        raise MemoryError('Insufficient free VRAM before CE; STOP')
    if psutil.virtual_memory().available < 2 * 1024**3:
        raise MemoryError('Insufficient available RAM before CE; STOP')
    environment = {'python_executable': sys.executable, 'torch': torch.__version__,
                   'sentence_transformers': __import__('sentence_transformers').__version__,
                   'CUDA': torch.version.cuda, 'device': device, 'GPU': torch.cuda.get_device_name(0) if device == 'cuda' else None,
                   'free_vram_bytes': free, 'total_vram_bytes': total,
                   'RAM_total_bytes': psutil.virtual_memory().total, 'RAM_available_bytes': psutil.virtual_memory().available}
    import subprocess
    environment['other_GPU_usage'] = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,process_name,used_gpu_memory',
                                                    '--format=csv,noheader'], capture_output=True, text=True).stdout.strip()
    preflight = {'before_sha256': ledger, 'historical_verification': prior_safety,
                 'cross_encoder_snapshot': str(snapshot), 'cross_encoder_files': fingerprint,
                 'reproduction': reproduction, 'environment': environment}
    write(REPORTS / 'rag_r0_preflight.json', preflight)
    print(json.dumps({'preflight': prior_safety, 'reproduction': reproduction, 'environment': environment}), flush=True)
    if device == 'cuda':
        torch.cuda.reset_peak_memory_stats()
    minimum_free = [free];peak_rss = [psutil.Process().memory_info().rss];stop = threading.Event()
    def monitor():
        while not stop.wait(.1):
            peak_rss[0] = max(peak_rss[0], psutil.Process().memory_info().rss)
            if device == 'cuda':
                minimum_free[0] = min(minimum_free[0], torch.cuda.mem_get_info()[0])
    watcher = threading.Thread(target=monitor, daemon=True);watcher.start()
    try:
        model = CrossEncoder(str(snapshot), device=device, local_files_only=True, model_kwargs={'dtype': torch.float32})
        model.eval()
        assert model.num_labels == 1 and model.max_length == 512
        assert next(model.parameters()).dtype == torch.float32
        model_info = {'model_id': MODEL_ID, 'path': str(snapshot), 'revision': revision,
                      'model_weights_sha256': weight_hash, 'files_sha256': fingerprint,
                      'max_sequence_length': model.max_length, 'device': str(model.device), 'dtype': str(next(model.parameters()).dtype),
                      'legacy_config_name_or_path': config.get('_name_or_path'), 'num_hidden_layers': 6,
                      'loaded_default_activation': type(model.activation_fn).__name__,
                      'scoring_activation': 'Identity (raw logits)', 'same_object_for_both_pools': True,
                      'model_inputs': ['original DEV question', 'exact frozen candidate passage text']}
        batch_size = 16
        class Scorer:
            fingerprint = weight_hash
            def predict_raw(self, pairs):
                if device == 'cuda' and torch.cuda.mem_get_info()[0] < 1.5 * 1024**3:
                    raise MemoryError('Unsafe CE GPU headroom; STOP')
                if psutil.virtual_memory().available < 1 * 1024**3:
                    raise MemoryError('Unsafe CE RAM headroom; STOP')
                return model.predict(pairs, batch_size=batch_size, activation_fn=torch.nn.Identity(),
                                     apply_softmax=False, convert_to_numpy=True, show_progress_bar=False)
        scoring_started = time.perf_counter()
        ranked, score_rows, scoring = score_pools(questions, pools, {c: r['text'] for c, r in chunks.items()}, Scorer(), batch_size)
        scoring['runtime_seconds'] = time.perf_counter() - scoring_started
    finally:
        stop.set();watcher.join(timeout=2)
    if device == 'cuda' and minimum_free[0] < 1.5 * 1024**3:
        raise MemoryError('CE minimum GPU headroom below limit; STOP')
    assert scoring['logical_pair_count'] == len(score_rows) == 2900
    assert set(scoring['encoded_query_ids']) == {q['query_id'] for q in dev_evaluable(questions)}
    analysis = analyze(questions, pools, ranked, chunks, read(CORPUS / 'manifest.json')['books'])
    safety = verify_ledger(ledger)
    resource = {'batch_size': batch_size, 'peak_allocated_VRAM_bytes': torch.cuda.max_memory_allocated() if device == 'cuda' else None,
                'peak_reserved_VRAM_bytes': torch.cuda.max_memory_reserved() if device == 'cuda' else None,
                'minimum_global_free_VRAM_bytes': minimum_free[0], 'peak_process_RSS_bytes': peak_rss[0],
                'experiment_runtime_seconds': time.perf_counter() - started}
    report = {'experiment': 'R0_EXISTING_CROSS_ENCODER', 'result_label': 'EXPERIMENTAL / DESCRIPTIVE — DRAFT DEV labels',
              'cross_encoder': model_info, 'preflight': environment, 'reproduction': reproduction,
              'scoring': scoring, 'resources': resource, 'safety': safety, **analysis,
              'scoring_contract': 'raw CE logits descending; equal-score ties by chunk_id; no dense/evidence/lexical mix or expansion',
              'TEST_evaluated': False, 'training_performed': False, 'downloads_performed': False,
              'score_parquet_path': str(SCORES), 'domain_failure_audit_status': 'pending engineering source-text inspection',
              'artifacts_created': ['scripts/evaluate_rag_r0_existing_crossencoder.py', 'tests/test_rag_r0_existing_crossencoder.py',
                                    str(SCORES.relative_to(ROOT)), str(OUT.relative_to(ROOT)),
                                    str(OUT.with_suffix('.md').relative_to(ROOT)), 'datasets/training/reports/rag_r0_preflight.json']}
    report['decision'] = initial_decision(report)
    SCORES.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(score_rows), SCORES, compression='zstd')
    report['score_parquet_sha256'] = sha(SCORES)
    write(OUT, report)
    # Exact passages are for engineering review only, after all model scoring finishes.
    diagnostics = {'review_definition': 'review every pool/query with accepted CE first rank >10; final domain failure requires source inspection',
                   'review_cases': [{**case, 'accepted_text': chunks[case['accepted_candidate']['chunk_id']]['text'],
                                     'best_nonaccepted_text': chunks[case['best_nonaccepted_candidate']['chunk_id']]['text'],
                                     'top5_texts': [chunks[c['chunk_id']]['text'] for c in case['top5']]} for case in analysis['poor_rank_review_cases']],
                   'TEST_evaluated': False}
    write(REPORTS / 'rag_r0_reranker_failures.json', diagnostics)
    render_report(report, chunks)
    print(json.dumps({'decision': report['decision'], 'systems': {s: {'metrics': v['metrics'], 'no_gold_top50': v['no_gold_top50']} for s, v in analysis['systems'].items()},
                      'scoring': scoring, 'resources': resource, 'safety': safety, 'review_count': len(diagnostics['review_cases'])}, indent=2), flush=True)


def render_report(report, chunks):
    """Re-render after engineering annotations without any further CE scoring."""
    r = report;ce = r['cross_encoder']
    lines = ['# R0 — existing unchanged cross-encoder', '', f"**FINAL R0 DECISION: {r['decision']}.**", '',
             'Experimental/descriptive: frozen DEV labels remain DRAFT. No training, downloads, retrieval regeneration, production promotion, Qwen, expansion, lexical search, or score mixing. TEST evaluated: NO.', '',
             '## Frozen controls and CE fingerprint', '', f"Before/after freeze checks: `{r['safety']}`. Prior recorded controls `{r.get('historical_verification')}`; production snapshot contains 64 files, changes 0. Detailed before SHA-256 ledger: `rag_r0_preflight.json`. G1/G2/G3 remain complete and frozen.", '',
             f"Existing `{ce['model_id']}`; snapshot `{ce['revision']}`; local path `{ce['path']}`; weights SHA-256 `{ce['model_weights_sha256']}`. Tokenizer/config hashes are in JSON. Max length {ce['max_sequence_length']}; device `{ce['device']}`; dtype `{ce['dtype']}`; loaded default activation `{ce['loaded_default_activation']}`, explicitly scored through Identity to return raw logits.", '',
             f"The cache config contains legacy `_name_or_path={ce['legacy_config_name_or_path']}` metadata, but the named L-6 repository cache, resolved main revision, actual six-layer architecture, and single immutable weight fingerprint were verified. The same in-memory CE scored both pools; no alternate checkpoint was loaded.", '',
             f"Saved DEV candidates loaded directly: `{r['reproduction']}`. A IDs match authoritative historical DEV lists; G3 file hash, 30-query set, individual dense metrics, and aggregate metrics match the frozen G3 report. Exact frozen chunk IDs, texts, work IDs, and source offsets were validated. No dense encoder was invoked.", '',
             f"Environment `{r['preflight']}`. Resources `{r['resources']}`. Scoring `{r['scoring']}`. Logical score rows 2,900; identical query/chunk pairs scored once and reused across pools. Only (original query, frozen passage) pairs reach CE. No gold/span/answer/neighbour/metadata enters scoring. Tie policy is chunk ID ascending only when raw scores are exactly equal.", '',
             '## Four-system DEV metrics', '', '| Metric | A dense | A+CE | G3 dense | G3+CE |', '|---|---:|---:|---:|---:|']
    names = ['A dense', 'A+CE', 'G3 dense', 'G3+CE']
    def cells(fn, fmt):return ' | '.join(format(fn(r['systems'][name]), fmt) for name in names)
    lines.append('| MRR | ' + cells(lambda s:s['metrics']['mrr'], '.4f') + ' |')
    for family, ks in [('hit', [1,3,5,10,20,50]), ('recall',[5,10,20,50])]:
        for k in ks:lines.append(f'| {family.title()}@{k} | ' + cells(lambda s:s['metrics'][family][str(k)], '.2%') + ' |')
    lines.append('| No accepted span Top50 | ' + cells(lambda s:s['no_gold_top50'], 'd') + ' |')
    lines += ['', '**Top50 invariants passed: YES.** Candidate membership, Hit@50, Recall@50, and no-gold Top50 are identical before/after CE within each retriever.', '',
              '## Practical comparison and movement', '', f"Movements: `{r['movement_counts']}`. Primary practical comparison is A+CE → G3+CE; prioritize MRR and Hit@5/10/20. Candidate-generation coverage remains fixed.", '',
              '| Query | Book | A dense | A+CE | G3 dense | G3+CE | A CE movement | G3 CE movement | Final comparison |', '|---|---|---:|---:|---:|---:|---|---|---|']
    for q in r['per_query']:
        lines.append('| ' + ' | '.join(str(x) for x in [q['query_id'],q['book'],*[q['ranks'][n] for n in names],q['A_movement'],q['G3_movement'],q['practical_movement']]) + ' |')
    lines += ['', '## Threshold recoveries and demotions', '', '| Transition | A | G3 |', '|---|---:|---:|']
    for k in [1,3,5,10,20]:
        for prefix in ['CE_RECOVERED_TO_TOP','CE_DEMOTED_OUT_OF_TOP']:
            key = f'{prefix}{k}';lines.append(f"| {key} | {r['threshold_counts']['A'][key]} | {r['threshold_counts']['G3'][key]} |")
    lines += ['', '## Score separation', '',
              'Accepted means overlapping a frozen grade-2 span under the existing source-span metric. “Nonaccepted/incorrect” means not overlapping those spans, not a new human relevance judgement; DRAFT labels can omit relevant passages. Only post-scoring evaluation uses these labels.', '',
              '| Pool | Group | Count | Mean | Median | p10 | p90 | Min | Max |', '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for pool, groups in r['score_separation'].items():
        for group, values in groups.items():
            lines.append('| ' + ' | '.join(str(x) if x is None or isinstance(x,int) else f'{x:.6f}' if isinstance(x,float) else x for x in [pool,group,*[values[k] for k in ['count','mean','median','p10','p90','min','max']]]) + ' |')
    lines += ['', '| Query | A best-accepted minus best-nonaccepted CE score | G3 margin |', '|---|---:|---:|']
    for q in r['per_query']:
        qid=q['query_id']
        lines.append(f"| {qid} | {r['per_query_score_margins']['A'][qid]['margin']} | {r['per_query_score_margins']['G3'][qid]['margin']} |")
    for qid, diagnostic in r['diagnostics'].items():
        q = diagnostic['rank_comparison'];lines += ['', f'## Diagnostic {qid} — {q["book"]}', '', q['question'], '', f"Ranks `{q['ranks']}`; G3 CE movement `{q['G3_movement']}`.", '']
        for pool, d in diagnostic['pools'].items():
            good = d['best_accepted'];bad = d['best_nonaccepted']
            lines += [f"{pool}: accepted CE rank/score `{(good['ce_rank'], good['ce_score']) if good else None}`; best nonaccepted CE rank/score `{(bad['ce_rank'],bad['ce_score']) if bad else None}`; accepted-minus-best-nonaccepted margin `{d['margin']}`.", '']
            first=d['dense_rank1_candidate']
            lines += [f"Original dense rank1: `{first['chunk_id']}`, raw CE score {first['ce_score']:.6f}, CE rank {first['ce_rank']}, accepted={d['dense_rank1_is_accepted']}; accepted-minus-dense-rank1 CE margin `{d['accepted_minus_dense_rank1_ce_margin']}`. When CE rank1 is accepted, the best nonaccepted passage is at a later CE rank.",'']
            if good:lines += ['Accepted passage: '+chunks[good['chunk_id']]['text'].replace('\n',' '),'']
            lines += ['| CE rank | Dense rank | Raw CE score | Chunk | Frozen candidate text |', '|---:|---:|---:|---|---|']
            for c in d['top10']:
                text = chunks[c['chunk_id']]['text'].replace('\n',' ').replace('|','\\|')
                lines.append(f"| {c['ce_rank']} | {c['dense_rank']} | {c['ce_score']:.6f} | {c['chunk_id']} | {text} |")
    lines += ['', '## Candidate failures and reranker domain failures', '', f"Candidate failures (accepted passage absent from Top50): `{r['candidate_failure_counts']}`. The CE cannot recover an absent candidate.", '',
              'Operational domain-failure review: inspect every pool/query whose first accepted CE rank is >10. Confirm failure only when source text shows clearly incorrect candidates substantially above the accepted passage. A nonaccepted span alone is insufficient. All review cases, including ambiguous/relevant alternatives, are preserved in `rag_r0_reranker_failures.json`.', '',
              f"Audit status: {r['domain_failure_audit_status']}. Domain-failure summary: `{r.get('domain_failure_summary')}`.", '']
    for note in r.get('domain_failure_audit',[]):
        lines.append(f"- {note['retriever']} / {note['query_id']}: {note['classification']}; dense {note['dense_rank']} → CE {note['ce_rank']}. {note['reason']}")
    lines += ['',f"Required tests: `{r.get('tests')}`. All runtime candidate-count, membership, metric-invariance, DEV-only, score-row and freeze assertions passed.",'']
    lines += ['', '## Final controls and stop', '', f"{r.get('decision_reason','Decision uses practical CE metrics and useful ranks of the two extra G3 accepted candidates; mixed directions remain inconclusive.')}", '',
              f"**TEST evaluated: NO. Production files changed: {r['safety']['production_files_changed']}. CE/cache and historical files changed: 0.**", '',
              f"Score parquet SHA-256 `{r['score_parquet_sha256']}`; full 2,900 score rows preserve dense rank/score, raw CE score/rank, retriever/query/work/chunk IDs, and shared CE fingerprint.", '',
              'Artifacts created:', '', *[f'- `{p}`' for p in r['artifacts_created']], '',
              f"**FINAL R0 DECISION: {r['decision']}.**", '', 'STOP after R0. No cross-encoder, bi-encoder, Qwen, or R1 training was started.']
    OUT.with_suffix('.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    main()
