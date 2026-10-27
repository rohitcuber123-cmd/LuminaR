"""Explicit PRIVATE_CODE privacy; real HTTP, isolated Mongo and FAISS artifacts."""
from uuid import uuid4
import json
from unittest.mock import Mock
import numpy as np
import pytest
from fastapi import HTTPException
from backend.database.mongodb import db
from backend.services import library_intelligence_store as store,library_intelligence_service as intelligence,library_catalogue_experience as catalogue
from search.library_intelligence import TenantIntelligence
from test_intelligence import encoder,book,build

@pytest.fixture
def private(client,library,upload,ready):
    a=library(private=True,name='Private archive A');b=library(owner=3,name='Public B');c=library(owner=3,private=True,name='Private C')
    for lid,user,code in [(a,2,'Isolated fixture access code'),(b,2,None),(b,4,None),(c,4,'Isolated fixture access code')]:
        r=client.post(f'/libraries/{lid}/join',headers={'x-test-user':str(user)},json={'access_code':code} if code else {})
        assert r.status_code==200,r.text
    own=book(client,a,'Aster Vale Restricted Archive Orchid 731');linked=book(client,a,'Public fixture title',linked=True)
    online=book(client,a,'Private member online edition',physical=False)
    member_asset=upload(a,book_id=online['library_book_id']).json();ready(member_asset)
    secret_asset=upload(a,book_id=own['library_book_id'],visibility='STAFF_ONLY').json();ready(secret_asset)
    # Owner 3 authored foreign fixtures, not owner 1.
    for lid in [b,c]:
        r=client.post(f'/libraries/{lid}/inventory/books',headers={'x-test-user':'3'},json={'title':'Other tenant title','subjects':['Foreign'],'create_physical_holding':True,'copies':1,'idempotency_key':str(uuid4())});assert r.status_code==201,r.text
    worker=TenantIntelligence(encoder,lambda pairs:np.ones(len(pairs)),model_version='all-MiniLM-L6-v2:unit')
    search,_=build(a,worker=worker);kg,_=build(a,'KNOWLEDGE_GRAPH',worker)
    return {'a':a,'b':b,'c':c,'book':own,'linked':linked,'online':online,'asset':member_asset,'staff_asset':secret_asset,'worker':worker,'search':search,'kg':kg}

def actor(user):return {'sub':str(user)}
def denied(function,*args,**kwargs):
    with pytest.raises(HTTPException) as e:function(*args,**kwargs)
    assert e.value.status_code==404

def test_private_library_member_search_allowed(private):
    r=private['worker'].semantic(private['a'],actor(2),'archive')
    assert r['source']['search_source']=='TENANT_SEMANTIC' and all(b['library_id']==private['a'] for b in r['results'])

@pytest.mark.parametrize('user',[4,5,9,10])
def test_private_library_outsider_search_denied(private,user):
    encode=Mock(side_effect=AssertionError('Outsider must not query HNSW'));private['worker'].encoder=encode
    denied(private['worker'].semantic,private['a'],actor(user),'archive');encode.assert_not_called()

def test_private_library_member_recommendations_allowed(private):
    r=catalogue.recommendations(private['a'],actor(2),['OL1W'],50)
    assert r['results'] and all(b['library_id']==private['a'] for b in r['results'])

def test_private_library_outsider_recommendations_denied(private):denied(catalogue.recommendations,private['a'],actor(4),['OL1W'],50)

def test_private_library_direct_catalogue_denied(client,private):
    r=client.get(f'/libraries/{private["a"]}/catalogue/books',headers={'x-test-user':'4'});assert r.status_code==404

def test_private_library_direct_book_denied(client,private):
    r=client.get(f'/libraries/{private["a"]}/catalogue/books/{private["book"]["library_book_id"]}',headers={'x-test-user':'4'});assert r.status_code==404

def test_private_library_hnsw_tenant_only(private):
    manifest,rows,index=private['worker'].cache.load(private['a'],'SEARCH_INDEX',private['search']['artifact_generation_id'],intelligence.target_status(private['a'],'SEARCH_INDEX')['manifest_checksum'])
    assert manifest['library_id']==private['a'] and index.ntotal==3
    assert all(row['library_id']==private['a'] for row in rows)
    assert {row['library_book_id'] for row in rows}=={private[k]['library_book_id'] for k in ['book','linked','online']}

