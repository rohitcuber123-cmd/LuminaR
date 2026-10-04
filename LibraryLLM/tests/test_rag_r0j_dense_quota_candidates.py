"""R0J preservation contracts, frozen data reproductions, and inference isolation."""
import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from r0j_common import *


@pytest.fixture
def dense():
    return [{'rank': i, 'chunk_id': f'c{i:03}', 'similarity': 1000-i, 'text': f'original {i}'} for i in range(1, 81)]


@pytest.fixture
def expansion(dense):
    return [{**dense[0], 'text': 'must not replace dense copy', 'matched_queries': ['variant']},
            *[{'rank': i, 'chunk_id': f'e{i:03}', 'similarity': i, 'text': f'extra {i}', 'matched_queries': ['variant']}
              for i in range(1, 41)]]


@pytest.fixture(scope='module')
def frozen():
    r0i = read(OUT)
    raw = {r['k']: r for r in r0i['raw_sweep']['results']}
    top80 = {qid: sorted(rows, key=lambda c: c['rank']) for qid, rows in raw[80]['ranked_candidates'].items()}
    questions = [q for q in read(ROOT / 'rag/evaluation/rag_retrieval_eval_v1.json')['questions'] if q['split'] == 'DEV']
    chunks = {c['chunk_id']: {'start': c['source_start'], 'end': c['source_end']}
              for rows in top80.values() for c in rows}
    return raw, top80, questions, chunks


def test_frozen_policy_set():
    assert tuple(POLICIES.items()) == (('dense60', (60, 0, 60)), ('dense80', (80, 0, 80)),
        ('d50e30', (50, 30, 80)), ('d60e20', (60, 20, 80)), ('d70e10', (70, 10, 80)), ('d80e20', (80, 20, 100)))
    with pytest.raises(TypeError):
        POLICIES['added_after_results'] = (40, 40, 80)


def baseline_reproduction(frozen, name, k):
    raw, top80, questions, chunks = frozen
    pools = {qid: build_pool(rows, [], name) for qid, rows in top80.items()}
    ranked = {qid: rerank(rows, [c['ce_score'] for c in rows]) for qid, rows in pools.items()}
    assert metrics(questions, pools, chunks, k) == raw[k]['candidate_metrics']
    assert metrics(questions, ranked, chunks, k) == raw[k]['CE_metrics']
    assert all(ids(pools[qid]) == ids(rows[:k]) for qid, rows in top80.items())


def test_dense60_exact_reproduction(frozen): baseline_reproduction(frozen, 'dense60', 60)
def test_dense80_exact_reproduction(frozen): baseline_reproduction(frozen, 'dense80', 80)


def preserves(dense, expansion, name):
    n, extra, cap = POLICIES[name]
    pool = build_pool(dense, expansion, name)
    assert ids(pool)[:n] == ids(dense[:n]) and len(pool) <= cap
    assert sum(c['expansion_only'] for c in pool) == extra


def test_d50e30_preserves_first50(dense, expansion): preserves(dense, expansion, 'd50e30')
def test_d60e20_preserves_first60(dense, expansion): preserves(dense, expansion, 'd60e20')
def test_d70e10_preserves_first70(dense, expansion): preserves(dense, expansion, 'd70e10')
def test_d80e20_preserves_first80(dense, expansion): preserves(dense, expansion, 'd80e20')


def test_expansion_never_replaces_dense_quota(dense, expansion):
    for name in POLICY_NAMES:
        pool = build_pool(dense, expansion, name)
        assert pool[0]['text'] == dense[0]['text']
        assert pool[0]['similarity'] == dense[0]['similarity']
    assert build_pool(dense, expansion, 'd60e20')[0]['source'] == 'BOTH'


def test_chunk_id_dedup(dense, expansion):
    pool = build_pool(dense, expansion, 'd50e30')
    assert len(ids(pool)) == len(set(ids(pool)))
    with pytest.raises(AssertionError): build_pool(dense, expansion + [expansion[1]], 'd50e30')


def test_expansion_quota_counts_unique_only(dense, expansion):
    many_duplicates = [{**c, 'matched_queries': ['variant']} for c in dense[:60]]
    pool = build_pool(dense, many_duplicates + expansion[1:], 'd60e20')
    assert ids(pool)[60:] == ids(expansion[1:21]) and len(pool) == 80


