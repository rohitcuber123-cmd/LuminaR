from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import pytest
from rag.services import cloze_grading as g, knowledge_cloze as c, document_knowledge as dk, knowledge_quiz as q
from tests.test_knowledge_artifacts import env

def item(answer,kind=None,source=None):
    source=source or f'The source answer is {answer}.'
    return {'id':'cloze-test','type':'fill_blank','question':'Complete the source sentence: '+source.replace(answer,'_____',1),
        'correctAnswer':answer,'canonicalAnswer':answer,'sourceExcerpt':source,'blankType':kind or g.answer_type(answer),
        'sourceFactId':'fact','subjectId':'subject','relationId':'relation','relationType':'DEFINITION','evidenceUnitIds':['u1'],
        'sourceChunkIds':['c1'],'pageStart':20,'pageEnd':20,'acceptedAliases':c.aliases(answer,source),
        'conflictingTerms':['Go-Back-N','Selective Repeat','ALOHA','CSMA','CRC','checksum','transmission','transition','Error Control','Stop-and-Wait']}

def forbidden(_):
    pytest.fail('Identity/numeric grading called an encoder')

@pytest.mark.parametrize('expected,answer',[
    ('acknowledgement','acknowledgment'),('acknowledgement','acknowlegement'),('Sliding Window','  Sliding   Window  '),
    ('Sliding Window Protocol','sliding-window protocol'),('Go-Back-N','Go Back N'),('Go-Back-N','Go - Back - N'),
    ('ALOHA','aloha'),('transmission','transmisson'),('Sliding Window','Slidng Window'),('ALOHA','ＡＬＯＨＡ')])
def test_cloze_identity_normalization_and_typo(expected,answer):
    assert g.grade(item(expected,'TERM'),answer,forbidden)['verdict']=='CORRECT'

@pytest.mark.parametrize('expected,answer',[
    ('Selective Repeat','Go-Back-N'),('Go-Back-N','Selective Repeat'),('ALOHA','CSMA'),('CRC','checksum'),
    ('transmission','transition'),('ACK','ACC'),('Sliding Window','Stop-and-Wait'),('frame','frames'),
    ('Go-Back-N','Go-Back-M'),('ALOHA','not ALOHA'),('protocol','protocols'),('Flow control','Flow controls')])
def test_cloze_wrong_related_term(expected,answer):
    assert g.grade(item(expected,'TERM'),answer,forbidden)['verdict']=='INCORRECT'

@pytest.mark.parametrize('expected,answer', [('2T','2 T'),('2','2.0'),('5 ms','5 milliseconds'),('5 seconds','5000 ms'),('50%','50.0 percent'),('-2','-2.0'),('2T','2.0Ｔ')])
def test_cloze_number_equivalence(expected,answer):
    assert g.grade(item(expected),answer,forbidden)['verdict']=='CORRECT'

@pytest.mark.parametrize('expected,answer',[('2T','T'),('2','20'),('50%','5%'),('5 seconds','5 milliseconds'),('5 ms','5'),('-2','2'),('2.5','25'),('2T','2')])
def test_cloze_numeric_or_unit_conflict(expected,answer):
    assert g.grade(item(expected),answer,forbidden)['verdict']=='INCORRECT'

def test_cloze_source_alias_acronym():
    value=item('Automatic Repeat reQuest (ARQ)','TERM','Automatic Repeat reQuest (ARQ) resends frames after a missing acknowledgment.')
    assert c.validate(value)
    assert g.grade(value,'ARQ',forbidden)['verdict']=='CORRECT'
    assert g.grade(value,'Automatic Repeat Request',forbidden)['verdict']=='CORRECT'
    assert g.grade(item('acknowledgement','TERM'),'ACK',forbidden)['verdict']=='INCORRECT'

def test_cloze_entity_name_preserves_leading_article():
    assert g.grade(item('THE WHO','ENTITY'),'Who',forbidden)['verdict']=='INCORRECT'

def test_cloze_phrase_semantics_and_partial():
    value=item('controls sender rate so receiver is not overwhelmed','DESCRIPTION')
    cache=g.SemanticCache()
    vectors=lambda texts:[[1,0],[.9,.1],[.9,.1],[.9,.1],[.9,.1]]
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(g,'CACHE',cache)
        assert g.grade(value,'regulates how fast the sender transmits to protect the receiver',vectors)['verdict']=='CORRECT'
        patch.setattr(g,'CACHE',g.SemanticCache())
        assert g.grade(value,'controls sender rate',lambda texts:[[1,0],[.7,.7],[.7,.7],[1,0],[0,1]])['verdict']=='PARTIAL'

@pytest.mark.parametrize('expected,answer',[
    ('allows multiple frames in transit','allows only one frame in transit'),
    ('allows multiple frames in transit','does not allow multiple frames in transit'),
    ('controls the transmission rate','doesn’t control the transmission rate'),
    ('waits for 5 seconds before transmission','waits for 5 milliseconds before transmission'),
    ('controls the transmission rate','Error Control controls the transmission rate')])
def test_cloze_contradiction_overrides_embedding(expected,answer):
    assert g.grade(item(expected,'DESCRIPTION'),answer,forbidden)['verdict']=='INCORRECT'

@pytest.mark.parametrize('answer',[
    'controls sender rate so receiver is overwhelmed',
    'controls receiver rate so sender is not overwhelmed',
    'controls sender rate so receiver is never not overwhelmed'])
def test_cloze_negated_purpose_or_role_reversal(answer):
    value=item('controls sender rate so receiver is not overwhelmed','DESCRIPTION')
    # The reversed two-role clause must not bypass the whole-answer guard.
    if answer=='controls receiver rate so sender is not overwhelmed':
        assert g.grade(value,answer,lambda texts:[[1,0] for _ in texts])['verdict']=='INCORRECT'
    else:
        assert g.grade(value,answer,forbidden)['verdict']=='INCORRECT'

