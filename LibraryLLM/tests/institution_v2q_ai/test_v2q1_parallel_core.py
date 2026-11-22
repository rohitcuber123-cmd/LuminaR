"""Exercise real concurrent Core reads with disposable canonical-library data."""
import asyncio
import hashlib
import json
import time
from threading import Event, Lock
from uuid import uuid4

import httpx
import pytest
from bson import json_util
from assistant.library_scope import LibraryCatalogue
from assistant.tools import ToolFailure
from backend.services import library_catalogue_experience as catalogue
from backend.services import library_lending_journal as journal
from backend.database.mongodb import db
from test_integration import fixture, chat  # noqa: F401 -- shared owned fixture


def test_canonical_library_recommendations_survive_parallel_book_reads(fixture,client,monkeypatch):
    lib=fixture[1][0]
    for number in range(1,12):
        result=client.post(f'/libraries/{lib}/inventory/books',json={
            'title':f'A owned Python acquisition {number}','authors':['Ada'],
            'subjects':['Python'],'copies':2,'idempotency_key':str(uuid4())})
        assert result.status_code==201,result.text
    if journal.state(lib)!='CANONICAL':
        activated=client.post(f'/libraries/{lib}/staff/lending/activate',json={'idempotency_key':str(uuid4())})
        assert activated.status_code==200,activated.text
    original_hydrate=catalogue.hydrate
    def slower_real_hydrate(*args,**kwargs):
        # Exercise contention during ordinary current-holdings reads.
        time.sleep(.08)
        return original_hydrate(*args,**kwargs)
    monkeypatch.setattr(catalogue,'hydrate',slower_real_hydrate)
    transport=fixture[0].app.state.assistant_http_client._transport
    original_handler=transport.handler
    statuses=[];finished=Event();guard=Lock();phase=['before']
    def forward(request):
        result=original_handler(request)
        if '/catalogue/books/' in request.url.path:
            with guard:
                statuses.append((phase[0],result.status_code))
                if sum(label=='before' for label,_ in statuses)>=12:finished.set()
        return result
    async def concurrently_forward(request):
        return await asyncio.to_thread(forward,request)
    fixture[0].app.state.assistant_http_client._transport=httpx.MockTransport(concurrently_forward)
    def snapshot():
        return {name:hashlib.sha256('\n'.join(sorted(json_util.dumps(row,sort_keys=True)
            for row in db[name].find({'library_id':lib}))).encode()).hexdigest()
            for name in ['institution_library_books','institution_holdings','institution_copies']}
    original_snapshot=snapshot()
    fixed_books=LibraryCatalogue.books
    async def prior_parallel_books(self,identities):
        return list(await asyncio.wait_for(asyncio.gather(*(self.book(identity) for identity in dict.fromkeys(identities))),40))
    monkeypatch.setattr(LibraryCatalogue,'books',prior_parallel_books)
    started=time.perf_counter()
    before=chat(fixture,lib,action='RECOMMEND')
    before_ms=(time.perf_counter()-started)*1000
    assert finished.wait(15),'Prior parallel requests did not finish'
    # Q4 fixes the Core authority precheck itself, so the historical parallel
    # client must now succeed too. Keep both paths and the data snapshots.
    assert before.status_code==200 and not before.json()['errors'],before.text
    assert all(status==200 for label,status in statuses if label=='before'),statuses
    assert snapshot()==original_snapshot
    phase[0]='after'
    monkeypatch.setattr(LibraryCatalogue,'books',fixed_books)
    started=time.perf_counter()
    response=chat(fixture,lib,action='RECOMMEND')
    after_ms=(time.perf_counter()-started)*1000
    assert response.status_code==200,response.text
    data=response.json()
    assert not data['errors'],data
    assert len(data['books'])==10,data
    assert all(row['library_id']==lib for row in data['books'])
    assert not any(label=='after' and status>=400 for label,status in statuses),statuses
    assert snapshot()==original_snapshot
    print('V2Q1_SAME_FIXTURE_COMPARISON='+json.dumps({'before_http_status':before.status_code,
        'before_ms':round(before_ms,2),'after_ms':round(after_ms,2),
        'before_core_statuses':[status for label,status in statuses if label=='before'],
        'after_http_status':response.status_code,'after_book_count':len(data['books']),
        'after_core_statuses':[status for label,status in statuses if label=='after'],
        'same_books_holdings_and_copies':True,'snapshot_sha256':original_snapshot,
        'parser':'deterministic; structured action uses no Qwen'}))


def test_failed_lookup_does_not_start_later_book_requests():
    calls=[]
    class FailingCatalogue(LibraryCatalogue):
        async def book(self,identity):
            calls.append(identity)
            raise ToolFailure('core','HTTP_503')
    async def run():
        with pytest.raises(ToolFailure):
            await FailingCatalogue(None,'test').books(['first','second'])
    asyncio.run(run())
    assert calls==['first']


def test_fifty_canonical_candidates_finish_within_existing_deadline(fixture,client):
    lib=fixture[1][0]
    for number in range(1,50):
        result=client.post(f'/libraries/{lib}/inventory/books',json={
            'title':f'A owned Python book {number}','subjects':['Python'],
            'copies':1,'idempotency_key':str(uuid4())})
        assert result.status_code==201,result.text
    if journal.state(lib)!='CANONICAL':
        activated=client.post(f'/libraries/{lib}/staff/lending/activate',json={'idempotency_key':str(uuid4())})
        assert activated.status_code==200,activated.text
    original=fixture[0].app.state.assistant_http_client._transport.handler
    async def forward(request):return await asyncio.to_thread(original,request)
    fixture[0].app.state.assistant_http_client._transport=httpx.MockTransport(forward)
    started=time.perf_counter()
    response=chat(fixture,lib,action='RECOMMEND')
    elapsed=(time.perf_counter()-started)*1000
    assert response.status_code==200,response.text
    data=response.json()
    assert not data['errors'] and len(data['books'])==10 and data['has_more'],data
    assert all(book['library_id']==lib for book in data['books'])
    print('V2Q1_FIFTY_CANDIDATES='+json.dumps({'elapsed_ms':round(elapsed,2),
        'candidates':50,'returned':len(data['books']),'evidence':'owned Core fixture; structured action, no Qwen'}))
