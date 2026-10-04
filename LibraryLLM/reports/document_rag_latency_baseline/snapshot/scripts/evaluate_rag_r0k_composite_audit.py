"""Audit exact current production scoring on fixed original-query G3 Dense60."""
import argparse
import json
import time
from r0k_common import *


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--retriever', required=True, choices=['g3'])
    p.add_argument('--candidate-k', required=True, type=int, choices=[60])
    p.add_argument('--compare', required=True, choices=[','.join(SYSTEMS)])
    p.add_argument('--split', required=True, choices=['dev'])
    p.parse_args()
    for path in (OUT_K, SCORES_K, PRE_K):
        if path.exists(): raise FileExistsError(f'R0K artifact exists; inspect before any rerun: {path}')
    ledger, r0, r0i, r0j = freeze_k()
    _, formula = production_formula()
    package = formula_package_sources()
    for path, fingerprint in package['source_sha256'].items(): ledger[path] = fingerprint
    before_sources = {str(ROOT / 'scripts' / name): sha(ROOT / 'scripts' / name)
                      for name in ('r0k_common.py', 'evaluate_rag_r0k_composite_audit.py')}
    write(PRE_K, {'before_sha256': ledger, 'systems': SYSTEMS, 'candidate_K': 60,
          'formula': formula, 'CE_package': package, 'selection_policy': SELECTION_K,
          'experimental_code_sha256': before_sources, 'query_expansion': False,
          'semantic_intent_data': None, 'warmup_pairs': 16, 'batch_size': 16, 'TEST_evaluated': False})
    rt = Runtime(r0)
    assert isinstance(rt.ce.activation_fn, rt.torch.nn.Identity), 'Production CE default differs from raw Identity; STOP'
    import pyarrow.parquet as pq
    metadata_rows = pq.read_table(CORPUS / 'chunks.parquet').to_pylist()
    metadata = {c['chunk_id']: c for c in metadata_rows}
    all_texts = {c['chunk_id']: c['text'] for c in metadata_rows}
    assert len(all_texts) == 16895
    historical50 = {q['query_id']: q['top50'] for q in read(TRAIN / 'evaluation_indexes/minilm_g3_gooaq_50k/dense_dev_evaluation.json')['queries']}
    baseline = next(r for r in r0j['results'] if r['system'] == 'dense60')
    top60 = {}
    for q in rt.questions:
        rows = rt.retrieve(q, 60)
        assert ids(rows[:50]) == ids(historical50[q['query_id']]), 'Frozen G3 Top50 differs; STOP'
        top60[q['query_id']] = rows
        if q['query_id'] in baseline['ranked_candidates']:
            old = sorted(baseline['ranked_candidates'][q['query_id']], key=lambda c: c['rank'])
            assert ids(rows) == ids(old), 'R0J Top60 differs; STOP'
    reproduction = {'all_DEV_queries': len(rt.questions), 'evaluable_DEV_queries': len(rt.evaluable),
                    'exact_Top50_prefix_all_DEV': True, 'exact_R0J_Top60_evaluable': True}
    rt.warm(top60)
    with Memory(rt.torch, rt.psutil) as memory:
        rt.torch.cuda.synchronize(); experiment_start = time.perf_counter(); t = experiment_start
        pools = {q['query_id']: rt.retrieve(q, 60) for q in rt.evaluable}
        rt.torch.cuda.synchronize(); retrieval_seconds = time.perf_counter()-t
        assert all(ids(rows) == ids(top60[qid]) for qid, rows in pools.items())
        pairs = [(q['question'], all_texts[c['chunk_id']]) for q in rt.evaluable for c in pools[q['query_id']]]
        assert len(pairs) == 1740 and all(text for _, text in pairs)
        rt.torch.cuda.synchronize(); t = time.perf_counter()
        scores = rt.score(pairs)
        rt.torch.cuda.synchronize(); ce_seconds = time.perf_counter()-t
        raw_pools = {}; offset = 0
        t = time.perf_counter()
        for q in rt.evaluable:
            qid = q['query_id']
            raw_pools[qid] = rerank(pools[qid], scores[offset:offset+60]); offset += 60
        raw_sort_seconds = time.perf_counter()-t
        composite_pools = {}; evidence_seconds = 0.; composite_total_seconds = 0.
        for q in rt.evaluable:
            qid = q['query_id']
            score_by_id = {c['chunk_id']: c['ce_score'] for c in raw_pools[qid]}
            candidates = scoring_candidates(pools[qid], metadata)
            t = time.perf_counter()
            combined, timing = composite(candidates, [score_by_id[c['chunk_id']] for c in candidates], q['question'], all_texts)
            composite_total_seconds += time.perf_counter()-t
            evidence_seconds += timing['evidence_seconds']
            composite_pools[qid] = combined
        source_verify(formula)
        execution_seconds = time.perf_counter()-experiment_start
    system_pools = {'dense': pools, 'raw-ce': raw_pools, 'current-composite': composite_pools}
    system_metrics = {name: metrics(rt.evaluable, rows, rt.chunks, 60) for name, rows in system_pools.items()}
    assert system_metrics['dense'] == baseline['candidate_metrics'], 'R0J dense metrics differ; STOP'
    assert system_metrics['raw-ce'] == baseline['CE_metrics'], 'R0J raw CE metrics differ; STOP'
    old_scores = {(qid, c['chunk_id']): c['ce_score'] for qid, rows in baseline['ranked_candidates'].items() for c in rows}
    assert all(ids(raw_pools[qid]) == ids(baseline['ranked_candidates'][qid]) for qid in pools)
    maximum_score_delta = max(abs(c['ce_score'] - old_scores[(qid,c['chunk_id'])]) for qid, rows in raw_pools.items() for c in rows)
    for qid in pools:
        assert all(set(ids(system_pools[name][qid])) == set(ids(pools[qid])) and len(system_pools[name][qid]) == 60 for name in SYSTEMS)
    for field in ('candidate_Hit', 'candidate_Recall', 'covered_queries', 'no_gold_candidate_count', 'admitted_spans'):
        assert len({m[field] for m in system_metrics.values()}) == 1, 'Candidate admission metrics changed; STOP'
    saved_rows = []
    w = formula['weights']
    for q in rt.evaluable:
        qid = q['query_id']
        raw = {c['chunk_id']: c for c in raw_pools[qid]}
        composite_by_id = {c['chunk_id']: c for c in composite_pools[qid]}
        for c in pools[qid]:
            cid = c['chunk_id']; combined = composite_by_id[cid]
            cw = w['CE']*combined['normalized_rerank_score']
            ew = w['evidence']*combined['evidence_score']
            dw = w['dense']*combined['faiss_norm']
            assert combined['rerank_score'] == raw[cid]['ce_score']
            assert cw+ew+dw == combined['final_score']
            saved_rows.append({'query_id': qid, 'work_id': q['work_id'], 'chunk_id': cid,
                'dense_rank': c['rank'], 'dense_raw_score': c['similarity'],
                'dense_normalized_score': combined['faiss_norm'], 'raw_ce_score': raw[cid]['ce_score'],
                'ce_normalized_score': combined['normalized_rerank_score'],
                'evidence_raw_score': combined['evidence_score'], 'evidence_normalized_score': None,
                'dense_weighted_contribution': dw, 'ce_weighted_contribution': cw,
                'evidence_weighted_contribution': ew, 'final_composite_score': combined['final_score'],
                'raw_ce_rank': raw[cid]['ce_rank'], 'composite_rank': combined['composite_rank'],
                'accepted_overlap': any(overlaps(rt.chunks[cid], s) for s in q['accepted_passages'] if s['relevance_grade'] == 2),
                'text': all_texts[cid], 'evidence_signals': combined['evidence_signals'],
                'evidence_metrics_json': json.dumps({key: combined[key] for key in (
                    'actor_alignment', 'event_alignment', 'local_causal_score', 'speaker_score',
                    'first_person_narrative', 'motivation_strength', 'consequence_strength',
                    'motivation_priority', 'directional_subject_alignment', 'temporal_phase_alignment', 'polarity_alignment') if key in combined}, sort_keys=True),
                'CE_weights_sha256': rt.ce_info['model_weights_sha256'], 'G3_weights_sha256': rt.g3_info['weights_sha256'],
                'formula_fingerprint_sha256': formula['formula_fingerprint_sha256']})
    import pyarrow as pa
    pq.write_table(pa.Table.from_pylist(saved_rows), SCORES_K, compression='zstd')
    per_query, movement_counts, crossings = movements(rt.evaluable, system_metrics)
    pipeline_raw = retrieval_seconds+ce_seconds+raw_sort_seconds
    pipeline_composite = retrieval_seconds+ce_seconds+composite_total_seconds
    report = {'experiment': 'R0K', 'decision': decision_k(system_metrics), 'selection_policy': SELECTION_K,
        'result_label': 'EXPERIMENTAL / DESCRIPTIVE — frozen DRAFT DEV labels',
        'G3': rt.g3_info, 'CE': rt.ce_info, 'formula': formula, 'CE_package_sources': package,
        'environment': rt.environment, 'reproduction': {**reproduction, 'raw_CE_R0J_all_metrics_and_ranks_exact': True,
            'raw_CE_R0J_maximum_score_absolute_difference': maximum_score_delta,
            'CE_default_activation_is_Identity': True},
        'system_metrics': system_metrics, 'per_query_movement': per_query,
        'movement_counts': movement_counts, 'threshold_crossings': crossings,
        'timing': {'dense_retrieval_seconds': retrieval_seconds, 'raw_CE_seconds': ce_seconds,
            'raw_CE_sort_seconds': raw_sort_seconds, 'evidence_calculation_seconds': evidence_seconds,
            'composite_stage_seconds': composite_total_seconds,
            'composite_calculation_excluding_evidence_seconds': composite_total_seconds-evidence_seconds,
            'Dense60_RawCE_pipeline_seconds': pipeline_raw, 'Dense60_Composite_pipeline_seconds': pipeline_composite,
            'Dense60_RawCE_ms_per_query': 1000*pipeline_raw/29,
            'Dense60_Composite_ms_per_query': 1000*pipeline_composite/29,
            'composite_extra_ms_per_query': 1000*(pipeline_composite-pipeline_raw)/29,
            'shared_execution_seconds': execution_seconds, 'logical_CE_pairs_per_scored_system': 1740,
            'unique_scored_CE_pairs': len(set(pairs)), 'actual_scored_CE_pairs': len(pairs),
            'CE_scores_shared_exactly_between_B_and_C': True, 'warmup_pairs_separate': 16,
            'pipeline_note': 'Actual measured shared retrieval and CE stages; add measured raw sorting or composite stage respectively. No separate CE rerun or extrapolated cost.'},
        'memory': memory.result, 'CE_batch_size': rt.batch_size,
        'score_rows': len(saved_rows), 'score_parquet_sha256': sha(SCORES_K),
        'encoded_queries': rt.encoded, 'safety': verify_ledger(ledger),
        'TEST_evaluated': False, 'production_changed': False, 'labels_changed': False,
        'training_performed': False, 'downloads_performed': False, 'query_expansion_performed': False,
        'weights_tuned': False, 'candidate_policy_search': False, 'stop_after': 'R0K'}
    write(OUT_K, report)
    print(json.dumps({'decision': report['decision'], 'metrics': {name: {k:v for k,v in m.items() if k!='per_query'} for name,m in system_metrics.items()},
                     'movement_counts': movement_counts, 'threshold_crossings': crossings, 'timing': report['timing'],
                     'memory': memory.result, 'safety': report['safety']}, indent=2), flush=True)


if __name__ == '__main__': main()
