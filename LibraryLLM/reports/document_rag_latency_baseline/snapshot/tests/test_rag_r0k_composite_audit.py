"""Frozen R0K reproduction and production-formula isolation contracts."""
import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from r0k_common import *


@pytest.fixture(scope='module')
def frozen():
    r0j = read(R0J)
    baseline = next(r for r in r0j['results'] if r['system']=='dense60')
    pools = {qid: sorted(cs, key=lambda c:c['rank']) for qid,cs in baseline['ranked_candidates'].items()}
    questions = [q for q in read(ROOT / 'rag/evaluation/rag_retrieval_eval_v1.json')['questions'] if q['split']=='DEV']
    chunks = {c['chunk_id']: {'start': c['source_start'], 'end': c['source_end']} for cs in pools.values() for c in cs}
    return baseline,pools,questions,chunks


def test_dense60_exact_reproduction(frozen):
    baseline,pools,questions,chunks = frozen
    assert metrics(questions,pools,chunks,60)==baseline['candidate_metrics']


def test_raw_ce_exact_r0j_reproduction(frozen):
    baseline,pools,questions,chunks = frozen
    ranked={qid:rerank(cs,[c['ce_score'] for c in cs]) for qid,cs in pools.items()}
    assert metrics(questions,ranked,chunks,60)==baseline['CE_metrics']
    assert all(ids(cs)==ids(baseline['ranked_candidates'][qid]) for qid,cs in ranked.items())


@pytest.fixture
def scoring():
    dense=[{'rank':i,'chunk_id':f'book_hash{i:016x}','work_id':'book','similarity':1-i/100} for i in range(1,61)]
    metadata={c['chunk_id']:{'chunk_id':c['chunk_id'],'work_id':'book','title':'Generic title','chapter':'Unknown',
              'text':f'The traveller said that ambition and knowledge made him want to discover life. Passage {i}.'} for i,c in enumerate(dense)}
    inputs=scoring_candidates(dense,metadata)
    texts={cid:c['text'] for cid,c in metadata.items()}
    scores=[float(i-30) for i in range(60)]
    return dense,metadata,inputs,texts,scores


@pytest.fixture
def evaluated(scoring):
    dense,metadata,inputs,texts,scores=scoring
    combined,_=composite(inputs,scores,'Why did the traveller want to discover life?',texts)
    return dense,rerank(dense,scores),combined


def test_identical_candidate_membership_all_systems(evaluated):
    assert len({frozenset(ids(cs)) for cs in evaluated})==1
def test_candidate_count_60(evaluated): assert all(len(cs)==60 for cs in evaluated)
def test_no_candidate_addition(evaluated): assert set(ids(evaluated[2]))<=set(ids(evaluated[0]))
def test_no_candidate_removal(evaluated): assert set(ids(evaluated[0]))<=set(ids(evaluated[2]))


def test_same_ce_fingerprint():
    r0=read(REPORTS/'rag_r0_existing_crossencoder.json'); r0j=read(R0J)
    assert r0['cross_encoder']==r0j['CE']
    assert sha(Path(r0j['CE']['path'])/'model.safetensors')==r0j['CE']['model_weights_sha256']


def test_production_formula_source_hash_recorded():
    _,formula=production_formula()
    for path,h in formula['source_sha256'].items():assert sha(path)==h
    assert str(ROOT/'rag/reranker.py') in formula['source_sha256']
    assert str(ROOT/'rag/evidence.py') in formula['source_sha256']
    assert len(formula['formula_fingerprint_sha256'])==64


def test_existing_weights_not_changed(scoring):
    _,_,inputs,texts,scores=scoring
    rows,_=composite(inputs,scores,'Why discover life?',texts)
    _,formula=production_formula()
    assert formula['weights']=={'CE':.30,'evidence':.55,'dense':.15}
    for c in rows:assert c['final_score']==.30*c['normalized_rerank_score']+.55*c['evidence_score']+.15*c['faiss_norm']


