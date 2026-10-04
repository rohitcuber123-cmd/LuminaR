"""Six frozen dense-quota policies, unchanged expansion, exact local G3 and raw CE."""
import argparse
import json
import time
from r0j_common import *


def checked_generation(rt, q, frozen):
    gen, policy = generation(rt, q, 80)
    old = frozen['expansion_phase']['generation_details']['dense-preserving-union'][q['query_id']]
    assert gen['retrieval_queries'] == old['queries'], 'Expansion query strings/order differ; STOP'
    assert ids(gen['uncapped_candidates']) == ids(old['uncapped_candidates']), 'Expansion order differs; STOP'
    for new, previous in zip(gen['uncapped_candidates'], old['uncapped_candidates']):
        assert new['matched_queries'] == previous['matched_queries']
        assert new['text'] == previous['text'] == rt.chunks[new['chunk_id']]['text']
    return gen, policy


def summarize(rt, results, top80, generation_details):
    tracking = []
    expansion_value = []
    demotions = []
    subset_metrics = {}
    qmap = {q['query_id']: q for q in rt.evaluable}
    for result in results:
        name = result['system']
        n, extra, _ = POLICIES[name]
        subsets = {}
        for qid, ranked in result['ranked_candidates'].items():
            q = qmap[qid]
            prece = sorted(ranked, key=lambda c: c['rank'])
            dense = prece[:n]
            subsets[qid] = rerank(dense, [c['ce_score'] for c in dense])
            covered_spans = set(i for c in dense for i in accepted_indices(q, c, rt.chunks))
            rank_by_id = {c['chunk_id']: c['rank'] for c in top80[qid]}
            if qid in CRITICAL:
                targets = [c for c in top80[qid] if accepted_indices(q, c, rt.chunks)]
                target = targets[0] if targets else None
                found = next((c for c in ranked if target and c['chunk_id'] == target['chunk_id']), None)
                tracking.append({'policy': name, 'query_id': qid,
                    'target_chunk_id': target['chunk_id'] if target else None,
                    'original_dense_rank': target['rank'] if target else None,
                    'candidate_present': found is not None, 'source': found['source'] if found else None,
                    'pre_CE_pool_index': found['rank'] if found else None,
                    'post_CE_rank': found['ce_rank'] if found else None,
                    'all_accepted_candidates': [{ 'chunk_id': c['chunk_id'], 'source': c['source'],
                        'original_dense_rank': rank_by_id.get(c['chunk_id']),
                        'pre_CE_pool_index': c['rank'], 'post_CE_rank': c['ce_rank']}
                        for c in ranked if accepted_indices(q, c, rt.chunks)]})
            for c in ranked:
                if not c['expansion_only']:
                    continue
                spans = accepted_indices(q, c, rt.chunks)
                if spans:
                    kind = ('NEW_QUERY_COVERAGE' if not covered_spans else
                            'ADDITIONAL_ACCEPTED_SPAN' if set(spans) - covered_spans else 'NEITHER')
                    expansion_value.append({'policy': name, 'query_id': qid,
                        'expansion_query_variants': c['matched_queries'], 'chunk_id': c['chunk_id'],
                        'original_dense_rank': rank_by_id.get(c['chunk_id']),
                        'dense_rank_note': 'outside guaranteed quota; rank within original Top80' if c['chunk_id'] in rank_by_id else 'not in original Top80; deeper rank not measured',
                        'CE_rank': c['ce_rank'], 'accepted_span_indices': spans,
                        'new_span_indices_vs_dense_quota': sorted(set(spans) - covered_spans),
                        'classification': kind})
            # Causal subset comparison: remove supplements, reuse exactly the same logits.
            # No extra scored policy and no mixed scoring are introduced.
            if extra:
                old_by_id = {c['chunk_id']: c for c in subsets[qid]}
                for correct in ranked:
                    if correct['chunk_id'] not in old_by_id or not accepted_indices(q, correct, rt.chunks):
                        continue
                    old_rank = old_by_id[correct['chunk_id']]['ce_rank']
                    boundaries = [k for k in (5, 10, 20) if old_rank <= k < correct['ce_rank']]
                    if not boundaries:
                        continue
                    outrankers = [c for c in ranked if c['expansion_only'] and c['ce_rank'] < correct['ce_rank']]
                    distractors = [c for c in outrankers if not accepted_indices(q, c, rt.chunks)]
                    demotions.append({'policy': name, 'query_id': qid,
                        'classification': 'EXPANSION_DISTRACTOR_DEMOTION' if distractors else 'ACCEPTED_SUPPLEMENT_DISPLACEMENT',
                        'correct_chunk_id': correct['chunk_id'], 'correct_CE_score': correct['ce_score'],
                        'old_rank_dense_quota_only': old_rank, 'new_rank': correct['ce_rank'],
                        'crossed_boundaries': boundaries,
                        'query_first_accepted_old_rank': min((c['ce_rank'] for c in subsets[qid] if accepted_indices(q, c, rt.chunks)), default=None),
                        'query_first_accepted_new_rank': result['CE_metrics']['per_query'][qid]['first_rank'],
                        'new_outranking_distractors': [{'chunk_id': c['chunk_id'], 'CE_score': c['ce_score'],
                            'source_query_variants': c['matched_queries'], 'CE_rank': c['ce_rank']}
                            for c in distractors],
                        'accepted_supplement_outrankers': [c['chunk_id'] for c in outrankers if accepted_indices(q, c, rt.chunks)],
                        'label_caveat': 'Distractor means no frozen accepted-span overlap; it does not prove semantic irrelevance.'})
        subset_metrics[name] = metrics(rt.evaluable, subsets, rt.chunks, n)
    label_notes = []
    known = {'pp_05': 'OL66524W__tokens_220__d4ff028b2f8aa974',
             'time_05': 'OL27039837W__tokens_220__2928e5046c948f13'}
    for r in results:
        for qid, cid in known.items():
            found = next((c for c in r['ranked_candidates'][qid] if c['chunk_id'] == cid), None)
            if found:
                assert not accepted_indices(qmap[qid], found, rt.chunks)
                label_notes.append({'policy': r['system'], 'query_id': qid, 'chunk_id': cid,
                    'CE_rank': found['ce_rank'], 'source': found['source'],
                    'classification': 'POSSIBLE_LABEL_COVERAGE_LIMITATION',
                    'text': rt.chunks[cid]['text'], 'reason': 'Carried-forward R0 source-inspected answer evidence outside frozen accepted spans; no gold credit.'})
    domain = []
    for qid in ('v8_08', 'pp_02', 'time_01'):
        for r in results:
            m = r['CE_metrics']['per_query'][qid]
            domain.append({'policy': r['system'], 'query_id': qid, 'accepted_candidate_present': m['first_rank'] is not None,
                           'CE_first_accepted_rank': m['first_rank'],
                           'classification': 'RERANKER_DOMAIN_FAILURE' if m['first_rank'] is not None and m['first_rank'] > 20 else
                           'CANDIDATE_CONSTRUCTION_FAILURE' if m['first_rank'] is None else 'ACCEPTED_EVIDENCE_IN_TOP20'})
    return {'critical_query_tracking': tracking, 'expansion_value': expansion_value,
            'expansion_distractor_demotions': demotions, 'dense_quota_same_logit_subset_metrics': subset_metrics,
            'possible_label_coverage_limitations': label_notes, 'known_CE_domain_failures': domain}


