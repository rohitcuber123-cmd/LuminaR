"""Fresh Core access evidence and production Assistant with a controlled parser."""
from uuid import uuid4
from types import SimpleNamespace
import asyncio
import pytest
from backend.database.mongodb import db
from backend.services import library_asset_service as assets
from assistant.schemas import AssistantIntentDecision,Intent,ReferenceScope
from tests.institution_v2q_ai.test_integration import fixture,chat


def ready_asset(client,lib,book,tmp_path,monkeypatch,visibility='MEMBERS'):
    monkeypatch.setenv('LIBRARY_ASSET_ROOT',str(tmp_path))
    import pymupdf
    doc=pymupdf.open();page=doc.new_page();page.insert_text((50,50),'Synthetic authorized text.');pdf=doc.tobytes();doc.close()
    r=client.post(f'/libraries/{lib}/assets',headers={'X-Luminar-Upload':str(uuid4())},
        data={'title':'Private synthetic manual','visibility':visibility,'library_book_id':book},files={'file':('fixture.pdf',pdf,'application/pdf')})
    assert r.status_code==202,r.text
    asset=r.json().get('asset',r.json());identity=asset['asset_id'];generation=str(uuid4())
    db.institution_library_assets.update_one({'asset_id':identity},{'$set':{'status':'READY','active_generation_id':generation}})
    row=db.institution_library_assets.find_one({'asset_id':identity});directory=assets.artifacts_path(row);directory.mkdir(parents=True)
    for name in assets.ARTIFACT_FILES:(directory/name).write_bytes(b'{}')
    return identity,row


class DigitalParser:
    async def parse(self,message,context):
        return AssistantIntentDecision(intent=Intent.CHECK_AVAILABILITY,confidence=1,
            reference_scope=ReferenceScope.CURRENT_PAGE_BOOK,reference_position='ALL')
    async def respond(self,*args):raise AssertionError('Digital facts must not be paraphrased by Qwen')


@pytest.mark.parametrize('query',['Is there a digital version?','Can I read this online?','Does this book have a PDF?',
    'Can I access the ebook?','Is it available digitally?','Which one has an accessible PDF?'])
def test_authorized_local_pdf_is_not_physical_stock(client,fixture,tmp_path,monkeypatch,query):
    api,libs,books,_=fixture;api.app.state.assistant.qwen=DigitalParser()
    asset,_=ready_asset(client,libs[0],books[0],tmp_path,monkeypatch)
    response=chat(fixture,libs[0],message=query,page_context={'work_id':books[0]}).json()
    assert not response['errors'] and response['availability']==[],response
    digital=response['digital_availability'][0]
    assert digital['status']=='AUTHORIZED' and digital['access_authorized'] and digital['full_text_accessible']
    assert digital['resources'][0]['asset_id']==asset
    assert 'available copies' not in response['message'] and 'PDF' in response['message']
    assert client.get(f'/libraries/{libs[0]}/assets/{asset}/file',headers={'x-test-user':'2'}).status_code==200


@pytest.mark.parametrize('kind',['absent','restricted','foreign','missing_source','processing','external_link'])
def test_unknown_hides_inaccessible_or_unverified_assets(client,fixture,tmp_path,monkeypatch,kind):
    api,libs,books,_=fixture;api.app.state.assistant.qwen=DigitalParser()
    if kind in ['restricted','foreign','missing_source','processing']:
        asset,row=ready_asset(client,libs[1] if kind=='foreign' else libs[0],books[1] if kind=='foreign' else books[0],tmp_path,monkeypatch,'STAFF_ONLY' if kind=='restricted' else 'MEMBERS')
        if kind=='missing_source':assets.source_path(row).unlink()
        if kind=='processing':db.institution_library_assets.update_one({'asset_id':asset},{'$set':{'status':'PROCESSING'}})
    if kind=='external_link':db.institution_library_books.update_one({'library_book_id':books[0]},{'$set':{'online_url':'https://example.com/preview.pdf'}})
    r=chat(fixture,libs[0],message='Can I read this online?',page_context={'work_id':books[0]}).json()
    assert not r['errors'],r
    d=r['digital_availability'][0];assert d['status']=='UNKNOWN' and d['resources']==[]
    assert d['asset_present'] is None and d['access_authorized'] is None
    assert 'cannot be verified' in r['message'] and 'available copies' not in r['message']


def test_no_stock_does_not_cancel_authorized_digital_access(client,fixture,tmp_path,monkeypatch):
    api,libs,books,_=fixture;api.app.state.assistant.qwen=DigitalParser()
    ready_asset(client,libs[0],books[0],tmp_path,monkeypatch)
    db.institution_copies.update_many({'library_book_id':books[0]},{'$set':{'status':'ON_LOAN'}})
    result=chat(fixture,libs[0],message='Does it have a digital version?',page_context={'work_id':books[0]}).json()
    assert result['digital_availability'][0]['status']=='AUTHORIZED'


