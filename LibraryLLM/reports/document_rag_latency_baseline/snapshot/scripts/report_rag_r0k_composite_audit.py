"""Validate saved component scores and audit movements without encoding or model loading."""
from collections import defaultdict
import json
import numpy as np
import pyarrow.parquet as pq
from r0k_common import *

COMPONENTS = {'CE': 'ce_weighted_contribution', 'evidence': 'evidence_weighted_contribution', 'dense': 'dense_weighted_contribution'}
KNOWN_LABEL_IDS = {'pp_05': 'OL66524W__tokens_220__d4ff028b2f8aa974',
                   'time_05': 'OL27039837W__tokens_220__2928e5046c948f13'}


def breakdown(c):
    return {k: c[k] for k in ('chunk_id', 'text', 'dense_rank', 'dense_raw_score', 'dense_normalized_score',
        'raw_ce_rank', 'raw_ce_score', 'ce_normalized_score', 'evidence_raw_score',
        'ce_weighted_contribution', 'evidence_weighted_contribution', 'dense_weighted_contribution',
        'final_composite_score', 'composite_rank', 'accepted_overlap', 'evidence_signals', 'evidence_metrics_json')}


def pair_attribution(winner, loser, benefit=False):
    deltas = {name: winner[field]-loser[field] for name, field in COMPONENTS.items()}
    assert winner['composite_rank'] < loser['composite_rank']
    evidence, dense = deltas['evidence'] > 0, deltas['dense'] > 0
    if evidence and dense: root = 'MULTI_COMPONENT'
    elif evidence: root = 'EVIDENCE_HEURISTIC'
    elif dense: root = 'DENSE_SCORE'
    else: root = 'UNCLEAR'
    return {'classification': root + ('_RECOVERY' if benefit else '_DISTRACTOR') if root != 'UNCLEAR' else root,
            'winner_minus_loser_weighted_terms': deltas,
            'composite_margin': winner['final_composite_score']-loser['final_composite_score'],
            'exact_composite_tie': winner['final_composite_score'] == loser['final_composite_score'],
            'attribution_rule': 'Signs of actual pairwise evidence/dense weighted margins that reverse raw CE order; not a tuned weight or an ablation experiment.'}


def movement_cases(r, grouped):
    harm, benefit = [], []
    for movement in r['per_query_movement']:
        delta = movement['raw_CE_to_composite_first_accepted_rank_delta']
        if delta is None or abs(delta) < 5: continue
        cs = grouped[movement['query_id']]
        corrects = [c for c in cs if c['accepted_overlap']]
        is_benefit = delta < 0
        target = min(corrects, key=lambda c: c['composite_rank'] if is_benefit else c['raw_ce_rank'])
        if is_benefit:
            jumped = [c for c in cs if c['raw_ce_rank'] < target['raw_ce_rank'] and c['composite_rank'] > target['composite_rank']]
            pairs = [{**breakdown(c), **pair_attribution(target, c, True)} for c in sorted(jumped, key=lambda c:c['raw_ce_rank'])]
        else:
            jumped = [c for c in cs if c['raw_ce_rank'] > target['raw_ce_rank'] and c['composite_rank'] < target['composite_rank']]
            pairs = [{**breakdown(c), **pair_attribution(c, target)} for c in sorted(jumped, key=lambda c:c['composite_rank'])]
        for c in pairs:
            c['possible_label_coverage_limitation'] = c['chunk_id'] == KNOWN_LABEL_IDS.get(movement['query_id'])
        classes = {c['classification'] for c in pairs}
        overall = (next(iter(classes)) if len(classes)==1 else
                   'MULTI_COMPONENT_RECOVERY' if is_benefit else 'MULTI_COMPONENT_DISTRACTOR') if pairs else 'UNCLEAR'
        case = {**movement, 'classification': overall, 'target_accepted_candidate': breakdown(target),
                'original_raw_CE_first_accepted_candidate': breakdown(min(corrects,key=lambda c:c['raw_ce_rank'])),
                'composite_first_accepted_candidate': breakdown(min(corrects,key=lambda c:c['composite_rank'])),
                'crossing_candidates': pairs,
                'candidate_texts_inspected_from_frozen_corpus': True,
                'label_caveat': 'Distractor is a scoring diagnostic under frozen accepted spans; non-overlap does not prove semantic irrelevance.'}
        (benefit if is_benefit else harm).append(case)
    return harm, benefit


