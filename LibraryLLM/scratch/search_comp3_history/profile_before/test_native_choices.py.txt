from copy import deepcopy
from fastapi import HTTPException
import pytest
from scripts.search_v2c_c5er_offline_native import compile_functions
from .parser import parse_query,validate,decide,executable,normalize,FacetVocabulary

def transformer():
    env={'deepcopy':deepcopy,'HTTPException':HTTPException,'parse_query':parse_query,'validate':validate,'decide':decide,'executable':executable,'normalize':normalize,'FacetVocabulary':FacetVocabulary}
    return compile_functions('search/query_interaction.py',['transformer'],env)['transformer']

@pytest.mark.parametrize('operation',['correction_apply','correction_keep'])
def test_actual_native_correction_transform_resolves_the_issued_vocabulary(operation):
    q='include category Fictiom';p=parse_query(q,['Fiction']);correction=p.corrections[0]
    row={'query':q,'mode':'SMART','filters':{},'omit':[]};choice={'operation':operation,'correction':correction}
    resolved=transformer()(row,choice,None)(p,['Fiction'],{})
    assert executable(resolved) and not resolved.corrections
    if operation=='correction_apply':assert resolved.subjects==['Fiction']
    else:assert not resolved.subjects and correction['from'] in resolved.semantic_text

def test_literal_choice_preserves_native_exact_mode():
    q='Fiction 4';p=parse_query(q,['Fiction']);row={'query':q,'mode':'SMART','filters':{},'omit':[]}
    resolved=transformer()(row,{'operation':'literal'},None)(p,['Fiction'],{})
    assert resolved.mode=='EXACT' and resolved.exact_text==q

def test_append_only_native_completion_cannot_silently_skip_a_blank_slot():
    q='by [empty required creator value]';p=parse_query(q,[]);row={'query':q,'mode':'SMART','filters':{},'omit':[]}
    with pytest.raises(HTTPException) as rejected:transformer()(row,{'operation':'complete','field':'author'},'Aster Vale')(p,[],{})
    assert rejected.value.status_code==422