def test_no_query_expansion(scoring,monkeypatch):
    import rag.evidence as evidence
    monkeypatch.setattr(evidence,'generate_expanded_queries',lambda *_:pytest.fail('Expansion called'))
    _,_,inputs,texts,scores=scoring
    rows,_=composite(inputs,scores,'Why discover life?',texts)
    assert len(rows)==60


def test_no_lexical():
    _,formula=production_formula()
    assert tuple(formula['weights'])==('CE','evidence','dense')
    assert 'search(' not in formula['executed_post_CE_source']
    assert 'lexical' not in formula['formula_from_current_AST']


def test_no_gold_used_in_scoring(scoring):
    # Gold flags are never an input to production scoring; even extra metadata flags cannot alter it.
    _,_,inputs,texts,scores=scoring
    plain,_=composite(inputs,scores,'Why discover life?',texts)
    changed=copy.deepcopy(inputs)
    for i,c in enumerate(changed):c.update(accepted_overlap=bool(i%2),relevance_grade=2,accepted_passages=[{'score':1e99}])
    other,_=composite(changed,scores,'Why discover life?',texts)
    assert [(c['chunk_id'],c['final_score']) for c in plain]==[(c['chunk_id'],c['final_score']) for c in other]
    assert 'accepted' not in production_formula()[1]['executed_post_CE_source']


def admission(evaluated):
    dense,raw,combined=evaluated
    chunks={c['chunk_id']:{'start':i*100,'end':i*100+100} for i,c in enumerate(dense)}
    q={'query_id':'dev','split':'DEV','accepted_passages':[{'relevance_grade':2,'source_start':4700,'source_end':4790}]}
    return [metrics([q],{'dev':cs},chunks,60) for cs in evaluated]


def test_candidate_recall_invariant(evaluated):assert len({m['candidate_Recall'] for m in admission(evaluated)})==1
def test_candidate_hit_invariant(evaluated):assert len({m['candidate_Hit'] for m in admission(evaluated)})==1
def test_no_gold_invariant(evaluated):assert len({m['no_gold_candidate_count'] for m in admission(evaluated)})==1


def test_dev_only():
    rt=Runtime.__new__(Runtime);rt.allowed={'dev'};rt.guard=lambda:pytest.fail('Non-DEV reached model')
    with pytest.raises(RuntimeError):rt.retrieve({'query_id':'train','split':'TRAIN'},60)


def test_test_never_encoded():
    rt=Runtime.__new__(Runtime);rt.allowed={'dev'};rt.guard=lambda:pytest.fail('TEST reached model')
    with pytest.raises(RuntimeError):rt.retrieve({'query_id':'protected','split':'TEST'},60)


@pytest.fixture(scope='module')
def freeze_verified():
    ledger,_,_,_=freeze_k()
    return verify_ledger(ledger)


def test_historical_files_unchanged(freeze_verified):assert freeze_verified['historical_files_changed']==0
def test_production_files_unchanged(freeze_verified):assert freeze_verified['production_files_changed']==0


def test_normalization_zero_range_and_empty():
    from rag.evidence import normalize_scores_minmax
    assert normalize_scores_minmax([])==[]
    assert normalize_scores_minmax([-8.,-8.])==[.5,.5]
    assert normalize_scores_minmax([-10.,0.,10.])==[0.,.5,1.]


def test_composite_exact_ties_preserve_dense_order(scoring):
    _,_,inputs,texts,_=scoring
    for c in inputs:c['score']=1.;c['text']='Identical text with no actor.'
    rows,_=composite(inputs,[0.]*60,'unmatchedquestion',texts)
    assert ids(rows)==ids(inputs)


def test_inputs_not_mutated(scoring):
    _,_,inputs,texts,scores=scoring
    before=copy.deepcopy(inputs)
    composite(inputs,scores,'Why discover life?',texts)
    assert inputs==before
