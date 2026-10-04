"""R0 isolation and candidate invariants, without loading/training any model."""
from collections import Counter
import copy

import pytest
from scripts.evaluate_rag_r0_existing_crossencoder import (
    dev_evaluable, rerank_raw, score_pools, system_result, top50_invariants, validate_candidates,
)


class FakeCE:
    fingerprint = 'one-unchanged-cross-encoder-sha256'
    def __init__(self):
        self.inputs = []
    def predict_raw(self, pairs):
        self.inputs.extend(pairs)
        # Deliberately reverse dense order and produce logits outside [0,1].
        return [float(int(passage.removeprefix('exact passage ')) - 25) for _, passage in pairs]


@pytest.fixture
def experiment():
    questions = [
        {'query_id':'dev1', 'split':'DEV', 'work_id':'book', 'question':'Original query?!',
         'accepted_passages':[
             {'relevance_grade':2,'source_start':0,'source_end':80},
             {'relevance_grade':2,'source_start':2000,'source_end':2080},
             {'relevance_grade':2,'source_start':6000,'source_end':6080}]},
        {'query_id':'dev2', 'split':'DEV', 'work_id':'book', 'question':'Other original query',
         'accepted_passages':[{'relevance_grade':2,'source_start':6000,'source_end':6080}]},
        {'query_id':'protected', 'split':'TEST', 'work_id':'book', 'question':'PROTECTED TEST NEVER SCORE',
         'accepted_passages':[{'relevance_grade':2,'source_start':0,'source_end':80}]},
        {'query_id':'unlabelled', 'split':'DEV', 'work_id':'book', 'question':'UNLABELLED SKIP', 'accepted_passages':[]},
    ]
    chunks = {f'c{i:02}':{'start':i*100,'end':i*100+100,'work_id':'book'} for i in range(50)}
    texts = {f'c{i:02}':f'exact passage {i}' for i in range(50)}
    candidates = [{'chunk_id':f'c{i:02}', 'rank':i+1, 'similarity':float(100000-i),
                   'evidence':1e9-i, 'lexical_score':1e9-i} for i in range(50)]
    reverse = [{**c, 'rank':i+1, 'similarity':-c['similarity']} for i,c in enumerate(reversed(candidates))]
    pools = {s:{q['query_id']:{'top50':copy.deepcopy(order)} for q in questions}
             for s,order in [('A',candidates),('G3',reverse)]}
    scorer = FakeCE()
    ranked, rows, info = score_pools(questions,pools,texts,scorer,batch_size=7)
    return questions,chunks,texts,pools,scorer,ranked,rows,info


def test_same_crossencoder_for_a_and_g3(experiment):
    *_,rows,info = experiment
    assert {r['cross_encoder_fingerprint'] for r in rows} == {FakeCE.fingerprint}
    assert info['same_cross_encoder_fingerprint'] == FakeCE.fingerprint
    # Reused pairs have bit-identical scores across different dense orders.
    by_pool = {s:{(r['query_id'],r['chunk_id']):r['ce_score'] for r in rows if r['retriever']==s} for s in ['A','G3']}
    assert by_pool['A'] == by_pool['G3']


def test_candidate_count_50(experiment):
    pools = experiment[3]
    validate_candidates(pools['A']['dev1']['top50'])
    with pytest.raises(RuntimeError):
        validate_candidates(pools['A']['dev1']['top50'][:49])
    bad = copy.deepcopy(pools['A']['dev1']['top50']);bad[-1]['chunk_id']=bad[0]['chunk_id']
    with pytest.raises(RuntimeError):validate_candidates(bad)


def test_candidate_membership_preserved(experiment):
    pools,ranked = experiment[3],experiment[5]
    for s in ['A','G3']:
        for q in ['dev1','dev2']:
            assert Counter(c['chunk_id'] for c in pools[s][q]['top50']) == Counter(c['chunk_id'] for c in ranked[s][q])


def test_raw_ce_score_only(experiment):
    ranked = experiment[5]['A']['dev1']
    assert ranked[0]['chunk_id']=='c49' and ranked[0]['ce_score']==24.0
    assert ranked[-1]['chunk_id']=='c00' and ranked[-1]['ce_score']==-25.0
    assert [r['ce_score'] for r in ranked] == sorted([r['ce_score'] for r in ranked],reverse=True)


