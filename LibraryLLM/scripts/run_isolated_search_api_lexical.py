"""Exercise the real /search route with a stub semantic index and isolated Mongo."""
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import uuid
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
load_dotenv(ROOT/'.env')
name='luminar_lexical_batch4_'+uuid.uuid4().hex


def run():
    with tempfile.TemporaryDirectory(prefix='luminar-search-api-lexical-') as temporary:
        root=Path(temporary)
        os.environ['MONGO_DB_NAME']=name
        os.environ['LUMINAR_SEARCH_INDEX_DIR']=str(root/'queue')
        os.environ['JWT_SECRET_KEY']='isolated-test-signing-key-'+uuid.uuid4().hex
        os.environ['LUMINAR_LEXICAL_SYNC_ENABLED']='false'
        os.environ['LEXICAL_SEARCH_ENABLED']='false'

        import numpy as np
        from fastapi.testclient import TestClient
        from pymongo import MongoClient
        from backend.main import app as core_app
        from backend.database.mongodb import users_collection,books_collection
        from backend.services.auth_service import hash_password
        from search.lexical_build import build_snapshot
        from search.lexical_delta import LexicalOverlayStore,initialize_delta,DELTA_FILENAME
        from search.sync_queue import SyncQueue,index_root
        import search.luminar_search as lm

        mongo=MongoClient(os.getenv('MONGO_URI','mongodb://localhost:27017'),
                          serverSelectionTimeoutMS=3000)
        if books_collection.database.name!=name or index_root()!=root/'queue':
            raise RuntimeError('Search test did not bind to isolated database/queue')
        mongo.admin.command('ping')
        password='Isolated Admin '+uuid.uuid4().hex
        email='batch4-'+uuid.uuid4().hex+'@example.com'
        docs=[
            {'work_id':'S','title':'Other','authors':'Someone'},
            {'work_id':'F','title':'Frankenstein','authors':'Mary Shelley'},
            {'work_id':'D','title':'A Tale of Two Cities','authors':'Charles Dickens'},
            {'work_id':'O','title':'1984','authors':'George Orwell'},
            {'work_id':'J','title':'Pride and Prejudice','authors':'Jane Austen'},
            {'work_id':'M','title':'Another Book','authors':'Mary Sheley'},
            {'work_id':'X','title':'Gone from Mongo','authors':'Missing Author'},
        ]
        for doc in docs:
            doc.update(total_copies=1,available_copies=1)
        lexical_root=root/'lexical'
        lexical_root.mkdir()
        store=None
        extra=[]
        try:
            users_collection.insert_one({'user_id':1,'name':'Isolated admin',
                                         'email':email,'password_hash':hash_password(password),
                                         'role':'ADMIN','is_email_verified':True,'is_active':True})
            books_collection.insert_many(doc for doc in docs if doc['work_id']!='X')
            core=TestClient(core_app)
            login=core.post('/auth/staff-login',json={'email':email,'password':password})
            assert login.status_code==200,login.json().get('detail')
            headers={'Authorization':'Bearer '+login.json()['access_token']}
            queue=SyncQueue(index_root())
            manifest=build_snapshot(docs,lexical_root,source_db=name)
            initialize_delta(lexical_root,manifest,0,queue)
            store=LexicalOverlayStore(lexical_root,expected_source_db=name,event_queue=queue)
            assert store.health()['lexical_available']

            engine=lm.LuminaRSearchEngine.__new__(lm.LuminaRSearchEngine)
            engine.device='cpu'
            semantic_ids=['S']
            snapshot=types.SimpleNamespace(
                base=types.SimpleNamespace(ntotal=2),
                delta=types.SimpleNamespace(ntotal=0),
                candidates=lambda vector,count:[{'work_id':wid,'hnsw_score':.9}
                                                for wid in semantic_ids])
            engine.index_manager=types.SimpleNamespace(
                snapshot=snapshot,encode=lambda texts:np.ones((1,8),dtype=np.float32),
                status=lambda:{'index_status':'STALE','active_vectors':2,
                               'semantic_generation':30,'retry_attempts':0},
                start=lambda:None)
            engine.books_collection=books_collection
            engine.library_inventory=books_collection
            engine.reranker=types.SimpleNamespace(
                predict=lambda pairs,**kw:np.array([.95 if 'Title: Other' in pair[1]
                                                    else .1 for pair in pairs]))
            engine.lexical_store=store
            engine.lexical_writer=None
            original=lm.LuminaRSearchEngine
            lm.LuminaRSearchEngine=lambda:engine
            try:
                import search.api as search_api
            finally:
                lm.LuminaRSearchEngine=original
            api=TestClient(search_api.app)
            def query(value):
                return api.post('/search',headers=headers,
                                json={'query':value,'top_k':5,'save_history':False,
                                      'diagnostics':True})
            assert api.post('/search',json={'query':'Frankenstein',
                                           'save_history':False}).status_code==401
            assert api.post('/search',headers={'Authorization':'Bearer bad'},
                            json={'query':'Frankenstein','save_history':False}).status_code==401
            off=query('Frankenstein')
            assert off.status_code==200,off.text
            assert [r['work_id'] for r in off.json()['results']]==['S']
            os.environ['LEXICAL_SEARCH_ENABLED']='true'
            exact=query('Frankenstein')
            assert exact.status_code==200,exact.text
            assert [r['work_id'] for r in exact.json()['results']][:2]==['F','S']
            assert set(exact.json())==set(off.json())
            assert set(exact.json()['results'][0])==set(off.json()['results'][0])
            assert 'diagnostics' not in exact.json()
            author=query('Jane Austen')
            assert author.status_code==200 and author.json()['results'][0]['work_id']=='J'
            for typo,wid in (('frankenstien','F'),('charls dickens','D'),
                             ('george orwel','O')):
                result=query(typo)
                assert result.status_code==200 and wid in [r['work_id'] for r in result.json()['results']],(
                    typo,result.status_code,[r['work_id'] for r in result.json().get('results',[])])
            assert query('mary shelly').json()['results'][0]['work_id']=='S'
            semantic_ids[:]=['F','F','S']
            deduped=query('Frankenstein')
            assert deduped.status_code==200
            ids=[r['work_id'] for r in deduped.json()['results']]
            assert len(ids)==len(set(ids))
            semantic_ids[:]=['X','S']
            missing=query('Gone from Mongo')
            assert missing.status_code==200
            assert [r['work_id'] for r in missing.json()['results']]==['S']
            semantic_ids[:]=['S']

            with ThreadPoolExecutor(max_workers=5) as pool:
                concurrent=list(pool.map(lambda _:query('Frankenstein'),range(5)))
            assert all(response.status_code==200 for response in concurrent)
            assert all(len({r['work_id'] for r in response.json()['results']})==
                       len(response.json()['results']) for response in concurrent)

            # Every failure fixture lives under this temporary test root.
            for condition in ('missing_pointer','bad_pointer','missing_delta','corrupt_delta'):
                fixture=root/condition
                fixture.mkdir()
                if condition=='bad_pointer':
                    (fixture/'active_lexical.json').write_text('bad json',encoding='utf-8')
                if condition in ('missing_delta','corrupt_delta'):
                    build_snapshot([docs[1]],fixture,source_db=name)
                if condition=='corrupt_delta':
                    (fixture/DELTA_FILENAME).write_bytes(b'corrupt')
                broken=LexicalOverlayStore(fixture,expected_source_db=name)
                extra.append(broken)
                assert not broken.health()['lexical_available']
                engine.lexical_store=broken
                fallback=query('Frankenstein')
                assert fallback.status_code==200
                assert [r['work_id'] for r in fallback.json()['results']]==['S']
            engine.lexical_store=types.SimpleNamespace(
                health=lambda:{'lexical_available':True},
                fuzzy=lambda *args:(_ for _ in ()).throw(OSError('simulated lexical error')))
            exception=query('Frankenstein')
            assert exception.status_code==200
            assert [r['work_id'] for r in exception.json()['results']]==['S']
            engine.lexical_store=store
            queue.request(['TEST_STALE'])
            assert not store.health()['lexical_available']
            stale=query('Frankenstein')
            assert stale.status_code==200
            assert [r['work_id'] for r in stale.json()['results']]==['S']
            os.environ['LEXICAL_SEARCH_ENABLED']='false'
            disabled=query('Frankenstein')
            assert disabled.status_code==200
            assert [r['work_id'] for r in disabled.json()['results']]==['S']
            return {'database':'isolated','actual_search_route':True,'auth':True,
                    'flag_off':'PASS','flag_on':'PASS','exact_title':'PASS',
                    'author':'PASS','typos':'PASS','dedupe':'PASS',
                    'mongo_authority':'PASS','fallback':'PASS',
                    'concurrent_completed':len(concurrent),'public_schema':'PASS'}
        finally:
            for item in extra: item.close()
            if store is not None: store.close()
            mongo.drop_database(name)
            mongo.close()


if __name__=='__main__':
    print('RESULT_JSON:'+json.dumps(run(),sort_keys=True))