def contribution_stats(rows):
    statistics_by_component = {}
    unique_wins = Counter(); co_wins = Counter(); fractional_wins = Counter(); ties = 0
    for name, field in COMPONENTS.items():
        values = np.abs([c[field] for c in rows])
        statistics_by_component[name] = {'mean_absolute_weighted_contribution': float(np.mean(values)),
            'median': float(np.median(values)), 'p10': float(np.percentile(values,10)), 'p90': float(np.percentile(values,90))}
    for c in rows:
        magnitudes = {name: abs(c[field]) for name, field in COMPONENTS.items()}
        greatest = max(magnitudes.values()); winners = [name for name, value in magnitudes.items() if value==greatest]
        if len(winners)==1: unique_wins[winners[0]] += 1
        else: ties += 1
        for name in winners:
            co_wins[name] += 1; fractional_wins[name] += 1/len(winners)
    return statistics_by_component, {'denominator_candidate_pairs': len(rows), 'exact_tie_count': ties,
        'component_unique_winner_count': {n: unique_wins[n] for n in COMPONENTS},
        'component_including_ties_count': {n: co_wins[n] for n in COMPONENTS},
        'component_fractional_dominance_frequency': {n: fractional_wins[n]/len(rows) for n in COMPONENTS},
        'note': 'Numerically largest absolute weighted term per candidate. Large offsets do not necessarily determine pairwise ordering; margins in harm/benefit cases provide that attribution.'}


def rank_disagreement(grouped, movement):
    output = []; all_changes = []
    deltas = {x['query_id']: x['raw_CE_to_composite_first_accepted_rank_delta'] for x in movement}
    for qid, cs in grouped.items():
        raw = np.array([c['raw_ce_rank'] for c in cs]); combined = np.array([c['composite_rank'] for c in cs])
        changes = np.abs(raw-combined); all_changes.extend(int(x) for x in changes)
        ordered = sorted(cs,key=lambda c:c['raw_ce_rank'])
        inverted = sum(a['composite_rank']>b['composite_rank'] for i,a in enumerate(ordered) for b in ordered[i+1:])
        output.append({'query_id': qid, 'Spearman_rank_correlation': float(np.corrcoef(raw,combined)[0,1]),
            'candidate_count': 60, 'rank_changes': {str(k): {'count': int(np.sum(changes>=k)), 'fraction': float(np.mean(changes>=k))} for k in (5,10,20)},
            'pairwise_order_inversions': inverted, 'pairwise_comparison_count': 1770,
            'pairwise_disagreement_fraction': inverted/1770,
            'first_accepted_rank_delta': deltas[qid]})
    global_stats = {'candidate_pairs': len(all_changes), 'mean_absolute_rank_change': float(np.mean(all_changes)),
        'median_absolute_rank_change': float(np.median(all_changes)),
        'rank_changes': {str(k): {'count': sum(x>=k for x in all_changes), 'fraction': sum(x>=k for x in all_changes)/len(all_changes)} for k in (5,10,20)},
        'pairwise_order_inversions': sum(x['pairwise_order_inversions'] for x in output),
        'pairwise_comparison_count': 1770*len(output)}
    return output, global_stats


def pct(value): return f'{value:.2%}'


