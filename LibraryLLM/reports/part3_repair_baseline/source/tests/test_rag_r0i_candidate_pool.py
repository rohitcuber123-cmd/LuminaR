"""R0I: nested pools, raw CE contract, real frozen recovery ranks and union control."""
import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from r0i_common import prefix,rerank,dense_preserving_union,query_metrics,Runtime,KS,read,TRAIN,ROOT,select_k
from evaluate_rag_r0i_expansion import existing_builder


@pytest.fixture
def rows():return [{'rank':i,'chunk_id':f'c{i:03}','similarity':1e6-i,'text':f'passage {i}'} for i in range(1,81)]


def ids(rows):return [c['chunk_id'] for c in rows]


def test_k20_subset_of_k30(rows):assert set(ids(prefix(rows,20)))<set(ids(prefix(rows,30)))
def test_k30_subset_of_k40(rows):assert set(ids(prefix(rows,30)))<set(ids(prefix(rows,40)))
def test_k40_subset_of_k50(rows):assert set(ids(prefix(rows,40)))<set(ids(prefix(rows,50)))
def test_k50_subset_of_k60(rows):assert set(ids(prefix(rows,50)))<set(ids(prefix(rows,60)))
def test_k60_subset_of_k80(rows):assert set(ids(prefix(rows,60)))<set(ids(prefix(rows,80)))


def test_dense_order_preserved_before_ce(rows):
    for k in KS:assert ids(prefix(rows,k))==ids(rows)[:k]


class FakeCE:
    def __init__(self):self.calls=[]
    def predict(self,pairs,**kwargs):
        self.calls.append((pairs,kwargs,id(self)))
        return [float(int(text.split()[-1])-40) for _,text in pairs]


@pytest.fixture
def scorer():
    rt=Runtime.__new__(Runtime);rt.batch_size=16;rt.guard=lambda:None;rt.ce=FakeCE()
    rt.torch=SimpleNamespace(nn=SimpleNamespace(Identity=lambda:'Identity'))
    return rt


def test_same_crossencoder_all_k(rows,scorer):
    for k in KS:scorer.score([('original',c['text']) for c in prefix(rows,k)])
    assert {c[2] for c in scorer.ce.calls}=={id(scorer.ce)}


def test_candidate_membership_fixed_within_k(rows):
    for k in KS:
        before=prefix(rows,k);after=rerank(before,list(range(k)))
        assert set(ids(before))==set(ids(after)) and len(after)==k


@pytest.fixture
def frozen():
    saved={q['query_id']:q for q in read(TRAIN/'evaluation_indexes/minilm_g3_gooaq_50k/dense_dev_evaluation.json')['queries']}
    labels={q['query_id']:q for q in read(ROOT/'rag/evaluation/rag_retrieval_eval_v1.json')['questions'] if q['split']=='DEV'}
    chunks={c['chunk_id']:{'start':c['source_start'],'end':c['source_end']} for q in saved.values() for c in q['top50']}
    return saved,labels,chunks


def test_v8_06_absent_below_rank47(frozen):
    saved,labels,chunks=frozen
    for k in [20,30,40,46]:assert query_metrics(labels['v8_06'],saved['v8_06']['top50'][:k],chunks,k)['first_rank'] is None


def test_v8_06_present_at_k50(frozen):
    saved,labels,chunks=frozen
    assert query_metrics(labels['v8_06'],saved['v8_06']['top50'],chunks,50)['first_rank']==47


def test_pp_05_absent_below_rank49(frozen):
    saved,labels,chunks=frozen
    for k in [20,30,40,48]:assert query_metrics(labels['pp_05'],saved['pp_05']['top50'][:k],chunks,k)['first_rank'] is None


def test_pp_05_present_at_k50(frozen):
    saved,labels,chunks=frozen
    assert query_metrics(labels['pp_05'],saved['pp_05']['top50'],chunks,50)['first_rank']==49


def test_test_queries_never_encoded():
    rt=Runtime.__new__(Runtime);rt.allowed={'dev'};rt.guard=lambda:pytest.fail('TEST reached inference guard')
    with pytest.raises(RuntimeError):rt.retrieve({'query_id':'protected','split':'TEST','question':'never'},80)


def test_raw_ce_only(rows,scorer):
    values=scorer.score([('original',c['text']) for c in rows])
    assert min(values)<0 and max(values)>1
    assert all(call[1]['activation_fn']=='Identity' and call[1]['apply_softmax'] is False for call in scorer.ce.calls)


def test_no_score_mixing(rows):
    scores=list(range(80));expected=ids(rerank(rows,scores));altered=copy.deepcopy(rows)
    for c in altered:c.update(similarity=float('nan'),evidence=1e300,lexical_score=1e300)
    assert ids(rerank(altered,scores))==expected


def test_expansion_cannot_modify_original_source_text(rows):
    class Retriever:
        def search(self,query,top_k,**kwargs):
            assert top_k==15
            return {'results':copy.deepcopy(rows[:15]),'timing_ms':{}}
    class Instance:retriever=Retriever()
    fn,policy=existing_builder()
    result=fn(Instance(),'Why does the creature create life?',work_id='book',final_budget=50)
    assert all(c['text']==rows[c['rank']-1]['text'] for c in result['uncapped_candidates'])
    assert policy['per_branch_depth']==15 and policy['production_literal_cap']==40
    assert result['retrieval_queries'][0]=='Why does the creature create life?'


def test_dense_preserving_union_really_preserves_dense_candidates(rows):
    dense=prefix(rows,50);bad_duplicate={**dense[0],'text':'expanded replacement must not overwrite original'}
    union=dense_preserving_union(dense,[bad_duplicate,*rows[50:]],20)
    assert ids(union)[:50]==ids(dense) and union[0]['text']==dense[0]['text']
    assert len(union)==70 and set(ids(dense)).issubset(ids(union))


def test_metrics_include_spans_beyond_top50(rows):
    chunks={c['chunk_id']:{'start':i*100,'end':i*100+100} for i,c in enumerate(rows)}
    q={'accepted_passages':[{'relevance_grade':2,'source_start':7000,'source_end':7080}]}
    assert query_metrics(q,rows[:50],chunks,50)['first_rank'] is None
    m=query_metrics(q,rows,chunks,80)
    assert m['first_rank']==71 and m['recall']['80']==1 and m['hit']['80']==1


def test_k_selection_prioritizes_coverage_over_mrr():
    def r(k,cov,mrr):return {'k':k,'candidate_metrics':{'candidate_Recall':cov,'candidate_Hit':cov},
       'CE_metrics':{'hit':{'20':.5,'10':.5},'mrr':mrr},'timing':{'average_retrieval_plus_CE_ms_per_query':k}}
    assert select_k([r(50,.7,.9),r(80,.8,.3)])==80


def test_nonfinite_ce_score_stops(rows):
    with pytest.raises(RuntimeError):rerank(rows,[float('nan')]*80)