def decide(results):
    winner = max(results, key=priority)
    baseline = next(r for r in results if r['system'] == 'dense60')
    name = winner['system']
    useful_new = [qid for qid, m in winner['CE_metrics']['per_query'].items()
                  if m['hit']['20'] and not baseline['CE_metrics']['per_query'][qid]['hit']['20']]
    if winner['CE_metrics']['hit']['20'] < baseline['CE_metrics']['hit']['20'] and not useful_new:
        decision = 'G. R0J MIXED / INCONCLUSIVE'
        reason = ('The coverage-first winner adds accepted candidate coverage but no new Top20 query '
                  'and has worse CE Hit20 than dense60. The experiment does not establish that its '
                  'extra retrieval/CE cost is justified.')
    elif name == 'dense60':
        decision = 'F. EXPANSION PROVIDES NO USEFUL VALUE ON TOP OF PRESERVED DENSE RETRIEVAL'
        reason = 'Dense60 wins the frozen coverage/CE quality/cost priority; no expansion policy improves that tradeoff.'
    else:
        decisions = {'d60e20': 'A. DENSE60 + EXPANSION20 IS THE BEST CANDIDATE CONSTRUCTION',
                     'd50e30': 'B. DENSE50 + EXPANSION30 IS THE BEST CANDIDATE CONSTRUCTION',
                     'd70e10': 'C. DENSE70 + EXPANSION10 IS THE BEST CANDIDATE CONSTRUCTION',
                     'dense80': 'D. DENSE80 WITHOUT EXPANSION IS BETTER',
                     'd80e20': 'E. DENSE80 + EXPANSION20 JUSTIFIES THE EXTRA COST'}
        decision = decisions[name]
        reason = 'This policy wins the frozen coverage-first priority, followed by CE Hit20/Hit10, no-gold, measured CE latency and MRR; descriptive DEV result only.'
    return {'decision': decision, 'coverage_first_priority_winner': name,
            'new_Top20_queries_vs_dense60': useful_new, 'decision_reason': reason}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--policies', required=True, choices=[','.join(POLICY_NAMES)])
    p.add_argument('--retriever', required=True, choices=['g3'])
    p.add_argument('--cross-encoder', required=True, choices=[MODEL_ID])
    p.add_argument('--raw-cross-encoder-only', required=True, action='store_true')
    p.add_argument('--split', required=True, choices=['dev'])
    p.parse_args()
    assert os.environ.get('PYTHONHASHSEED') == '42', 'Use R0I process hash seed42 to reproduce expansion order'
    for path in (OUT_J, SCORES_J, PRE_J):
        if path.exists():
            raise FileExistsError(f'R0J artifact exists; inspect before any rerun: {path}')
    ledger, r0, r0i = freeze_j()
    frozen_policy = {k: {'dense_quota': n, 'expansion_unique_quota': e, 'max_CE_pool': cap}
                     for k, (n, e, cap) in POLICIES.items()}
    write(PRE_J, {'before_sha256': ledger, 'policies': frozen_policy, 'selection_policy': SELECTION,
                 'hash_seed': '42', 'CE_cache_enabled': False, 'warmup_pairs': 16,
                 'experimental_code_sha256': {str(ROOT / 'scripts' / name): sha(ROOT / 'scripts' / name)
                    for name in ('r0j_common.py', 'evaluate_rag_r0j_dense_quota_candidates.py')},
                 'TEST_evaluated': False})
    rt = Runtime(r0)
    top80, reproduction = reproduce(rt, r0)
    frozen80 = next(r for r in r0i['raw_sweep']['results'] if r['k'] == 80)
    for q in rt.evaluable:
        qid = q['query_id']
        assert ids(top80[qid]) == ids(sorted(frozen80['ranked_candidates'][qid], key=lambda c: c['rank'])), 'R0I Top80 differs; STOP'
    reproduction.update(exact_R0I_Top80_ID_match=True, Top80_comparison_queries=len(rt.evaluable),
                        non_evaluable_DEV_note='Frozen R0I has Top80 pools for 29 evaluable queries; all30 reproduce frozen Top50.')
    rt.warm(top80)
    results, score_rows, details = [], [], {}
    for name, (n, extra, ceiling) in POLICIES.items():
        dense_seconds = expansion_seconds = construction_seconds = 0.
        info, pools = {}, {}
        with Memory(rt.torch, rt.psutil) as memory:
            rt.torch.cuda.synchronize()
            start = time.perf_counter()
            for q in rt.evaluable:
                qid = q['query_id']
                rt.torch.cuda.synchronize(); t = time.perf_counter()
                dense = rt.retrieve(q, n)
                rt.torch.cuda.synchronize(); dense_seconds += time.perf_counter() - t
                assert ids(dense) == ids(top80[qid][:n]), 'Fresh dense quota differs; STOP'
                expansion = []
                if extra:
                    rt.torch.cuda.synchronize(); t = time.perf_counter()
                    gen, policy = checked_generation(rt, q, r0i)
                    rt.torch.cuda.synchronize(); expansion_seconds += time.perf_counter() - t
                    expansion = gen['uncapped_candidates']
                    info[qid] = {'queries': gen['retrieval_queries'], 'candidates': expansion}
                t = time.perf_counter()
                # Dense Top80 is a frozen rank lookup, not part of scored pool outside quota.
                pool = build_pool(top80[qid], expansion, name)
                assert ids(pool)[:n] == ids(dense)
                assert_critical(qid, pool, top80[qid])
                for c in pool:
                    assert c.get('text', rt.chunks[c['chunk_id']]['text']) == rt.chunks[c['chunk_id']]['text']
                pools[qid] = pool
                construction_seconds += time.perf_counter() - t
            rt.torch.cuda.synchronize()
            retrieval_seconds = time.perf_counter() - start
            result, rows = evaluate_pool(rt, pools, ceiling, name, retrieval_seconds, start)
        result['memory'] = memory.result
        result['policy'] = frozen_policy[name]
        result['timing'].update(original_dense_retrieval_seconds=dense_seconds,
             expansion_retrieval_seconds=expansion_seconds, construction_assertion_seconds=construction_seconds,
             average_total_ms_per_query=1000 * result['timing']['total_query_batch_seconds'] / len(rt.evaluable),
             cache_reuse_count=0, CE_cache_enabled=False)
        counts = list(result['candidate_counts_by_query'].values())
        added = {qid: sum(c['expansion_only'] for c in pool) for qid, pool in pools.items()}
        result['candidate_count_summary'] = {'min': min(counts), 'mean': statistics.mean(counts), 'max': max(counts),
              'total_expansion_only_unique_added': sum(added.values()), 'expansion_only_added_by_query': added}
        by_pair = {(qid, c['chunk_id']): c for qid, candidates in result['ranked_candidates'].items() for c in candidates}
        for row in rows:
            c = by_pair[(row['query_id'], row['chunk_id'])]
            row.update(source=c['source'], expansion_only=c['expansion_only'],
                       matched_queries=c['matched_queries'], dense_quota=n, expansion_quota=extra)
        if name in ('dense60', 'dense80'):
            previous = next(r for r in r0i['raw_sweep']['results'] if r['k'] == n)
            assert result['candidate_metrics'] == previous['candidate_metrics'], 'R0I baseline candidate metrics differ; STOP'
            assert result['CE_metrics'] == previous['CE_metrics'], 'R0I baseline CE metrics differ; STOP'
            assert all(ids(result['ranked_candidates'][qid]) == ids(previous['ranked_candidates'][qid]) for qid in pools)
            old_scores = {(qid, c['chunk_id']): c['ce_score'] for qid, candidates in previous['ranked_candidates'].items() for c in candidates}
            result['R0I_baseline_reproduction'] = {'all_metrics_and_ranks_exact': True,
                'maximum_CE_score_absolute_difference': max(abs(c['ce_score'] - old_scores[key]) for key, c in by_pair.items())}
        if name == 'd80e20':
            previous = next(r for r in r0i['expansion_phase']['results'] if r['system'] == 'dense-preserving-union')
            previous_pools = {qid: sorted(rows, key=lambda c: c['rank']) for qid, rows in previous['ranked_candidates'].items()}
            assert result['candidate_metrics'] == metrics(rt.evaluable, previous_pools, rt.chunks, ceiling)
            assert result['CE_metrics'] == metrics(rt.evaluable, previous['ranked_candidates'], rt.chunks, ceiling)
            result['R0I_union_metrics_reproduced'] = True
        results.append(result); score_rows.extend(rows); details[name] = info
        print(json.dumps({'policy': name, 'candidate_counts': result['candidate_count_summary'],
            'candidate_Recall': result['candidate_metrics']['candidate_Recall'],
            'covered': result['candidate_metrics']['covered_queries'], 'MRR': result['CE_metrics']['mrr'],
            'Hit10': result['CE_metrics']['hit']['10'], 'Hit20': result['CE_metrics']['hit']['20'],
            'timing': result['timing'], 'memory': result['memory']}), flush=True)
    analysis = summarize(rt, results, top80, details)
    decision = decide(results)
    import pyarrow as pa
    import pyarrow.parquet as pq
    pq.write_table(pa.Table.from_pylist(score_rows), SCORES_J, compression='zstd')
    report = {'experiment': 'R0J', 'result_label': 'EXPERIMENTAL / DESCRIPTIVE — DRAFT DEV labels',
              **decision, 'selection_policy': SELECTION, 'policies': frozen_policy,
              'G3': rt.g3_info, 'CE': rt.ce_info, 'environment': rt.environment,
              'reproduction': reproduction, 'expansion_generation_policy': policy,
              'expansion_generation_matches_R0I_exactly': True,
              'results': results, 'generation_details': details, **analysis,
              'safety': verify_ledger(ledger), 'score_parquet_sha256': sha(SCORES_J),
              'score_rows': len(score_rows), 'score_path': str(SCORES_J),
              'encoded_queries': rt.encoded, 'CE_cache_enabled': False,
              'logical_CE_pairs': len(score_rows), 'actual_scored_CE_pairs': len(score_rows),
              'unique_query_chunk_pairs_across_policies': len({(r['query_id'], r['chunk_id']) for r in score_rows}),
              'cache_reuse_count': 0, 'TEST_evaluated': False, 'production_changed': False,
              'labels_changed': False, 'training_performed': False, 'downloads_performed': False,
              'stop_after': 'R0J', 'warmup_pairs_separately_reported': 16}
    write(OUT_J, report)
    write(REPORTS / 'rag_r0j_expansion_distractors.json', {'demotions': analysis['expansion_distractor_demotions']})
    print('FINAL', report['decision'], flush=True)


if __name__ == '__main__':
    main()
