"""Actual Core/Search/Recommendation entrypoints with owned data and cached models.

No global rebuild: the isolated global snapshot is deliberately empty. Private
document processing uses the resident encoder adapter; Qwen serving is not claimed.
"""
import json,os,sys,time,threading,socket
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import scripts.institution_v2o_trace
assert os.environ['MONGO_DB_NAME'].startswith('luminar_v2o_fixture_')


def main():
    # Accepted real Core lifespan/Staff login/JWT/tenant operations before Search.
    source=(ROOT/'scripts/institution_v2n_benchmark_child.py').read_text(encoding='utf8').replace('luminar_v2n_fixture_','luminar_v2o_fixture_').replace('    mongo.close()','    pass # Keep the owned shared client for subsequent entrypoints.')
    namespace={'__file__':__file__,'__name__':'o_core_rehearsal'}
    exec(compile(source,str(ROOT/'scripts/institution_v2n_benchmark_child.py'),'exec'),namespace)
    namespace['main']()
    report=json.loads(Path(sys.argv[1]).read_text());report['entrypoints']={}
    def save():Path(sys.argv[1]).write_text(json.dumps(report,indent=2,default=str))
    from backend.database.mongodb import db,client
    from backend.main import app as core
    from backend.utils.jwt_utils import create_access_token
    from fastapi.testclient import TestClient
    headers={'Authorization':'Bearer '+create_access_token(1,'n-bench-1@example.com','GENERAL_USER')}
    api=TestClient(core)
    response=api.post('/libraries/register',headers=headers,json={'name':'Actual entrypoint fixture','slug':'o-'+uuid4().hex,'library_type':'PRIVATE_INSTITUTION','access_mode':'PRIVATE_CODE','access_code':'Owned fixture passphrase'})
    assert response.status_code==201;lib=response.json()['library']['library_id']
    for n in range(3):
        response=api.post(f'/libraries/{lib}/inventory/books',headers=headers,json={'title':f'Networks entrypoint {n}','subjects':['Networks'],'authors':['Fixture author'],'idempotency_key':str(uuid4())})
        assert response.status_code==201,response.text
    import torch,faiss,numpy as np
    torch.set_num_threads(2);faiss.omp_set_num_threads(2)
    index=Path(os.environ['LUMINAR_SEARCH_INDEX_DIR']);index.mkdir(parents=True)
    faiss.write_index(faiss.IndexHNSWFlat(384,32,faiss.METRIC_INNER_PRODUCT),str(index/'hnsw.index'))
    np.save(index/'index_work_ids.npy',np.array([],dtype=str))
    (index/'hnsw_metadata.json').write_text(json.dumps({'model_name':'all-MiniLM-L6-v2','dimension':384,'normalized':True,'metric':'inner_product','vector_count':0}))
    # Warm cache lives in owned root; no 9GB live global graph is loaded or written.
    from search.api import app as search_app,engine
    with TestClient(search_app) as search_api:
        report['entrypoints']['Search']={'startup':'PASS','global_snapshot':'EMPTY_OWNED_FIXTURE_NO_REBUILD','telemetry_enabled':False}
        response=search_api.post('/search',headers=headers,json={'query':'networks','save_history':True})
        assert response.status_code==200,response.text
        report['global_search_http']=response.status_code
        report['manual_builds']=[]
        for target in ['SEARCH_INDEX','KNOWLEDGE_GRAPH']:
            response=api.post(f'/libraries/{lib}/intelligence/builds',headers=headers,json={'target':target});assert response.status_code==202,response.text
            job=response.json();deadline=time.monotonic()+60
            while True:
                row=db.institution_intelligence_jobs.find_one({'job_id':job['job_id']})
                if row['state'] in ['SUCCEEDED','FAILED','RECOVERY_REQUIRED']:break
                assert time.monotonic()<deadline;time.sleep(.1)
            assert row['state']=='SUCCEEDED',row.get('error_code')
            report['manual_builds'].append({'target':target,'state':row['state'],'generation':row['artifact_generation_id']});save()
        response=search_api.get(f'/libraries/{lib}/catalogue/search?search=networks&staff=true',headers=headers)
        assert response.status_code==200,response.text
        report['tenant_search_http']=response.status_code
        # Actual recommendation ASGI entrypoint; request dependency is bridged to
        # the actual Search ASGI handler to avoid contacting a live default port.
        import recommendation.recommendation_service as rec_service
        from recommendation.api import app as rec_app
        original=rec_service.requests.post
        class BridgeResponse:
            def __init__(self,response):self.response=response;self.status_code=response.status_code;self.text=response.text
            def json(self):return self.response.json()
        def bridge(url,**kwargs):
            assert url==rec_service.SEARCH_API_URL
            return BridgeResponse(search_api.post('/search',json=kwargs['json'],headers=kwargs['headers']))
        rec_service.requests.post=bridge
        try:
            response=TestClient(rec_app).get('/recommendations?limit=5',headers=headers);assert response.status_code==200,response.text
            report['entrypoints']['Recommendation']={'http':200,'transport':'Actual ASGI; Search HTTP dependency bridged to actual ASGI, not a network deployment.'}
        finally:rec_service.requests.post=original
        db.institution_memberships.insert_one({'membership_id':str(uuid4()),'library_id':lib,'user_id':4,'role':'GENERAL_USER','status':'ACTIVE'})
        patron_headers={'Authorization':'Bearer '+create_access_token(4,'n-bench-4@example.com','GENERAL_USER')}
        response=api.post(f'/libraries/{lib}/catalogue/recommendations',headers=patron_headers,json={'limit':5})
        assert response.status_code==200,response.text
        report['tenant_recommendations_http']=response.status_code
        # Real upload, fenced document job, actual TXT chunk/embed/FAISS and
        # extractive Knowledge Tools; adapter reuses actual Search encoder.
        content=('A network connects library systems. Network protocols define communication rules. '
                 'Routing selects a path across networks. Reliable delivery uses acknowledgements.\n')*30
        response=api.post(f'/libraries/{lib}/assets',headers={**headers,'X-Luminar-Upload':str(uuid4())},data={'title':'Owned network notes','visibility':'MEMBERS'},files={'file':('network-notes.txt',content.encode(),'text/plain')})
        assert response.status_code in {201,202},response.text
        upload_status=response.status_code
        aid=response.json()['asset_id']
        from rag.services.library_asset_pipeline import LibraryAssetPipeline
        adapter=SimpleNamespace(reranker=SimpleNamespace(retriever=SimpleNamespace(model=engine.embedding_model)),inference_lock=threading.RLock())
        pipeline=LibraryAssetPipeline(adapter,encoder=lambda texts,**kwargs:engine.embedding_model.encode(texts,normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False,**kwargs))
        assert pipeline.run_one()
        asset=db.institution_library_assets.find_one({'asset_id':aid});assert asset['status']=='READY',asset.get('error_code')
        row,directory,manifest,chunks=pipeline.prepared(lib,aid,{'sub':'1'})
        vectors=np.load(directory/'vectors.npy');assert len(vectors)==len(chunks) and chunks
        study=pipeline.generate(lib,aid,{'sub':'1'},'summary','quick')
        assert study
        report['document_pipeline']={'upload_http':upload_status,'status':'READY','chunks':len(chunks),'real_cached_encoder':True,'faiss_validated':True,'private_prepared_retrieval':'PASS','knowledge_summary':'PASS',
                                     'engine_adapter':'Resident actual encoder only; Qwen/RAG API inference not started or claimed.'}
        report['entrypoints']['RAG_Qwen']={'status':'SEPARATE_PROCESS_REHEARSAL_PENDING','reason':'Real Qwen/RAG startup runs separately after Search releases its models; no full5M global deployment qualification.'}
        report['serving_library']=lib;report['artifact_root']=str(Path(os.environ['LIBRARY_INTELLIGENCE_ROOT']).name)
        save()
    client.close();report['completed']=True;save()


if __name__=='__main__':main()