def critical_preserved(frozen, qid, rank):
    _, top80, questions, chunks = frozen
    question = next(q for q in questions if q['query_id'] == qid)
    dense = top80[qid]
    assert query_metrics(question, dense, chunks, 80)['first_rank'] == rank
    for name in POLICY_NAMES:
        pool = build_pool(dense, [], name)
        assert_critical(qid, pool, dense)
        assert dense[rank-1]['chunk_id'] in ids(pool)


def test_v8_06_present_in_all_dense50plus_policies(frozen): critical_preserved(frozen, 'v8_06', 47)
def test_pp_05_present_in_all_dense50plus_policies(frozen): critical_preserved(frozen, 'pp_05', 49)


def test_same_ce_fingerprint():
    r0 = read(REPORTS / 'rag_r0_existing_crossencoder.json')
    r0i = read(OUT)
    assert r0['cross_encoder'] == r0i['raw_sweep']['CE']
    assert sha(Path(r0['cross_encoder']['path']) / 'model.safetensors') == r0['cross_encoder']['model_weights_sha256']


def test_raw_ce_only():
    calls = []
    class CE:
        def predict(self, pairs, **kwargs):
            calls.append(kwargs)
            return [-3., 2.]
    rt = Runtime.__new__(Runtime)
    rt.batch_size = 16; rt.guard = lambda: None; rt.ce = CE()
    rt.torch = SimpleNamespace(nn=SimpleNamespace(Identity=lambda: 'Identity'))
    assert rt.score([('original question', 'a'), ('original question', 'b')]) == [-3., 2.]
    assert calls[0]['activation_fn'] == 'Identity' and calls[0]['apply_softmax'] is False


def test_no_composite_score(dense):
    values = list(range(80))
    altered = copy.deepcopy(dense)
    for c in altered: c.update(similarity=float('nan'), evidence_score=1e90, lexical_score=1e99)
    assert ids(rerank(dense, values)) == ids(rerank(altered, values))


def test_dev_only():
    rt = Runtime.__new__(Runtime); rt.allowed = {'dev'}
    rt.guard = lambda: pytest.fail('Non-DEV reached inference')
    with pytest.raises(RuntimeError): rt.retrieve({'split': 'TRAIN', 'query_id': 'train'}, 60)


def test_test_never_encoded():
    rt = Runtime.__new__(Runtime); rt.allowed = {'dev'}
    rt.guard = lambda: pytest.fail('TEST reached inference')
    with pytest.raises(RuntimeError): rt.retrieve({'split': 'TEST', 'query_id': 'protected'}, 80)


@pytest.fixture(scope='module')
def frozen_verification():
    ledger, _, _ = freeze_j()
    return verify_ledger(ledger)


def test_historical_files_unchanged(frozen_verification):
    assert frozen_verification['historical_files_changed'] == 0
    assert frozen_verification['verified_file_count'] > 390


def test_production_files_unchanged(frozen_verification):
    assert frozen_verification['production_files_changed'] == 0


def test_inputs_not_mutated(dense, expansion):
    before = copy.deepcopy((dense, expansion))
    build_pool(dense, expansion, 'd60e20')
    assert (dense, expansion) == before


def test_expansion_beyond_quota_retains_original_rank(dense):
    expansion = [{**dense[75], 'matched_queries': ['variant']}]
    pool = build_pool(dense, expansion, 'd60e20')
    assert pool[-1]['source'] == 'EXPANSION' and pool[-1]['original_dense_rank'] == 76
    assert pool[-1]['rank'] == 61


def test_coverage_priority_over_mrr():
    def result(coverage, hit20, mrr):
        return {'candidate_metrics': {'candidate_Recall': coverage, 'candidate_Hit': coverage, 'no_gold_candidate_count': 1},
                'CE_metrics': {'hit': {'20': hit20, '10': hit20}, 'mrr': mrr},
                'timing': {'average_CE_ms_per_query': 100}}
    assert priority(result(.8, .5, .2)) > priority(result(.7, .7, .9))
