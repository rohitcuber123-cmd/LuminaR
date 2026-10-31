"""Actual service methods under one candidate identity, no authority mocks."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import scripts.institution_v2o_trace
assert os.environ['MONGO_DB_NAME'].startswith('luminar_v2o_fixture_')
try:
    from backend.database.mongodb import db,client
    from backend.services import institution_repository as repo
    case=sys.argv[1];lib=os.environ['LUMINAR_V2O_LIBRARY'];actor={'sub':'1'}
    if case=='core':
        repo.ensure_indexes()
        repo.require_readable(lib)
        with repo.library_mutation(lib):repo.audit(lib,'FIXTURE_AUTH_CHECK',1,metadata={'reason':'Owned role qualification'})
        list(db.books.find({}, {'_id':0,'title':1}).limit(3));db.books.estimated_document_count()
    elif case=='recommendation':
        from recommendation.recommendation_service import get_user_behavior,get_book_by_work_id
        get_user_behavior(1);get_book_by_work_id('OL1W')
        from recommendation.api import app
        from fastapi.testclient import TestClient
        from backend.utils.jwt_utils import create_access_token
        response=TestClient(app).get('/feedback',headers={'Authorization':'Bearer '+create_access_token(1,'o@example.com','GENERAL_USER')})
        assert response.status_code==200
    elif case=='rag_metadata':
        from backend.services.library_asset_service import authorize_asset
        authorize_asset(lib,os.environ['LUMINAR_V2O_ASSET'],actor)
    elif case=='native':
        from backend.services import library_intelligence_store as store
        from search.library_intelligence import TenantIntelligence
        store.initialize()
        store.request_build(lib,actor,'KNOWLEDGE_GRAPH')
        def no_embedding(texts):raise AssertionError('KG must not encode')
        worker=TenantIntelligence(no_embedding,model_version='all-MiniLM-L6-v2:owned-role-qualification')
        assert worker.run_one()
        row=repo.collection('intelligence_jobs').find_one({'library_id':lib,'target':'KNOWLEDGE_GRAPH'},sort=[('created_at',-1)])
        assert row['state']=='SUCCEEDED',row.get('error_code')
        store.request_build(lib,actor,'SEARCH_INDEX');job=store.claim('owned-permission-probe')
        assert job and store.heartbeat(job);store.progress(job,'EMBEDDING',1,3)
    client.close()
except Exception as error:
    # Fixed metadata only; driver errors can contain query documents.
    print(type(error).__name__,getattr(error,'code',None),flush=True)
    raise SystemExit(13)
