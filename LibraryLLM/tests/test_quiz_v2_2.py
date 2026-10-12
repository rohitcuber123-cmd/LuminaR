import ast
from collections import Counter
from copy import deepcopy
from itertools import combinations
import json
from pathlib import Path
import pytest
from rag.services import document_knowledge as dk, knowledge_quiz as quiz
from rag.services import knowledge_quiz_relations as r, knowledge_mcq as mcq, knowledge_match as match

FIXTURE=Path(__file__).parent/'fixtures/knowledge_educational.json'


@pytest.fixture
def model():
    m=dk.build(json.loads(FIXTURE.read_text(encoding='utf8')));r.attach(m);return m


@pytest.fixture
def candidates(model):
    return mcq.candidates(model.quiz_relations,{},'v22')


def test_mcq_stem_and_answer_same_fact(model,candidates):
    assert candidates
    for q in candidates:
        record=next(x for x in model.quiz_relations if x['id']==q['relationId'])
        assert q['subjectId']==record['subjectId'] and q['sourceFactId']==record['sourceFactId']
        assert mcq.verify(q,model.quiz_relations) is None


def test_mcq_correct_answer_matches_relation_target(candidates):
    for q in candidates:assert q['correctAnswer']==q['_relation']['subjectText' if q['_identify'] else 'targetText']


@pytest.mark.parametrize('field',['question','correctAnswer','sourceFactId','subjectText','pageStart','explanation'])
def test_final_verifier_rejects_detached_bindings(model,candidates,field):
    q=deepcopy(candidates[0]);q[field]='detached'
    assert mcq.verify(q,model.quiz_relations)


def test_mcq_exactly_one_correct_option(model,candidates):
    q=deepcopy(candidates[0]);q['options'][0]=q['correctAnswer'];q['options'][1]=q['correctAnswer']
    assert mcq.verify(q,model.quiz_relations)


def test_mcq_distractor_not_valid_for_subject(model,candidates):
    q=candidates[0];correct=q['_relation'];other=q['_options'][1]
    supported={**other,'subjectId':correct['subjectId'],'subjectText':correct['subjectText']}
    assert not r.compatible(correct,other,[*model.quiz_relations,supported])


def test_mcq_option_text_unique(candidates):
    assert all(len({r.key(x) for x in q['options']})==4 for q in candidates)


def test_mcq_semantic_option_unique(model,candidates):
    q=deepcopy(candidates[0]);q['_options'][0]['semanticPeers']=[q['_options'][1]['legacyEvidenceId']]
    assert mcq.verify(q,model.quiz_relations)


def test_mcq_global_finalizer(model,candidates):
    selected,metrics=mcq.finalize_mcq_quiz(candidates,12,model.quiz_relations)
    assert 0<len(selected)<=12 and metrics['maxDistractorReuse']<=2
    assert all(mcq.verify(q,model.quiz_relations) is None for q in selected)


def test_mcq_quiz_wide_distractor_reuse_limit(model,candidates):
    selected,_=mcq.finalize_mcq_quiz(candidates,30,model.quiz_relations)
    uses=Counter(r.key(x) for q in selected for x in q['options'] if x!=q['correctAnswer'])
    assert max(uses.values())<=2


def test_mcq_option_set_not_repeated(model,candidates):
    selected,_=mcq.finalize_mcq_quiz(candidates,30,model.quiz_relations)
    signatures=[frozenset(r.key(x) for x in q['options']) for q in selected]
    assert len(signatures)==len(set(signatures)) and all(len(a&b)<3 for a,b in combinations(signatures,2))


def test_mcq_subject_diversity(model,candidates):
    selected,_=mcq.finalize_mcq_quiz(candidates,12,model.quiz_relations)
    assert max(Counter(q['subjectId'] for q in selected).values())<=2


def test_mcq_relation_diversity(model,candidates):
    selected,_=mcq.finalize_mcq_quiz(candidates,12,model.quiz_relations)
    assert {'DEFINITION','IDENTIFICATION'} <= {q['questionForm'] for q in selected}