def render(r):
    f = r['formula']; w = f['weights']; m = r['system_metrics']; t = r['timing']; mem = r['memory']
    lines = ['# R0K — Current composite reranker on fixed G3 Dense60', '',
        f"**FINAL R0K DECISION: {r['decision']}.**", '', r['decision_reason'], '',
        'Experimental/descriptive engineering audit on frozen DRAFT DEV labels. No production changes, expansion, candidate search, weight tuning, training, downloads or TEST evaluation.', '',
        '## Frozen controls and fingerprints', '',
        f"Freeze verification: `{r['safety']}`. G1/G2/G3/R0/R0I/R0J, tokens_220, evaluation labels, source map and model/cache files unchanged; all 64 production snapshot files unchanged. Full before-SHA ledger in rag_r0k_preflight.json.", '',
        f"G3: `{r['G3']['path']}`, weights SHA-256 `{r['G3']['weights_sha256']}`; normalized384-dimensional embeddings, window256, unchanged per-book IndexFlatIP indexes.", '',
        f"CE: `{r['CE']['model_id']}`, snapshot `{r['CE']['revision']}`, weights SHA-256 `{r['CE']['model_weights_sha256']}`. Exact local R0/R0I/R0J checkpoint, float32, max512, batch16. Actual6-layer architecture; legacy config name says L-12. Loaded default activation and explicit experimental activation are both Identity; no softmax or sigmoid.", '',
        f"Environment: `{r['environment']}`. CE package fingerprints and versions: `{r['CE_package_sources']}`.", '',
        '## Exact current production formula', '',
        '```python', f['formula_from_current_AST'], '```', '',
        f"Weights read from current rag/evidence.py: CE={w['CE']}, evidence={w['evidence']}, dense={w['dense']}. Formula fingerprint SHA-256: `{f['formula_fingerprint_sha256']}`; executed scoring AST SHA-256: `{f['post_CE_AST_sha256']}`.", '',
        f"Executed unchanged post-CE statements from rag/reranker.py lines{f['production_statement_first_line']}–{f['production_statement_last_line']}; no production candidate-generation code, model construction or final Top5 truncation is invoked. All60 candidates remain available for ordering/evaluation.", '',
        '| Participating project source | SHA-256 |', '|---|---|']
    for path,h in f['source_sha256'].items(): lines.append(f'| {path} | {h} |')
    lines += ['', 'CE scoring uses the frozen R0I adapter and exact loaded CE. Preflight hashes cover the adapter, inherited forward source and predict decorator; the unwrapped CrossEncoder predict implementation is additionally fingerprinted during final artifact verification, with that provenance recorded explicitly. Checkpoint tokenizer/config files retain their R0 hashes in JSON.', '',
        '## Normalization, evidence context and ties', '',
        f"Normalization: `{f['normalization']}`.", '',
        f"Composite tie rule: {f['tie_behavior']}. Raw CE uses descending raw logits with chunk-ID ascending for exact ties. The candidate prefix starts in original dense order.", '',
        f"Evidence context: `{f['evidence_context']}`. The actual imported calculate_evidence_score and normalize_scores_minmax functions execute unchanged. Their complete source and the executed production statement block are preserved in JSON.", '',
        'This audit uses the existing search default intent_data=None, equivalent to earlier retrieval audits using{}. It does not invoke QA-level semantic intent extraction. Evidence-internal concept, phrase, actor/event and speaker heuristics remain as written; no separate lexical retrieval or lexical score is introduced. No query expansion strings are generated; retrieval_queries contains the original question only.', '',
        '## Reproduction and fixed membership', '',
        f"Reproduction: `{r['reproduction']}`. All30 DEV queries reproduce the frozen Top50 prefix; all29 evaluable Dense60 pools reproduce R0J exactly. The30th DEV query has no grade2 accepted passage and is reproduced without scoring. Raw CE matches every R0J Dense60 metric, rank, and score (maximum absolute score difference0).", '',
        'A/B/C contain exactly the same 60 chunk IDs per evaluable query: 1740 query/chunk pairs. Raw CE logits are scored once and reused exactly by composite. All accepted-overlap flags are added after scoring; gold spans never enter the production scoring function. Candidate Hit, Candidate Recall and no-gold are invariant.', '',
        '## Metrics', '', '| Metric | Dense60 | Raw CE | Current Composite |', '|---|---:|---:|---:|']
    for label, family, depth in [('MRR','mrr',None), *[(f'Hit@{k}','hit',k) for k in (1,3,5,10,20)],
        *[(f'Recall@{k}','recall',k) for k in (5,10,20)], ('Candidate Hit','candidate_Hit',None),
        ('Candidate Recall','candidate_Recall',None), ('No-gold candidate count','no_gold_candidate_count',None)]:
        values = [m[name][family] if depth is None else m[name][family][str(depth)] for name in SYSTEMS]
        formatted = [str(v) if family=='no_gold_candidate_count' else f'{v:.4f}' if family=='mrr' else pct(v) for v in values]
        lines.append('| '+label+' | '+' | '.join(formatted)+' |')
    lines += ['', f"Frozen decision priority: {r['selection_policy']} Raw CE has higher Hit20; Hit10 ties; composite improves Hit5 but loses MRR and Hit1/3. This is an aggregate descriptive conclusion, not a claim that every query benefits from raw CE.", '',
        '## Every-query accepted-rank movement', '',
        f"Raw CE→Composite counts: `{r['movement_counts']}`. UNCHANGED includes the7 queries with no accepted candidate, whose ranks remain absent.", '',
        '| Query | Dense first accepted | Raw CE first accepted | Composite first accepted | Delta | Classification |',
        '|---|---:|---:|---:|---:|---|']
    for x in r['per_query_movement']:
        lines.append(f"| {x['query_id']} | {x['dense_first_accepted_rank']} | {x['raw_CE_first_accepted_rank']} | {x['composite_first_accepted_rank']} | {x['raw_CE_to_composite_first_accepted_rank_delta']} | {x['classification']} |")
    lines += ['', '## Threshold recoveries and demotions', '', '| Threshold | Recovered queries | Demoted queries |', '|---|---|---|']
    for k in (1,3,5,10,20):
        a=r['threshold_crossings'][f'COMPOSITE_RECOVERED_TO_TOP{k}']; b=r['threshold_crossings'][f'COMPOSITE_DEMOTED_OUT_OF_TOP{k}']
        lines.append(f'| Top{k} | {a} | {b} |')
    lines += ['', '## Critical queries and component breakdown', '',
        'Target is the earliest original dense candidate overlapping an accepted span; query-first accepted ranks are listed separately because a different accepted candidate can lead after reranking.', '',
        '| Query | Target dense rank | Target raw CE rank | Target composite rank | Query raw first | Query composite first |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for x in r['critical_query_tracking']:
        lines.append(f"| {x['query_id']} | {x['original_target_dense_rank']} | {x['target_raw_CE_rank']} | {x['target_composite_rank']} | {x['query_raw_CE_first_accepted_rank']} | {x['query_composite_first_accepted_rank']} |")
    lines += ['', '| Query | Raw CE score | Evidence score | Dense norm | CE weighted | Evidence weighted | Dense weighted | Final composite |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for x in r['critical_query_tracking']:
        c=x['candidate']
        values = [f'{c[key]:.9f}' if c else 'None' for key in ('raw_ce_score','evidence_raw_score','dense_normalized_score',
                   'ce_weighted_contribution','evidence_weighted_contribution','dense_weighted_contribution','final_composite_score')]
        lines.append('| '+x['query_id']+' | '+' | '.join(values)+' |')
    lines += ['', r['v8_06_analysis'], '',
        '## Known CE-domain failures', '', '| Query | Raw CE first accepted | Composite first accepted | Movement |', '|---|---:|---:|---|']
    for x in r['known_CE_domain_failure_tracking']:
        lines.append(f"| {x['query_id']} | {x['raw_CE_first_accepted_rank']} | {x['composite_first_accepted_rank']} | {x['classification']} |")
    lines += ['', 'These cases have admitted accepted evidence and therefore reflect ordering failures, distinct from absent-candidate failures such as time_03. Improvements in individual cases do not establish general heuristic superiority.', '',
        '## Label-coverage limitations', '',
        'Known engineering-only POSSIBLE_LABEL_COVERAGE_LIMITATION passages receive no automatic gold credit. Frozen DRAFT labels remain unchanged.', '',
        '| Query | Chunk | Raw CE rank | Composite rank | Evidence |', '|---|---|---:|---:|---:|']
    for x in r['possible_label_coverage_limitations']:
        lines.append(f"| {x['query_id']} | {x['chunk_id']} | {x['raw_ce_rank']} | {x['composite_rank']} | {x['evidence_raw_score']:.9f} |")
    lines += ['', 'Full answer-evidence text and all components are in JSON. These are2 unique passages/queries, observed under raw CE and composite; they are excluded from accepted-span metrics.', '',
        '## Effective component contributions', '', '| Component | Mean absolute weighted term | Median | p10 | p90 | Dominance frequency |', '|---|---:|---:|---:|---:|---:|']
    for name, s in r['component_contribution_statistics'].items():
        frequency=r['component_dominance']['component_fractional_dominance_frequency'][name]
        lines.append(f"| {name} | {s['mean_absolute_weighted_contribution']:.9f} | {s['median']:.9f} | {s['p10']:.9f} | {s['p90']:.9f} | {pct(frequency)} |")
    lines += ['', f"Dominance method/counts: `{r['component_dominance']}`. No weight changes or alternative formulas were evaluated.", '',
        '## Ordering disagreement', '', f"Global distribution: `{r['global_rank_disagreement']}`.", '',
        '| Query | Spearman correlation | Changed ≥5 | Changed ≥10 | Changed ≥20 | Pairwise inversion fraction | First accepted delta |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for x in r['rank_disagreement_by_query']:
        cells=[f"{x['rank_changes'][str(k)]['count']}/60 ({pct(x['rank_changes'][str(k)]['fraction'])})" for k in (5,10,20)]
        lines.append('| '+x['query_id']+f" | {x['Spearman_rank_correlation']:.6f} | "+' | '.join(cells)+f" | {pct(x['pairwise_disagreement_fraction'])} | {x['first_accepted_rank_delta']} |")
    for title, key in [('Harm cases: first accepted rank worsens by at least5','harm_cases'),('Benefit cases: first accepted rank improves by at least5','benefit_cases')]:
        lines += ['', '## '+title, '',
            'All candidates crossing the target in opposite directions between raw CE and composite are recorded with exact text and component scores in JSON and rag_r0k_composite_harm_cases.json. Pairwise attribution uses the signs of actual weighted term margins; it is diagnostic, with no tuned weights or scored ablations.', '']
        if not r[key]: lines.append('None.')
        for case in r[key]:
            lines += [f"- **{case['query_id']} / {case['classification']}**: first accepted rank{case['raw_CE_first_accepted_rank']}→{case['composite_first_accepted_rank']}; {len(case['crossing_candidates'])} crossing candidates. Target `{case['target_accepted_candidate']['chunk_id']}`."]
            for c in case['crossing_candidates'][:3]:
                lines.append(f"  - `{c['chunk_id']}`: CE={c['raw_ce_score']:.9f}, evidence={c['evidence_raw_score']:.9f}, dense={c['dense_raw_score']:.9f}; weighted CE/evidence/dense={c['ce_weighted_contribution']:.9f}/{c['evidence_weighted_contribution']:.9f}/{c['dense_weighted_contribution']:.9f}, final={c['final_composite_score']:.9f}; {c['classification']}.")
    lines += ['', f"Harm classifications: `{r['harm_classification_counts']}`. Benefit classifications: `{r['benefit_classification_counts']}`.", '',
        '## Actual latency, GPU and RAM', '', '| Stage | Seconds per29-query batch | ms/query |', '|---|---:|---:|']
    for label, value in [('Dense retrieval',t['dense_retrieval_seconds']),('Raw CE scoring',t['raw_CE_seconds']),
        ('Raw CE sorting',t['raw_CE_sort_seconds']),('Evidence scoring',t['evidence_calculation_seconds']),
        ('Composite normalization/sort and audit wrapper, excluding evidence',t['composite_calculation_excluding_evidence_seconds']),
        ('Dense60 + raw CE pipeline',t['Dense60_RawCE_pipeline_seconds']),('Dense60 + composite pipeline',t['Dense60_Composite_pipeline_seconds'])]:
        lines.append(f'| {label} | {value:.6f} | {1000*value/29:.3f} |')
    lines += ['', f"Composite extra latency: {t['composite_extra_ms_per_query']:.3f}ms/query. Evidence was measured, not assumed cheap. {t['pipeline_note']} The composite stage includes source verification and defensive candidate copies; non-evidence time is therefore normalization/sort plus audit overhead, not an isolated pure-formula microbenchmark. Initial30-query reproduction and16 CE warmup pairs are excluded from pipeline times. This is one actual shared-machine pass; timings contain runtime noise.", '',
        f"CE batch size{r['CE_batch_size']}; actual scored unique pairs{t['unique_scored_CE_pairs']} (1740 logical per scored system, reused exactly between B/C). Peak allocated VRAM={mem['peak_allocated_VRAM_bytes']/1024**2:.2f}MiB; peak reserved={mem['peak_reserved_VRAM_bytes']/1024**2:.2f}MiB; minimum global free={mem['minimum_global_free_VRAM_bytes']/1024**3:.3f}GiB; peak process RSS={mem['peak_process_RSS_bytes']/1024**3:.3f}GiB. Both frozen models were resident. No unrelated workload was terminated.", '',
        '## Integrity, artifacts and stop', '', f"Tests: `{r['tests']}`. Final saved-artifact verification: `{r['final_artifact_checks']}`.", '',
        f"Component parquet: {r['score_rows']} rows; SHA-256 `{r['score_parquet_sha256']}`. Every system metric was reconstructed from saved ranks. Normalization, weighted terms, stable composite ties, source hashes and all memberships were verified without model inference.", '',
        '**TEST evaluated: NO. Production changed: NO. Labels changed: NO. Historical artifacts changed: NO.**', '',
        'Artifacts created:', '', *[f'- `{path}`' for path in r['artifacts_created']], '',
        f"**FINAL R0K DECISION: {r['decision']}.**", '',
        'Stopped after R0K. No production integration, weight tuning, CE fine-tuning or additional candidate-policy experiment was started.']
    OUT_K.with_suffix('.md').write_text('\n'.join(lines),encoding='utf-8')


def main():
    r=read(OUT_K); pre=read(PRE_K)
    assert sha(SCORES_K)==r['score_parquet_sha256']
    for path,h in pre['experimental_code_sha256'].items():assert sha(path)==h
    source_verify(r['formula'])
    for path,h in r['CE_package_sources']['source_sha256'].items():assert sha(path)==h
    implementation = ROOT / '.venv/Lib/site-packages/sentence_transformers/cross_encoder/model.py'
    assert implementation.is_file()
    implementation_hash = sha(implementation)
    previous_implementation = r['CE_package_sources'].get('unwrapped_predict_implementation_finalization_sha256')
    if previous_implementation:
        assert previous_implementation == {str(implementation): implementation_hash}
    r['CE_package_sources']['unwrapped_predict_implementation_finalization_sha256'] = {str(implementation): implementation_hash}
    r['CE_package_sources']['additional_source_hash_provenance'] = 'Unwrapped CrossEncoder.predict source identified with inspect.unwrap and hashed at final artifact verification; supplementary to the preflight project/forward/decorator hashes.'
    assert r['formula']==pre['formula']
    rows=pq.read_table(SCORES_K).to_pylist()
    assert len(rows)==r['score_rows']==1740
    assert {c['CE_weights_sha256'] for c in rows}=={r['CE']['model_weights_sha256']}
    assert {c['G3_weights_sha256'] for c in rows}=={r['G3']['weights_sha256']}
    assert {c['formula_fingerprint_sha256'] for c in rows}=={r['formula']['formula_fingerprint_sha256']}
    chunks={c['chunk_id']:{'start':c['source_start_char'],'end':c['source_end_char'],'text':c['text']}
            for c in pq.read_table(CORPUS/'chunks.parquet',columns=['chunk_id','source_start_char','source_end_char','text']).to_pylist()}
    questions=[q for q in read(ROOT/'rag/evaluation/rag_retrieval_eval_v1.json')['questions'] if q['split']=='DEV']
    evaluable=dev_evaluable(questions); qmap={q['query_id']:q for q in evaluable}
    assert set(qmap)=={c['query_id'] for c in rows} and len(qmap)==29
    assert all(c['query_id'] in {q['query_id'] for q in questions} for c in r['encoded_queries'])
    grouped=defaultdict(list)
    for c in rows:grouped[c['query_id']].append(c)
    baseline=next(x for x in read(R0J)['results'] if x['system']=='dense60')
    systems={name:{} for name in SYSTEMS}
    from rag.evidence import normalize_scores_minmax
    w=r['formula']['weights']
    for qid,cs in grouped.items():
        cs.sort(key=lambda c:c['dense_rank'])
        assert len(cs)==len(set(ids(cs)))==60
        assert [c['dense_rank'] for c in cs]==list(range(1,61))
        assert ids(cs)==ids(sorted(baseline['ranked_candidates'][qid],key=lambda c:c['rank']))
        assert [c['ce_normalized_score'] for c in cs]==normalize_scores_minmax([c['raw_ce_score'] for c in cs])
        assert [c['dense_normalized_score'] for c in cs]==normalize_scores_minmax([c['dense_raw_score'] for c in cs])
        for c in cs:
            assert c['text']==chunks[c['chunk_id']]['text']
            assert c['evidence_normalized_score'] is None and 0<=c['evidence_raw_score']<=1
            assert c['ce_weighted_contribution']==w['CE']*c['ce_normalized_score']
            assert c['evidence_weighted_contribution']==w['evidence']*c['evidence_raw_score']
            assert c['dense_weighted_contribution']==w['dense']*c['dense_normalized_score']
            assert c['final_composite_score']==c['ce_weighted_contribution']+c['evidence_weighted_contribution']+c['dense_weighted_contribution']
            assert c['accepted_overlap']==any(overlaps(chunks[c['chunk_id']],s) for s in qmap[qid]['accepted_passages'] if s['relevance_grade']==2)
        systems['dense'][qid]=cs
        systems['raw-ce'][qid]=sorted(cs,key=lambda c:(-c['raw_ce_score'],c['chunk_id']))
        systems['current-composite'][qid]=sorted(cs,key=lambda c:c['final_composite_score'],reverse=True)
        assert [c['raw_ce_rank'] for c in systems['raw-ce'][qid]]==list(range(1,61))
        assert [c['composite_rank'] for c in systems['current-composite'][qid]]==list(range(1,61))
    for name,pools in systems.items():assert metrics(evaluable,pools,chunks,60)==r['system_metrics'][name]
    assert r['system_metrics']['raw-ce']==baseline['CE_metrics']
    assert r['system_metrics']['dense']==baseline['candidate_metrics']
    per,counts,crossings=movements(evaluable,r['system_metrics'])
    assert per==r['per_query_movement'] and counts==r['movement_counts'] and crossings==r['threshold_crossings']
    r['component_contribution_statistics'],r['component_dominance']=contribution_stats(rows)
    r['rank_disagreement_by_query'],r['global_rank_disagreement']=rank_disagreement(grouped,per)
    r['harm_cases'],r['benefit_cases']=movement_cases(r,grouped)
    r['harm_classification_counts']=dict(Counter(c['classification'] for c in r['harm_cases']))
    r['benefit_classification_counts']=dict(Counter(c['classification'] for c in r['benefit_cases']))
    frozen80=next(x for x in read(OUT)['raw_sweep']['results'] if x['k']==80)
    critical=[]
    for qid in CRITICAL:
        dense80=sorted(frozen80['ranked_candidates'][qid],key=lambda c:c['rank'])
        first=next((c for c in dense80 if any(overlaps(chunks[c['chunk_id']],s) for s in qmap[qid]['accepted_passages'] if s['relevance_grade']==2)),None)
        found=next((c for c in grouped[qid] if first and c['chunk_id']==first['chunk_id']),None)
        critical.append({'query_id':qid,'target_chunk_id':first['chunk_id'] if first else None,
            'original_target_dense_rank':first['rank'] if first else None,
            'target_present_in_Dense60':found is not None,'target_raw_CE_rank':found['raw_ce_rank'] if found else None,
            'target_composite_rank':found['composite_rank'] if found else None,
            'query_raw_CE_first_accepted_rank':r['system_metrics']['raw-ce']['per_query'][qid]['first_rank'],
            'query_composite_first_accepted_rank':r['system_metrics']['current-composite']['per_query'][qid]['first_rank'],
            'candidate':breakdown(found) if found else None})
    r['critical_query_tracking']=critical
    v8=next(x for x in critical if x['query_id']=='v8_06')
    assert v8['original_target_dense_rank']==47 and v8['target_raw_CE_rank']==1
    pp=next(x for x in critical if x['query_id']=='pp_05')
    assert pp['original_target_dense_rank']==49 and pp['target_raw_CE_rank']==12
    r['v8_06_analysis']=f"v8_06 hard check: accepted target dense47, raw CE1, composite{v8['target_composite_rank']}. Its CE/evidence/dense weighted contributions are{v8['candidate']['ce_weighted_contribution']:.9f}/{v8['candidate']['evidence_weighted_contribution']:.9f}/{v8['candidate']['dense_weighted_contribution']:.9f}. " + ('The strong raw-CE recovery remains at rank1; no demotion attribution is needed.' if v8['target_composite_rank']==1 else 'The full component breakdown and overtaking candidates are included in the critical/harm diagnostic data.')
    r['known_CE_domain_failure_tracking']=[x for x in per if x['query_id'] in ('v8_08','pp_02','time_01')]
    label=[]
    for qid,cid in KNOWN_LABEL_IDS.items():
        found=next((c for c in grouped[qid] if c['chunk_id']==cid),None)
        if found:
            assert not found['accepted_overlap']
            label.append({'query_id':qid,**breakdown(found),'classification':'POSSIBLE_LABEL_COVERAGE_LIMITATION',
                'reason':'Carried-forward R0 source-inspected Wickham/Lydia or red-sun answer evidence, outside frozen accepted spans; no gold credit.'})
    r['possible_label_coverage_limitations']=label
    r['decision_reason']=('Raw CE wins the frozen primary ordering priority: Hit20 is62.07% versus58.62%; Hit10 ties at51.72%; MRR is0.3578 versus0.3300. Composite improves Hit5 (41.38%→48.28%) but adds no Top20 query recovery and demotes time_05 out of Top20. Membership and candidate coverage remain identical. This conclusion is descriptive on29 DRAFT DEV queries; no production change follows automatically.')
    testlog=REPORTS/'rag_r0k_contract_tests.log'
    assert '22 passed' in testlog.read_text(encoding='utf-8-sig')
    r['tests']={'result':'22 passed','path':str(testlog),'sha256':sha(testlog)}
    r['safety']=verify_ledger(pre['before_sha256'])
    r['final_artifact_checks']={'all_metrics_recomputed_from_saved_scores':True,'Dense60_and_raw_CE_exact_R0J_reproduction':True,
        'all_system_candidate_memberships_identical':True,'candidate_Hit_Recall_no_gold_invariant':True,
        'normalization_and_weighted_terms_exact':True,'production_stable_composite_sort_exact':True,
        'formula_and_CE_source_hashes_unchanged':True,'all_candidate_passages_match_frozen_corpus':True,
        'all_encoded_queries_DEV_only':True,'gold_overlap_added_only_after_scoring':True,
        'experimental_code_matches_preflight':True}
    r['artifacts_created']=[str(p.relative_to(ROOT)) for p in (
        ROOT/'scripts/r0k_common.py',ROOT/'scripts/evaluate_rag_r0k_composite_audit.py',ROOT/'scripts/report_rag_r0k_composite_audit.py',
        ROOT/'tests/test_rag_r0k_composite_audit.py',PRE_K,OUT_K,OUT_K.with_suffix('.md'),SCORES_K,
        REPORTS/'rag_r0k_composite_harm_cases.json',testlog,REPORTS/'rag_r0k_evaluation.log')]
    write(OUT_K,r)
    write(REPORTS/'rag_r0k_composite_harm_cases.json',{'harm_cases':r['harm_cases'],'benefit_cases':r['benefit_cases']})
    render(r)
    print(json.dumps({'decision':r['decision'],'safety':r['safety'],'movement_counts':r['movement_counts'],
        'harm_classifications':r['harm_classification_counts'],'benefit_classifications':r['benefit_classification_counts'],
        'v8_06':r['v8_06_analysis'],'contributions':r['component_contribution_statistics'],
        'dominance':r['component_dominance'],'final_checks':r['final_artifact_checks']},indent=2))


if __name__=='__main__': main()