def test_no_dense_score_mix(experiment):
    candidates = copy.deepcopy(experiment[3]['A']['dev1']['top50'])
    scores = [float(i) for i in range(50)]
    before = rerank_raw(candidates,scores)
    for c in candidates:c['similarity']=-1e30*c['similarity']
    after = rerank_raw(candidates,scores)
    assert [c['chunk_id'] for c in before] == [c['chunk_id'] for c in after]
    assert [c['ce_score'] for c in before] == [c['ce_score'] for c in after]


def test_no_evidence_mix(experiment):
    candidates = copy.deepcopy(experiment[3]['A']['dev1']['top50'])
    before = rerank_raw(candidates,list(range(50)))
    for c in candidates:c['evidence']=float('nan')
    assert [c['chunk_id'] for c in before] == [c['chunk_id'] for c in rerank_raw(candidates,list(range(50)))]


def test_no_query_expansion(experiment):
    scorer = experiment[4]
    assert {q for q,_ in scorer.inputs} == {'Original query?!','Other original query'}


def test_no_lexical(experiment):
    candidates = copy.deepcopy(experiment[3]['A']['dev1']['top50'])
    for c in candidates:c['lexical_score']=float('inf')
    ordered = rerank_raw(candidates,list(range(50)))
    assert ordered[0]['chunk_id']=='c49'
    assert all(p.startswith('exact passage ') for _,p in experiment[4].inputs)


def compared(experiment,system):
    questions,chunks,_,pools,_,ranked,_,_ = experiment
    q = dev_evaluable(questions)
    dense = system_result(q,{x['query_id']:pools[system][x['query_id']]['top50'] for x in q},chunks)
    ce = system_result(q,ranked[system],chunks)
    assert top50_invariants(dense,ce)
    return dense,ce


def test_a_hit50_invariant(experiment):
    a,b = compared(experiment,'A');assert a['metrics']['hit']['50']==b['metrics']['hit']['50']


def test_a_recall50_invariant(experiment):
    a,b = compared(experiment,'A');assert a['metrics']['recall']['50']==b['metrics']['recall']['50']
    assert a['metrics']['recall']['50'] < 1 # Partial multiple-span recall, not just hit.


def test_g3_hit50_invariant(experiment):
    a,b = compared(experiment,'G3');assert a['metrics']['hit']['50']==b['metrics']['hit']['50']


def test_g3_recall50_invariant(experiment):
    a,b = compared(experiment,'G3');assert a['metrics']['recall']['50']==b['metrics']['recall']['50']


def test_no_gold_count_invariant(experiment):
    for system in ['A','G3']:
        a,b = compared(experiment,system);assert a['no_gold_top50']==b['no_gold_top50']==1


def test_dev_only(experiment):
    assert experiment[7]['encoded_query_ids']==['dev1','dev2']
    assert all(q['split']=='DEV' for q in dev_evaluable(experiment[0]))


def test_test_queries_never_encoded(experiment):
    assert 'protected' not in experiment[7]['encoded_query_ids']
    assert not any('PROTECTED' in q or 'UNLABELLED' in q for q,_ in experiment[4].inputs)


def test_score_rows_match_candidate_rows(experiment):
    pools,rows,info = experiment[3],experiment[6],experiment[7]
    expected = Counter((s,q,c['chunk_id']) for s in ['A','G3'] for q in ['dev1','dev2'] for c in pools[s][q]['top50'])
    actual = Counter((r['retriever'],r['query_id'],r['chunk_id']) for r in rows)
    assert actual==expected and len(rows)==info['logical_pair_count']==200
    assert info['actual_scored_pair_count']==100 and info['duplicate_pair_reuses']==100


def test_equal_score_ties_ignore_dense_order(experiment):
    a = experiment[3]['A']['dev1']['top50'];g = experiment[3]['G3']['dev1']['top50']
    assert [c['chunk_id'] for c in rerank_raw(a,[1.0]*50)] == [c['chunk_id'] for c in rerank_raw(g,[1.0]*50)]


def test_invariant_violation_stops(experiment):
    a,b = compared(experiment,'A');b=copy.deepcopy(b);b['metrics']['recall']['50']=0
    with pytest.raises(RuntimeError):top50_invariants(a,b)


def test_nonfinite_scores_stop(experiment):
    with pytest.raises(RuntimeError):rerank_raw(experiment[3]['A']['dev1']['top50'],[float('nan')]*50)
