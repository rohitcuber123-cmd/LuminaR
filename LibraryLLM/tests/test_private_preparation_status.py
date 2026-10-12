from concurrent.futures import ThreadPoolExecutor
from threading import Event,RLock
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.dependencies import get_current_user
from rag.services.private_document_routes import install_private_documents


def test_preparation_status_scoped_and_removed_and_cpu_does_not_hold_gpu_lock():
    started,finish=Event(),Event();gpu=RLock()
    def ingest(content,filename,user,embedding_lock,progress):
        assert embedding_lock is gpu
        progress('READING_SCANNED_PAGES');started.set();assert finish.wait(5)
        return {'document_id':'test'}
    service=SimpleNamespace(identity=lambda user:(user['sub'],user['sid']),ingest=ingest,sweep=lambda:None)
    app=FastAPI();install_private_documents(app,service,SimpleNamespace(inference_lock=gpu))
    current={'sub':'1','sid':'first'};app.dependency_overrides[get_current_user]=lambda:current.copy()
    key=str(uuid4())
    with TestClient(app) as client,ThreadPoolExecutor(max_workers=1) as pool:
        # Avoid lifecycle sweep: the dummy has no private files/SQLite state.
        future=pool.submit(client.post,'/rag/upload',headers={'X-Luminar-Preparation':key},files={'file':('fixture.pdf',b'%PDF-fixture')})
        assert started.wait(5)
        try:
            assert gpu.acquire(blocking=False);gpu.release()
            assert client.get('/rag/preparation/'+key).json()=={'stage':'READING_SCANNED_PAGES'}
            current['sid']='second';assert client.get('/rag/preparation/'+key).status_code==404
            current['sid']='first'
            assert client.post('/rag/upload',headers={'X-Luminar-Preparation':key},files={'file':('fixture.pdf',b'%PDF-fixture')}).status_code==429
        finally:finish.set()
        assert future.result().status_code==200
        assert client.get('/rag/preparation/'+key).status_code==404


def test_invalid_preparation_id_never_creates_status():
    app=FastAPI();service=SimpleNamespace(identity=lambda u:(u['sub'],u['sid']))
    install_private_documents(app,service,SimpleNamespace(inference_lock=RLock()))
    app.dependency_overrides[get_current_user]=lambda:{'sub':'1','sid':'s'}
    client=TestClient(app)
    assert client.get('/rag/preparation/bad').status_code==422
    assert client.post('/rag/upload',headers={'X-Luminar-Preparation':'bad'},files={'file':('fixture.pdf',b'%PDF-fixture')}).status_code==422