@pytest.mark.parametrize('answer,verdict',[
    ('regulates transmission speed','CORRECT'),
    ('regulates how fast data is sent','CORRECT'),
    ('regulates receiver speed','INCORRECT')])
def test_cloze_bounded_rate_paraphrase(answer,verdict,monkeypatch):
    monkeypatch.setattr(g,'CACHE',g.SemanticCache())
    value=item('controls the transmission rate','DESCRIPTION')
    assert g.grade(value,answer,lambda texts:[[1,0],*[[0,1] for _ in texts[1:]]])['verdict']==verdict

def test_cloze_irrelevant_and_no_partial_for_identity():
    assert g.grade(item('ALOHA','TERM'),'purple elephant',forbidden)['verdict']=='INCORRECT'
    assert g.grade(item('controls the rate','DESCRIPTION'),'purple elephant',lambda texts:[[1,0],*[ [0,1] for _ in texts[1:] ]])['verdict']=='INCORRECT'

def test_cloze_generated_source_identity_and_leak():
    model=dk.build(json.loads((Path(__file__).parent/'fixtures/knowledge_educational.json').read_text()))
    out=q.generate_from_knowledge(model,{'questionTypes':['fill_blank'],'questionCount':12})
    assert len(out['questions'])>=10
    for value in out['questions']:
        assert c.validate(value)
        assert value['sourceFactId'] and value['subjectId'] and value['relationId']
        assert value['canonicalAnswer'] not in value['question']

def test_cloze_ocr_corruption_rejected():
    model=dk.build([{'chunk_id':'scan','page':1,'extraction_method':'OCR','text':'F1ow C0ntr0l is a mechanism that regulates transmission of data frames.'}])
    out=q.generate_from_knowledge(model,{'questionTypes':['fill_blank'],'questionCount':12})
    assert not out['questions']

def grade_url(env,artifact,value):
    return env.base+'/artifacts/'+artifact['id']+'/cloze/'+value['id']+'/grade'

def quiz(env):
    artifact=env.service.generate(env.doc,'quiz',env.user,question_types=['fill_blank'])['artifact']
    assert artifact['content']['questions']
    return artifact,artifact['content']['questions'][0]

def test_cloze_authoritative_grade_route_source_no_store(env):
    artifact,value=quiz(env)
    response=env.client.post(grade_url(env,artifact,value),json={'answer':value['correctAnswer']})
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    assert response.json()['verdict']=='CORRECT'
    assert response.json()['source_pages']==[1]
    assert response.json()['qwen_calls']==response.json()['cuda_calls']==0
    for body in ({'answer':value['correctAnswer'],'canonical_answer':'malicious'},{'answer':2},{'answer':'x'*501}):
        assert env.client.post(grade_url(env,artifact,value),json=body).status_code==422

@pytest.mark.parametrize('sub,sid',[('other','session1'),('owner','wrong-session')])
def test_cloze_cross_user_and_wrong_session_rejected(env,sub,sid):
    from backend.dependencies import get_current_user
    artifact,value=quiz(env)
    env.app.dependency_overrides[get_current_user]=lambda:{**env.user,'sub':sub,'sid':sid}
    assert env.client.post(grade_url(env,artifact,value),json={'answer':value['correctAnswer']}).status_code==404

def test_cloze_deleted_artifact_and_wrong_item_rejected(env):
    artifact,value=quiz(env)
    url=grade_url(env,artifact,value)
    assert env.client.post(url.replace(value['id'],'unknown'),json={'answer':'anything'}).status_code==404
    env.service.delete(env.doc,artifact['id'],env.user)
    assert env.client.post(url,json={'answer':'anything'}).status_code==404

def test_cloze_logout_during_grade_rejected(env,monkeypatch):
    artifact,value=quiz(env);grade=g.grade
    def revoked(*args):
        result=grade(*args);env.docs.logout(env.user);return result
    monkeypatch.setattr(g,'grade',revoked)
    assert env.client.post(grade_url(env,artifact,value),json={'answer':value['correctAnswer']}).status_code in (401,404)

def test_cloze_default_zero_qwen_cuda_and_no_gpu_lock(env,monkeypatch):
    artifact,value=quiz(env)
    env.service.encoder=forbidden
    with ThreadPoolExecutor(max_workers=20) as pool:
        results=list(pool.map(lambda _:env.service.grade_cloze(env.doc,artifact['id'],value['id'],value['correctAnswer'],env.user),range(20)))
    assert all(x['verdict']=='CORRECT' and x['qwen_calls']==x['cuda_calls']==0 for x in results)

def test_cloze_concurrent_distinct_phrases_share_cpu_batch():
    from threading import Barrier
    barrier=Barrier(20);cache=g.SemanticCache();calls=[]
    def encoder(texts):
        calls.append(list(texts));return [[1,0] for _ in texts]
    def check(n):
        barrier.wait();return cache.similarities([f'answer {n}','source','expected'],encoder)
    with ThreadPoolExecutor(max_workers=20) as pool:results=list(pool.map(check,range(20)))
    assert all(x==[1,1] for x in results)
    assert len(calls)<20 and sum(len(x) for x in calls)<60
    assert not cache.jobs

def test_cloze_cache_revision_and_current_facet(env):
    artifact,value=quiz(env)
    path=env.docs.directory(env.doc)/'chunks.json';chunks=json.loads(path.read_text());chunks[0]['text']+=' Changed source.';path.write_text(json.dumps(chunks))
    assert env.client.post(grade_url(env,artifact,value),json={'answer':value['correctAnswer']}).status_code==404