def test_private_library_kg_tenant_only(private):
    r=intelligence.graph(private['a'],actor(2));books=[n for n in r['nodes'] if n['type']=='Book']
    assert {n['library_book_id'] for n in books}=={private[k]['library_book_id'] for k in ['book','linked','online']}
    denied(intelligence.graph,private['a'],actor(4))

def test_private_local_only_not_global_searchable(private):
    assert db.books.count_documents({'title':'Aster Vale Restricted Archive Orchid 731'})==0
    assert db.books.count_documents({'library_book_id':private['book']['library_book_id']})==0

def test_private_global_link_does_not_reveal_ownership(private):
    row=db.books.find_one({'work_id':'OL1W'})
    assert not any(field in row for field in ['library_id','library_book_id','accession_number','shelf_location','online_asset_id'])

def test_private_recommendation_no_global_filler(private):
    r=catalogue.recommendations(private['a'],actor(2),['OL999999W','OL1W'],50)
    assert all(b['source']=='LIBRARY' and b['owned_by_current_library'] for b in r['results'])

def test_private_recommendation_no_cross_library_leak(private):
    for lid in [private['b'],private['c']]:
        r=catalogue.recommendations(lid,actor(4),['OL1W'],50)
        assert all(b['library_id']==lid and b['library_book_id']!=private['book']['library_book_id'] for b in r['results'])

def test_private_multi_library_context_isolation(private):
    a=catalogue.recommendations(private['a'],actor(2),[],50);b=catalogue.recommendations(private['b'],actor(2),[],50)
    assert {r['library_book_id'] for r in a['results']}.isdisjoint({r['library_book_id'] for r in b['results']})

def revoke(private):db.institution_memberships.update_one({'library_id':private['a'],'user_id':2},{'$set':{'status':'REMOVED'}})
def test_private_membership_revocation_search_denied(private):
    private['worker'].semantic(private['a'],actor(2),'archive');revoke(private);denied(private['worker'].semantic,private['a'],actor(2),'archive')
def test_private_membership_revocation_recommendation_denied(private):
    catalogue.recommendations(private['a'],actor(2),[],50);revoke(private);denied(catalogue.recommendations,private['a'],actor(2),[],50)
def test_private_membership_revocation_kg_detail_assets_denied(client,private):
    revoke(private)
    for suffix in ['/intelligence/graph',f'/catalogue/books/{private["book"]["library_book_id"]}',f'/assets/{private["asset"]["asset_id"]}',f'/assets/{private["asset"]["asset_id"]}/file']:
        assert client.get('/libraries/'+private['a']+suffix,headers={'x-test-user':'2'}).status_code==404

def test_private_platform_only_no_tenant_access(client,private):
    from datetime import datetime,timezone
    db.platform_role_assignments.insert_one({'user_id':10,'role':'PLATFORM_ADMIN','status':'ACTIVE','approved_by':'QA','approval_ref':'fixture','approved_at':datetime.now(timezone.utc)})
    for suffix in ['/context','/catalogue/books','/intelligence/graph','/inventory/books']:
        assert client.get('/libraries/'+private['a']+suffix,headers={'x-test-user':'10'}).status_code==404
    denied(private['worker'].semantic,private['a'],actor(10),'archive');denied(catalogue.recommendations,private['a'],actor(10),[],50)

def test_private_code_member_not_staff(client,private):
    assert db.institution_memberships.find_one({'library_id':private['a'],'user_id':2})['role']=='GENERAL_USER'
    for suffix in ['/intelligence','/catalogue/books?staff=true']:
        assert client.get('/libraries/'+private['a']+suffix,headers={'x-test-user':'2'}).status_code==403
    assert client.post('/libraries/'+private['a']+'/inventory/books',headers={'x-test-user':'2'},json={'title':'Forbidden staff create','subjects':['Private'],'idempotency_key':str(uuid4())}).status_code==403
    assert client.post('/libraries/'+private['a']+'/intelligence/builds',headers={'x-test-user':'2'},json={'target':'SEARCH_INDEX'}).status_code==403

def test_private_staff_only_asset_hidden_from_member(client,private):
    r=client.get('/libraries/'+private['a']+'/catalogue/books/'+private['book']['library_book_id'],headers={'x-test-user':'2'}).json()['book']
    assert r['book_format']=='PHYSICAL_ONLY' and not r['has_online']
    for user,status in [(2,404),(4,404)]:
        assert client.get('/libraries/'+private['a']+'/assets/'+private['staff_asset']['asset_id'],headers={'x-test-user':str(user)}).status_code==status