def test_digital_only_local_creation_without_holdings(client,fixture,tmp_path,monkeypatch):
    _,libs,_,_=fixture
    r=client.post(f'/libraries/{libs[0]}/inventory/books',json={'title':'Local digital only','subjects':['Technical education'],'create_physical_holding':False,'copies':0,'idempotency_key':str(uuid4())})
    assert r.status_code==201,r.text
    book=r.json()['library_book_id'];ready_asset(client,libs[0],book,tmp_path,monkeypatch)
    result=client.get(f'/libraries/{libs[0]}/catalogue/books/{book}/digital-availability',headers={'x-test-user':'2'})
    assert result.status_code==200 and result.json()['status']=='AUTHORIZED'
    assert db.institution_holdings.count_documents({'library_book_id':book})==0


def test_foreign_book_and_revoked_member_denied(client,fixture):
    api,libs,books,_=fixture
    assert client.get(f'/libraries/{libs[0]}/catalogue/books/{books[1]}/digital-availability',headers={'x-test-user':'2'}).status_code==404
    db.institution_memberships.update_one({'library_id':libs[0],'user_id':2},{'$set':{'status':'REMOVED'}})
    assert client.get(f'/libraries/{libs[0]}/catalogue/books/{books[0]}/digital-availability',headers={'x-test-user':'2'}).status_code==404


def test_membership_proof_forged_scope_and_changed_visibility(client,fixture,tmp_path,monkeypatch):
    api,libs,books,_=fixture;api.app.state.assistant.qwen=DigitalParser()
    asset,_=ready_asset(client,libs[0],books[0],tmp_path,monkeypatch)
    path=f'/libraries/{libs[0]}/catalogue/books/{books[0]}/digital-availability'
    assert client.get(path,headers={'x-test-user':'3'}).status_code==404
    assert client.get(path.replace(libs[0],str(uuid4())),headers={'x-test-user':'2'}).status_code==404
    first=chat(fixture,libs[0],message='Does it have a PDF?',page_context={'work_id':books[0]}).json()
    assert first['digital_availability'][0]['status']=='AUTHORIZED'
    db.institution_library_assets.update_one({'asset_id':asset},{'$set':{'visibility':'STAFF_ONLY'}})
    next_turn=chat(fixture,libs[0],message='Can I read this online?',conversation_id=first['conversation_id'],page_context={'work_id':books[0]}).json()
    assert next_turn['digital_availability'][0]['status']=='UNKNOWN'
    assert asset not in str(next_turn)


def test_global_record_cannot_grant_tenant_document_access(client,fixture,tmp_path,monkeypatch):
    _,libs,books,_=fixture
    ready_asset(client,libs[0],books[0],tmp_path,monkeypatch)
    db.books.insert_one({'work_id':'OL999123W','title':'Same title','available_copies':99})
    db.institution_library_books.update_one({'library_book_id':books[0]},{'$set':{'global_work_id':'OL999123W'}})
    response=client.get('/books/OL999123W/digital-availability',headers={'x-test-user':'2'})
    assert response.status_code==200 and response.json()['status']=='UNKNOWN'
    assert response.json()['resources']==[]


def test_tool_rejects_cross_library_and_injected_link():
    from assistant.digital_availability import lookup
    from assistant.schemas import Book
    from assistant.tools import ToolFailure
    lib=str(uuid4());bid=str(uuid4())
    async def call(*args,**kwargs):
        return {'work_id':bid,'library_id':str(uuid4()),'catalogue_present':True,'status':'UNKNOWN',
            'asset_present':None,'access_authorized':None,'full_text_accessible':None,'resource_link_present':False,'resources':[]}
    tool=SimpleNamespace(catalogue=SimpleNamespace(library_id=lib,transport=SimpleNamespace(call=call)))
    with pytest.raises(ToolFailure):asyncio.run(lookup(tool,Book(work_id=bid)))
    from assistant.schemas import DigitalAvailability
    with pytest.raises(ValueError):DigitalAvailability.model_validate({'work_id':bid,'library_id':lib,'catalogue_present':True,'status':'AUTHORIZED','asset_present':True,'access_authorized':True,'full_text_accessible':True,'resource_link_present':True,'resources':[{'kind':'LIBRARY_DOCUMENT','asset_type':'PDF','asset_id':str(uuid4()),'href':'javascript:alert(1)'}]})


@pytest.mark.parametrize('query',['Does this book explain digital networks?','Is this book about online fraud?',
    'Which book can I borrow physically?','Is the second book available?'])
def test_topic_words_and_physical_questions_do_not_become_digital_queries(query):
    from assistant.digital_availability import digital_question
    assert not digital_question(query)
