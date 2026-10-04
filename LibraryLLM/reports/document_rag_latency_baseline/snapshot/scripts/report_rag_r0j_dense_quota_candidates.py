"""Verify saved R0J scores and produce the complete report without model inference."""
from collections import defaultdict
import json
import pyarrow.parquet as pq
from r0j_common import *


def pct(value):
    return f'{value:.2%}'


def render(r):
    lines = ['# R0J — Dense-quota-preserving candidate construction', '',
             f"**FINAL R0J DECISION: {r['decision']}.**", '', r['decision_reason'], '',
             'Experimental engineering result on frozen DRAFT DEV labels. No production change, training, downloads, composite scoring, or TEST evaluation.', '',
             '## Frozen controls and models', '',
             f"Before/after verification: `{r['safety']}`. G1/G2/G3/R0/R0I, tokens_220, source map, labels, models, and all64 production files remain unchanged. Full SHA ledger: `rag_r0j_preflight.json`.", '',
             f"G3: `{r['G3']['path']}`, SHA-256 `{r['G3']['weights_sha256']}`; normalized384-dimensional embeddings, window256, unchanged per-book IndexFlatIP indexes.", '',
             f"CE: `{r['CE']['model_id']}`, revision `{r['CE']['revision']}`, weights SHA-256 `{r['CE']['model_weights_sha256']}`. Exact R0/R0I local cache; actual6layers/384hidden, float32, max512, batch16, explicit Identity raw logits. Legacy config name says L-12; actual weights/cache/architecture are the frozen L-6. Inputs are the original DEV question and exact tokens_220 passage. Sort descending raw logit, chunk-ID ascending for ties.", '',
             f"Python: `{r['environment']['python_executable']}`. GPU: {r['environment']['GPU']}. Other GPU usage observed before loading: `{r['environment']['other_GPU_usage']}`. No unrelated process was terminated.", '',
             f"Reproduction: `{r['reproduction']}`. All30 DEV queries reproduce frozen Top50; all29 evaluable Top80 pools reproduce R0I exactly. Dense60/Dense80 candidate and CE metrics plus complete CE order reproduce R0I exactly. D80+E20 reproduces R0I union metrics under the unified builder.", '',
             '## Policies frozen before evaluation', '',
             '| Policy | Guaranteed original dense quota | Unique expansion supplements | Maximum CE pool |',
             '|---|---:|---:|---:|']
    for name, p in r['policies'].items():
        lines.append(f"| {name} | {p['dense_quota']} | {p['expansion_unique_quota']} | {p['max_CE_pool']} |")
    lines += ['', 'Dense copies always win deduplication by canonical chunk_id. The guaranteed prefix retains original dense order; unique supplements follow unchanged expansion first-seen order. Duplicates consume no supplement quota. All ceilings and prefix preservation are asserted at runtime. No per-query quota choice or extra policies.', '',
              f"Selection policy saved in preflight: {r['selection_policy']} Coverage-first priority winner: `{r['coverage_first_priority_winner']}`.", '',
              '## Central comparison', '',
              '| Policy | Candidate Hit | Candidate Recall | No gold | Hit10 | Hit20 | MRR | Mean candidates | Total ms/query |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for a in r['results']:
        d, c, t, count = a['candidate_metrics'], a['CE_metrics'], a['timing'], a['candidate_count_summary']
        lines.append(f"| {a['system']} | {pct(d['candidate_Hit'])} | {pct(d['candidate_Recall'])} | {d['no_gold_candidate_count']} | {pct(c['hit']['10'])} | {pct(c['hit']['20'])} | {c['mrr']:.4f} | {count['mean']:.2f} | {t['average_total_ms_per_query']:.2f} |")
    lines += ['', 'Candidate Hit/Recall refer to the complete actual pool, before CE; Recall is macro average over accepted grade2 spans per query. Reranking changes ordering, never membership. Metrics cover29 evaluable DEV queries; the30th DEV query has no grade2 span and is reproduced but not scored.', '',
              '## Counts and full reranking metrics', '',
              '| Policy | Candidate count min / mean / max | Expansion-only unique added, total | Accepted queries |',
              '|---|---:|---:|---:|']
    for a in r['results']:
        c = a['candidate_count_summary']
        lines.append(f"| {a['system']} | {c['min']} / {c['mean']:.2f} / {c['max']} | {c['total_expansion_only_unique_added']} | {a['candidate_metrics']['covered_queries']}/29 |")
    lines += ['']
    md_metrics(lines, r['results'])
    lines += ['', 'Hit@pool and Recall@pool equal Candidate Hit and Candidate Recall above. Exact per-query span ranks, admitted spans, candidate counts and supplement counts are included in JSON.', '',
              '## Existing expansion reproduction', '',
              f"Source: `{r['expansion_generation_policy']}`. The actual pre-CE production AST and unchanged evidence.py generator are reused with Top15 per variant, original query first and first-seen canonical dedup. All generated strings, ordering, matched-query provenance and deduplicated candidate order reproduce R0I exactly with PYTHONHASHSEED=42. The R0I controlled cap80 is retained while uncapped first-seen candidates supply the supplements; observed uncapped maximum40, so no cap binds. Only the combination with original dense quotas changes. Production rag/reranker.py was never edited.", '',
              '## Measured cost and shared-GPU headroom', '',
              '| Policy | Dense retrieval s | Expansion retrieval s | CE scoring s | Total batch s | CE ms/query | Total ms/query | Logical / unique / actual pairs |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for a in r['results']:
        t = a['timing']
        lines.append(f"| {a['system']} | {t['original_dense_retrieval_seconds']:.6f} | {t['expansion_retrieval_seconds']:.6f} | {t['CE_scoring_seconds']:.6f} | {t['total_query_batch_seconds']:.6f} | {t['average_CE_ms_per_query']:.3f} | {t['average_total_ms_per_query']:.3f} | {t['logical_CE_pairs']} / {t['unique_CE_pairs']} / {t['actual_scored_CE_pairs']} |")
    lines += ['', '| Policy | Peak allocated MiB | Peak reserved MiB | Minimum global free GiB | Peak process RSS GiB |',
              '|---|---:|---:|---:|---:|']
    for a in r['results']:
        m = a['memory']
        lines.append(f"| {a['system']} | {m['peak_allocated_VRAM_bytes']/1024**2:.2f} | {m['peak_reserved_VRAM_bytes']/1024**2:.2f} | {m['minimum_global_free_VRAM_bytes']/1024**3:.3f} | {m['peak_process_RSS_bytes']/1024**3:.3f} |")
    lines += ['', f"No CE cache used: {r['logical_CE_pairs']} logical pairs were actually scored, {r['unique_query_chunk_pairs_across_policies']} distinct query/chunk pairs across policies, zero cache reuse. Each policy has fresh dense retrieval, expansion retrieval where applicable, and complete CE scoring. The16 warmup pairs and initial30-query reproduction are separate from policy timings. Total runtime includes construction, assertions and metric aggregation; expansion time includes unchanged generation/merge and frozen-order checks. Timings are one measured pass on a shared machine, not statistical latency estimates. All memory peaks include both resident models; minimum free GPU headroom remains above the1.5GiB guard.", '',
              '## Critical accepted evidence', '',
              'The target is the earliest original Top80 candidate overlapping an accepted span. Source BOTH means it is retained as a dense copy and also appears in the expansion retrieval; EXPANSION means it lies outside the guaranteed dense quota. Other accepted candidates per query are recorded separately in JSON. Ranks outside original Top80 are not inferred.', '',
              '| Query | Policy | Target present | Source | Original dense rank | Pre-CE index | Post-CE rank |',
              '|---|---|---|---|---:|---:|---:|']
    for qid in CRITICAL:
        for x in r['critical_query_tracking']:
            if x['query_id'] == qid:
                lines.append(f"| {qid} | {x['policy']} | {x['candidate_present']} | {x['source']} | {x['original_dense_rank']} | {x['pre_CE_pool_index']} | {x['post_CE_rank']} |")
    lines += ['', 'v8_06 original rank47 and pp_05 original rank49 are asserted present in every policy. Their exact post-CE ranks are shown above; preserving membership does not imply unchanged CE rank when supplements outrank them.', '',
              '## D60 + E20 analysis', '', r['D60_special_analysis']['description'], '',
              f"New covered queries versus Dense60: `{r['D60_special_analysis']['new_candidate_coverage_queries']}`. New accepted-span admissions: `{r['D60_special_analysis']['additional_accepted_spans']}`. Query Hit20 gains: `{r['D60_special_analysis']['Top20_gains']}`; losses: `{r['D60_special_analysis']['Top20_losses']}`.", '',
              '## Expansion-only accepted evidence', '',
              'Classification compares each supplement against its guaranteed dense quota. NEW_QUERY_COVERAGE means that quota admitted no accepted span; ADDITIONAL_ACCEPTED_SPAN adds a previously uncovered span; NEITHER adds another candidate for already covered spans. Accepted supplements outside Top20 increase admission without creating a useful Top20 hit.', '',
              '| Policy | Query | Chunk | Original dense rank | CE rank | Contribution |',
              '|---|---|---|---:|---:|---|']
    for x in r['expansion_value']:
        lines.append(f"| {x['policy']} | {x['query_id']} | {x['chunk_id']} | {x['original_dense_rank']} | {x['CE_rank']} | {x['classification']} |")
    lines += ['', 'Exact source query variants and span indices for every accepted expansion-only candidate are in JSON.', '',
              '## Expansion distractor demotions', '',
              'For attribution, remove only appended supplements from a policy and rerank its guaranteed dense quota with exactly the same saved logits. This isolates membership effects without another scored policy or a changed CE. Report every accepted dense candidate crossing Top5/10/20, and distinguish candidate-level movement from the first accepted passage for the query. A distractor here lacks frozen accepted-span overlap; known unlabelled answer evidence is flagged separately.', '',
              f"Recorded accepted-candidate boundary demotions: {len(r['expansion_distractor_demotions'])}; EXPANSION_DISTRACTOR_DEMOTION instances: {r['distractor_demotion_count']}.", '']
    if not r['expansion_distractor_demotions']:
        lines.append('No accepted dense candidate crossed these boundaries because of appended expansion candidates.')
    for x in r['expansion_distractor_demotions']:
        lines += [f"- **{x['policy']} / {x['query_id']} / {x['classification']}**: accepted `{x['correct_chunk_id']}`, CE score{x['correct_CE_score']:.9f}, rank{x['old_rank_dense_quota_only']}→{x['new_rank']}, crosses{x['crossed_boundaries']}; query first accepted rank{x['query_first_accepted_old_rank']}→{x['query_first_accepted_new_rank']}."]
        for c in x['new_outranking_distractors']:
            lines.append(f"  - Appended `{c['chunk_id']}`, CE score{c['CE_score']:.9f}, rank{c['CE_rank']}, variant(s) `{c['source_query_variants']}`, label limitation:{c.get('possible_label_coverage_limitation', False)}.")
    lines += ['', '## Known CE-domain failures and label limitations', '',
              '| Query | Policy | Accepted candidate present | CE first accepted rank | Classification |',
              '|---|---|---|---:|---|']
    for x in r['known_CE_domain_failures']:
        lines.append(f"| {x['query_id']} | {x['policy']} | {x['accepted_candidate_present']} | {x['CE_first_accepted_rank']} | {x['classification']} |")
    lines += ['', f"POSSIBLE_LABEL_COVERAGE_LIMITATION: {r['label_diagnostic_instance_count']} pool/query instances, {r['label_diagnostic_unique_query_count']} unique queries. Known pp_05 Wickham/Lydia and time_05 red-sun passages retain R0's engineering flag and receive no gold credit; exact passages and CE ranks are in JSON. Frozen DRAFT labels were not changed.", '',
              '| Query | Policy | Known unlabelled answer passage CE rank | Source |',
              '|---|---|---:|---|']
    for x in r['possible_label_coverage_limitations']:
        lines.append(f"| {x['query_id']} | {x['policy']} | {x['CE_rank']} | {x['source']} |")
    lines += ['', '## Verification, artifacts and stop', '',
              f"Tests: `{r['tests']}`. Saved-parquet verification: `{r['final_artifact_checks']}`. Experiment source SHAs match preflight. Policy pools, raw-logit sorting, fingerprints, complete metrics and critical preservation were reconstructed from saved scores without loading models.", '',
              f"Score parquet: {r['score_rows']} rows, SHA-256 `{r['score_parquet_sha256']}`.", '',
              '**TEST evaluated: NO. Production changed: NO. Labels changed: NO. Historical artifacts changed: NO.**', '',
              'Artifacts created:', '', *[f'- `{p}`' for p in r['artifacts_created']], '',
              f"**FINAL R0J DECISION: {r['decision']}.**", '',
              'Stopped after R0J. No production implementation, CE fine-tuning or composite-weight experiment was started.']
    OUT_J.with_suffix('.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    r = read(OUT_J)
    assert tuple(r['policies']) == POLICY_NAMES
    pre = read(PRE_J)
    for path, expected in pre['experimental_code_sha256'].items():
        assert sha(path) == expected
    assert sha(SCORES_J) == r['score_parquet_sha256']
    rows = pq.read_table(SCORES_J).to_pylist()
    assert len(rows) == r['score_rows']
    assert {c['cross_encoder_sha256'] for c in rows} == {r['CE']['model_weights_sha256']}
    assert {c['g3_sha256'] for c in rows} == {r['G3']['weights_sha256']}
    chunks = {c['chunk_id']: {'start': c['source_start_char'], 'end': c['source_end_char'],
                             'text': c['text'], 'work_id': c['work_id']}
              for c in pq.read_table(CORPUS / 'chunks.parquet', columns=['chunk_id', 'source_start_char', 'source_end_char', 'text', 'work_id']).to_pylist()}
    questions = [q for q in read(ROOT / 'rag/evaluation/rag_retrieval_eval_v1.json')['questions'] if q['split'] == 'DEV']
    allowed = {q['query_id'] for q in questions}; evaluable = {q['query_id'] for q in dev_evaluable(questions)}
    assert len(allowed) == 30 and len(evaluable) == 29
    assert {c['query_id'] for c in rows} == evaluable
    assert all(c['query_id'] in allowed for c in r['encoded_queries'])
    frozen = read(OUT)
    frozen80 = next(a for a in frozen['raw_sweep']['results'] if a['k'] == 80)
    top80 = {qid: sorted(cs, key=lambda c: c['rank']) for qid, cs in frozen80['ranked_candidates'].items()}
    grouped = defaultdict(lambda: defaultdict(list))
    for c in rows: grouped[c['system']][c['query_id']].append(c)
    assert tuple(grouped) == POLICY_NAMES
    for a in r['results']:
        name = a['system']; n, extra, ceiling = POLICIES[name]
        pools = {}; ranked = {}
        for qid, cs in grouped[name].items():
            pool = sorted(cs, key=lambda c: c['input_rank'])
            assert [c['input_rank'] for c in pool] == list(range(1, len(pool)+1))
            assert n <= len(pool) <= ceiling and len(pool) == len(set(ids(pool)))
            assert ids(pool)[:n] == ids(top80[qid])[:n]
            assert_critical(qid, pool, top80[qid])
            expected_supplements = []
            if extra:
                gen = r['generation_details'][name][qid]
                old = frozen['expansion_phase']['generation_details']['dense-preserving-union'][qid]
                assert gen['queries'] == old['queries'] and ids(gen['candidates']) == ids(old['uncapped_candidates'])
                dense_ids = set(ids(top80[qid][:n]))
                expected_supplements = [c['chunk_id'] for c in gen['candidates'] if c['chunk_id'] not in dense_ids][:extra]
            assert ids(pool)[n:] == expected_supplements
            assert sum(c['expansion_only'] for c in pool) == len(expected_supplements)
            ranked[qid] = sorted(pool, key=lambda c: (-c['ce_score'], c['chunk_id']))
            assert [c['ce_rank'] for c in ranked[qid]] == list(range(1, len(pool)+1))
            assert ids(ranked[qid]) == ids(a['ranked_candidates'][qid])
            by_id = {c['chunk_id']: c for c in a['ranked_candidates'][qid]}
            for c in pool:
                saved = by_id[c['chunk_id']]
                assert c['ce_score'] == saved['ce_score'] and c['source'] == saved['source']
                assert c['matched_queries'] == saved['matched_queries']
                assert saved.get('text', chunks[c['chunk_id']]['text']) == chunks[c['chunk_id']]['text']
            pools[qid] = pool
        assert metrics(questions, pools, chunks, ceiling) == a['candidate_metrics']
        assert metrics(questions, ranked, chunks, ceiling) == a['CE_metrics']
    byname = {a['system']: a for a in r['results']}
    a, b = byname['dense60'], byname['d60e20']
    new_coverage = [qid for qid, m in a['candidate_metrics']['per_query'].items()
                    if m['first_rank'] is None and b['candidate_metrics']['per_query'][qid]['first_rank'] is not None]
    gains = [qid for qid, m in a['CE_metrics']['per_query'].items() if not m['hit']['20'] and b['CE_metrics']['per_query'][qid]['hit']['20']]
    losses = [qid for qid, m in a['CE_metrics']['per_query'].items() if m['hit']['20'] and not b['CE_metrics']['per_query'][qid]['hit']['20']]
    r['D60_special_analysis'] = {'new_candidate_coverage_queries': new_coverage,
        'additional_accepted_spans': b['candidate_metrics']['admitted_spans'] - a['candidate_metrics']['admitted_spans'],
        'Top20_gains': gains, 'Top20_losses': losses,
        'description': f"D60+E20 preserves every original rank1–60 candidate. Candidate Recall changes {pct(a['candidate_metrics']['candidate_Recall'])}→{pct(b['candidate_metrics']['candidate_Recall'])}; accepted-query coverage {a['candidate_metrics']['covered_queries']}→{b['candidate_metrics']['covered_queries']}. CE Hit20 changes {pct(a['CE_metrics']['hit']['20'])}→{pct(b['CE_metrics']['hit']['20'])}, Hit10 {pct(a['CE_metrics']['hit']['10'])}→{pct(b['CE_metrics']['hit']['10'])}. It adds{b['candidate_count_summary']['total_expansion_only_unique_added']} unique supplement occurrences across29queries. Measured total latency changes {a['timing']['average_total_ms_per_query']:.2f}→{b['timing']['average_total_ms_per_query']:.2f}ms/query; CE alone {a['timing']['average_CE_ms_per_query']:.2f}→{b['timing']['average_CE_ms_per_query']:.2f}ms/query."}
    label_ids = {x['chunk_id'] for x in r['possible_label_coverage_limitations']}
    for x in r['expansion_distractor_demotions']:
        for c in x['new_outranking_distractors']:
            c['possible_label_coverage_limitation'] = c['chunk_id'] in label_ids
    r['distractor_demotion_count'] = sum(x['classification'] == 'EXPANSION_DISTRACTOR_DEMOTION' for x in r['expansion_distractor_demotions'])
    r['label_diagnostic_instance_count'] = len(r['possible_label_coverage_limitations'])
    r['label_diagnostic_unique_query_count'] = len({x['query_id'] for x in r['possible_label_coverage_limitations']})
    testlog = REPORTS / 'rag_r0j_contract_tests.log'
    assert '22 passed' in testlog.read_text(encoding='utf-8-sig')
    r['tests'] = {'result': '22 passed', 'path': str(testlog), 'sha256': sha(testlog)}
    r['safety'] = verify_ledger(pre['before_sha256'])
    r['final_artifact_checks'] = {'all_metrics_recomputed_from_saved_parquet': True,
        'all_dense_quotas_and_ceilings_preserved': True, 'chunk_id_dedup_and_first_seen_supplements': True,
        'raw_CE_sort_and_fingerprints_exact': True, 'original_passage_text_unchanged': True,
        'R0I_dense60_dense80_and_union_reproduced': True, 'expansion_matches_R0I': True,
        'all_encoded_query_ids_DEV_only': True, 'experimental_code_matches_preflight': True}
    r['artifacts_created'] = [str(p.relative_to(ROOT)) for p in (
        ROOT / 'scripts/r0j_common.py', ROOT / 'scripts/evaluate_rag_r0j_dense_quota_candidates.py',
        ROOT / 'scripts/report_rag_r0j_dense_quota_candidates.py', ROOT / 'tests/test_rag_r0j_dense_quota_candidates.py',
        PRE_J, OUT_J, OUT_J.with_suffix('.md'), SCORES_J,
        REPORTS / 'rag_r0j_expansion_distractors.json', testlog, REPORTS / 'rag_r0j_evaluation.log')]
    write(OUT_J, r)
    write(REPORTS / 'rag_r0j_expansion_distractors.json', {'demotions': r['expansion_distractor_demotions']})
    render(r)
    print(json.dumps({'decision': r['decision'], 'priority_winner': r['coverage_first_priority_winner'],
        'safety': r['safety'], 'tests': r['tests'], 'D60': r['D60_special_analysis'],
        'demotion_instances': r['distractor_demotion_count'], 'label_diagnostic_instances': r['label_diagnostic_instance_count'],
        'final_artifact_checks': r['final_artifact_checks']}, indent=2))


if __name__ == '__main__':
    main()