def test_mcq_answer_position_distribution(model):
    positions=set()
    for seed in range(4):
        qs,_=mcq.finalize_mcq_quiz(mcq.candidates(model.quiz_relations,{},seed),12,model.quiz_relations)
        positions.update(q['options'].index(q['correctAnswer']) for q in qs)
    assert positions=={0,1,2,3}


def test_mcq_explanation_same_source_fact(candidates):
    assert all(q['explanation']==q['_relation']['sourceExcerpt'] for q in candidates)


def test_mcq_source_page_same_fact(candidates):
    assert all(q['pageStart']==q['_relation']['pageStart'] for q in candidates)


def test_mcq_ambiguous_source_rejected():
    m=dk.build([{'chunk_id':'c','page':1,'text':'Router is a device that forwards packets to the destination network. Router is a program that paints unrelated pictures on a display.'}]);r.attach(m)
    assert not any(x['subjectText']=='Router' for x in m.quiz_relations)


def test_mcq_ocr_corruption_rejected():
    m=dk.build([{'chunk_id':'c','page':1,'extraction_method':'OCR','text':'Router is a netw0rk d3vice that forwards pack3ts to the destinati0n network.'}]);r.attach(m)
    assert not m.quiz_relations


def test_mcq_partial_count_after_quality_filter(model):
    out=quiz.generate_from_knowledge(model,{'questionTypes':['mcq'],'questionCount':30})
    assert 0<len(out['questions'])<30 and out['messages'] and out['coverage']['qwenCalls']==0


def test_match_not_generated_from_mcq_questions():
    tree=ast.parse(Path(match.__file__).read_text(encoding='utf8'))
    assert not any('mcq' in ast.unparse(node).lower() for node in ast.walk(tree) if isinstance(node,(ast.Import,ast.ImportFrom)))


def test_match_uses_relation_records(model):
    for q in match.candidates(model.quiz_relations,{}):
        assert all(x['relationId'] in {r['id'] for r in model.quiz_relations} for x in q['leftItems'])


@pytest.mark.parametrize('invariant',['bijection','left','right','family','source','ids','page','size'])
def test_match_integrity_invariants(model,invariant):
    q=deepcopy(match.candidates(model.quiz_relations,{})[0]);assert match.verify(q,model.quiz_relations) is None
    if invariant=='bijection':q['correctMatches'][q['leftItems'][0]['id']]=q['correctMatches'][q['leftItems'][1]['id']]
    elif invariant=='left':q['leftItems'][1]['text']=q['leftItems'][0]['text']
    elif invariant=='right':q['rightItems'][1]['text']=q['rightItems'][0]['text']
    elif invariant=='family':q['relationFamily']='WRONG'
    elif invariant=='source':q['leftItems'][0]['sourceFactId']='detached'
    elif invariant=='ids':q['rightItems'][1]['id']=q['rightItems'][0]['id']
    elif invariant=='page':q['leftItems'][0]['pageStart']=999
    elif invariant=='size':q['leftItems']=q['leftItems'][:2]
    assert match.verify(q,model.quiz_relations)


def test_match_semantic_right_unique(model):
    relations=deepcopy(model.quiz_relations)
    for relation in relations:relation['semanticPeers']=[x['legacyEvidenceId'] for x in relations if x is not relation]
    assert not match.candidates(relations,{})


def test_match_three_pair_minimum(model):
    assert not match.candidates(model.quiz_relations[:2],{})
    assert all(3<=len(q['leftItems'])<=6 for q in match.candidates(model.quiz_relations,{}))


def test_match_cross_page_relations_allowed(model):
    assert any(len(q['sourceChunkIds'])>1 for q in match.candidates(model.quiz_relations,{}))


