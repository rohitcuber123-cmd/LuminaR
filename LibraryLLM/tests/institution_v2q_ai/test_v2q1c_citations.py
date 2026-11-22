"""Exercise the real unprotected HTTP adapter without loading another model."""
import ast
import contextlib
import copy
import json
import pytest
from pathlib import Path
from threading import RLock
from types import SimpleNamespace
from fastapi import FastAPI,Depends,HTTPException
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from pydantic import BaseModel,model_validator

ROOT=Path(__file__).resolve().parents[2]

def adapted(payload,question='Give the exact page number of the first mention of Jonathan Harker.'):
    tree=ast.parse((ROOT/'rag/api.py').read_text(encoding='utf8'))
    module=ast.Module(body=[node for node in tree.body if isinstance(node,(ast.ClassDef,ast.FunctionDef)) and node.name in {'RAGRequest','ask'}],type_ignores=[])
    namespace={'app':FastAPI(),'BaseModel':BaseModel,'model_validator':model_validator,'Depends':Depends,
        'HTTPException':HTTPException,'HTTPAuthorizationCredentials':HTTPAuthorizationCredentials,
        'optional_auth':HTTPBearer(auto_error=False),'contextlib':contextlib,
        'engine':SimpleNamespace(inference_lock=RLock(),ask=lambda **kwargs:copy.deepcopy(payload)),
        'private_documents':SimpleNamespace(clear_runtime=lambda:None),
        'valid_work_id':lambda value:False,'authorize_selection':lambda *args:None,
        'book_runtime':SimpleNamespace(refresh=lambda:None)}
    exec(compile(module,'rag/api.py','exec'),namespace)
    return namespace['ask'](namespace['RAGRequest'](query=question),None)

def test_recorded_unsupported_page_is_contained_at_http_boundary():
    raw=json.loads((ROOT/'reports/institution_v2q1_public_rag_resumed.json').read_text(encoding='utf8'))
    original=next(row['response'] for row in raw['queries'] if row['id']=='RAG027')
    assert original['answer']=='Page 15' and all(row.get('page') is None for row in original['sources'])
    result=adapted(original)
    assert result['verdict']=='NOT_SUPPORTED'
    assert '15' not in result['answer']
    assert result['sources']==original['sources']

def test_supported_page_and_grounded_answer_are_preserved():
    payload={'question':'On which page is calibration described?','answer':'Calibration is described on page 7.',
             'verdict':'SUPPORTED','sources':[{'page':7,'chunk_id':'owned-fixture'}]}
    assert adapted(payload,payload['question'])==payload

@pytest.mark.parametrize('answer,pages',[
    ('Page 15',[None]),('page 8',[7]),('pp. 3–5',[3,5]),('pages 1 and 15',[1]),
    ('page number: 15',[]),('p. 0',[1]),('pages 1-999999999',[1]),
    ('15',[]),('The answer is on pg. 8.',[7]),
])
def test_unsupported_page_formats_are_contained(answer,pages):
    from rag.citation_boundary import validate_page_claims
    original={'question':'Which page gives the result?','answer':answer,'verdict':'SUPPORTED',
              'sources':[{'page':page} for page in pages]}
    before=copy.deepcopy(original);result=validate_page_claims(original)
    assert result['verdict']=='NOT_SUPPORTED' and original==before

@pytest.mark.parametrize('answer,pages,question',[
    ('Page 7',[7],'Which page?'),('pp. 3–5',[3,4,5],'Which pages?'),
    ('pages 1 and 15',[1,15],'Which pages?'),('7',['7'],'Which page?'),
    ('The book has 15 pages.',[],'How many pages?'),('15',[],'What is the page count?'),
    ('There are 12 available copies.',[],'How many copies?'),
    ('The supplied passages do not establish this.',[],'What evidence exists?'),
])
def test_valid_pages_and_non_citation_facts_are_preserved(answer,pages,question):
    from rag.citation_boundary import validate_page_claims
    payload={'answer':answer,'question':question,'sources':[{'page':p} for p in pages],'verdict':'SUPPORTED'}
    assert validate_page_claims(payload)==payload

def test_null_boolean_and_negative_metadata_cannot_authorize_a_citation():
    from rag.citation_boundary import validate_page_claims
    assert validate_page_claims({'answer':'Page 1','sources':[{'page':True},{'page':-1},{'page':None}]})['verdict']=='NOT_SUPPORTED'

@pytest.mark.parametrize('answer',['Fifteen.','15, according to the book.','It is near the beginning.'])
def test_page_location_question_without_metadata_cannot_escape_by_rewording(answer):
    from rag.citation_boundary import validate_page_claims
    result=validate_page_claims({'question':'Give the exact page number of the first mention.',
        'answer':answer,'sources':[{'page':None}],'verdict':'SUPPORTED'})
    assert result['verdict']=='NOT_SUPPORTED' and 'source metadata' in result['answer']


def test_what_page_count_is_not_a_page_location_request():
    from rag.citation_boundary import validate_page_claims
    original={'question':'What page count is recorded?','answer':'321','verdict':'SUPPORTED','sources':[]}
    assert validate_page_claims(original) is original
