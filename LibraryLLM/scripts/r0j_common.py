"""Experimental R0J quotas. All historical helpers and production sources are read-only."""
from __future__ import annotations

import copy
from types import MappingProxyType
from r0i_common import *
from evaluate_rag_r0i_expansion import generation, existing_builder

POLICIES = MappingProxyType({
    'dense60': (60, 0, 60), 'dense80': (80, 0, 80),
    'd50e30': (50, 30, 80), 'd60e20': (60, 20, 80),
    'd70e10': (70, 10, 80), 'd80e20': (80, 20, 100),
})
POLICY_NAMES = tuple(POLICIES)
CRITICAL = ('v8_06', 'pp_05', 'v8_08', 'v8_09', 'v8_10', 'pp_02',
            'time_01', 'time_03', 'time_05', 'war_05')
OUT_J = REPORTS / 'rag_r0j_dense_quota_candidates.json'
SCORES_J = TRAIN / 'evaluation/rag_r0j_candidate_scores.parquet'
PRE_J = REPORTS / 'rag_r0j_preflight.json'
SELECTION = ('Lexicographic priority: candidate macro Recall, candidate Hit, CE Hit20, '
             'CE Hit10, fewer no-gold queries, lower measured CE milliseconds/query, MRR. '
             'If the coverage winner improves no useful Top20 coverage and worsens Hit20 '
             'against dense60, report MIXED / INCONCLUSIVE instead of asserting extra cost '
             'is justified. No query-specific policy or added policy.')


def ids(rows):
    return [c['chunk_id'] for c in rows]


def freeze_j():
    ledger, r0 = freeze()
    r0i = read(OUT)
    verify_ledger(read(REPORTS / 'rag_r0i_preflight.json')['before_sha256'])
    assert r0i['decision'].startswith('D. CURRENT EXPANSION/CAPPING')
    assert sha(SCORES) == r0i['score_parquet_sha256']
    assert sha(RAW) == r0i['raw_report_sha256']
    assert read(RAW) == r0i['raw_sweep']
    assert sha(r0i['raw_sweep']['raw_score_path']) == r0i['raw_sweep']['raw_score_sha256']
    for name in r0i['artifacts_added']:
        path = ROOT / name
        assert path.is_file(), path
        ledger[str(path)] = sha(path)
    return ledger, r0, r0i


def build_pool(dense80, expansion, policy):
    """Keep dense copies and order; expansion duplicates never consume quota."""
    n, extra, ceiling = POLICIES[policy]
    dense = prefix(dense80, n)
    assert len(ids(expansion)) == len(set(ids(expansion))), 'Expansion must be canonical first-seen deduped'
    expansion_by_id = {c['chunk_id']: c for c in expansion}
    dense_rank = {c['chunk_id']: c['rank'] for c in dense80}
    out = []
    for c in dense:
        row = copy.deepcopy(c)
        match = expansion_by_id.get(c['chunk_id']) if extra else None
        row.update(source='BOTH' if match else 'DENSE',
                   original_dense_rank=c['rank'], expansion_only=False,
                   matched_queries=list(match.get('matched_queries', [])) if match else [])
        out.append(row)
    seen = set(ids(dense))
    added = 0
    for c in expansion:
        if added == extra:
            break
        if c['chunk_id'] in seen:
            continue
        row = copy.deepcopy(c)
        row.update(source='EXPANSION', original_dense_rank=dense_rank.get(c['chunk_id']),
                   expansion_only=True)
        out.append(row)
        seen.add(c['chunk_id'])
        added += 1
    for i, c in enumerate(out, 1):
        c['rank'] = i
    assert ids(out)[:n] == ids(dense80)[:n]
    assert set(ids(dense80)[:n]).issubset(ids(out))
    assert len(out) == len(set(ids(out))) and n <= len(out) <= ceiling
    assert sum(c['expansion_only'] for c in out) <= extra
    return out


def priority(result):
    d, c, t = result['candidate_metrics'], result['CE_metrics'], result['timing']
    return (d['candidate_Recall'], d['candidate_Hit'], c['hit']['20'], c['hit']['10'],
            -d['no_gold_candidate_count'], -t['average_CE_ms_per_query'], c['mrr'])


def accepted_indices(q, candidate, chunks):
    spans = [s for s in q['accepted_passages'] if s['relevance_grade'] == 2]
    return [i for i, s in enumerate(spans) if overlaps(chunks[candidate['chunk_id']], s)]


def assert_critical(qid, pool, dense80):
    target_rank = {'v8_06': 47, 'pp_05': 49}.get(qid)
    if target_rank:
        target = dense80[target_rank - 1]['chunk_id']
        assert target in ids(pool), f'{qid} lost original dense rank {target_rank}; STOP'