def test_match_cross_format_fact_reuse_blocked(model):
    out=quiz.generate_from_knowledge(model,{'questionTypes':['mcq','matching','fill_blank'],'questionCount':12})
    concepts=[];facts=[]
    for q in out['questions']:
        if q['type']=='matching':
            concepts.extend(r.key(x['text']) for x in q['leftItems']);facts.extend(x['sourceExcerpt'] for x in q['leftItems'])
        else:
            facts.append(q['sourceExcerpt'])
            if q['type']=='mcq':concepts.append(r.key(q['subjectText']))
    assert len(facts)==len(set(facts)) and len(concepts)==len(set(concepts))


def test_match_quiz_wide_relation_reuse(model):
    out=quiz.generate_from_knowledge(model,{'questionTypes':['matching'],'questionCount':12})
    left=[x['text'] for q in out['questions'] for x in q['leftItems']]
    right=[x['text'] for q in out['questions'] for x in q['rightItems']]
    ids=[x['relationId'] for q in out['questions'] for x in q['leftItems']]
    assert len(out['questions'])==3 and out['learningItemCount']==12
    assert len(left)==len(set(left)) and len(right)==len(set(right)) and len(ids)==len(set(ids))


def test_match_stable_ids_and_right_shuffle_preserves_mapping(model):
    first=match.candidates(model.quiz_relations,{},'fixed');second=match.candidates(model.quiz_relations,{},'fixed')
    assert first==second
    q=first[0];q['rightItems'].reverse()
    assert match.verify(q,model.quiz_relations) is None
    assert not any(x['id'].startswith(('L1','R1')) for x in q['leftItems']+q['rightItems'])


def test_core_views_and_cloze_preserved(model):
    before={kind:dk.generate(kind,model,'Fixture',{}) for kind in ['KEY_CONCEPTS','FLASHCARDS','EXTRACTIVE_SUMMARY','MIND_MAP']}
    quiz.generate_from_knowledge(model,{'questionTypes':['mcq','matching'],'questionCount':12})
    assert before=={kind:dk.generate(kind,model,'Fixture',{}) for kind in before}


def test_purpose_and_composition_templates_only_use_supported_relations():
    texts=['Encryption is used for transforming readable records into protected ciphertext.',
           'Authentication is used for verifying the identity of an accessing principal.',
           'Authorization is used for determining permissions granted to verified identities.',
           'Checksum is used for detecting accidental corruption of transmitted information.']
    m=dk.build([{'chunk_id':'purpose','page':1,'text':'\n'.join(texts)}]);r.attach(m)
    qs=mcq.candidates(m.quiz_relations,{})
    assert qs and all(q['relationFamily']=='PURPOSE' and 'used for' in q['question'] for q in qs)


def test_numeric_relations_bind_attribute_value_and_source():
    chunks=[{'chunk_id':f'c{i}','page':1,'text':f'{label}\nTimeout interval: {value}'}
            for i,(label,value) in enumerate([('Alpha Protocol','10 seconds'),('Beta Protocol','20 minutes'),('Gamma Protocol','30 hours'),('Delta Protocol','40 days')])]
    m=dk.build(chunks);r.attach(m)
    qs=mcq.candidates(m.quiz_relations,{})
    assert qs and all(q['relationFamily']=='NUMERIC:timeout interval' for q in qs)
    assert all(q['correctAnswer'] in {'10 seconds','20 minutes','30 hours','40 days'} for q in qs)
    assert not r.equivalent('10 seconds','20 seconds')
    assert r.equivalent('20 seconds','20000 ms')


def test_relation_semantic_peers_reuse_existing_batch(model,monkeypatch):
    from rag.services import knowledge_encoder
    monkeypatch.setattr(knowledge_encoder,'encode',lambda _:pytest.fail('Extra semantic encoder call'))
    left,right=model.quiz_relations[:2]
    model.quiz_semantic_pairs=[[left['subjectText'],right['subjectText']]]
    model.quiz_relation_semantic_prepared=False
    r.attach(model)
    assert right['id'] in left['semanticPeers'] and not r.compatible(left,right,model.quiz_relations)
    before=deepcopy(model.quiz_relations);r.attach(model);assert before==model.quiz_relations
