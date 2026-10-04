"""Authenticated Core CRUD against a disposable Mongo DB and queue only."""
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
load_dotenv(ROOT/'.env')
name='luminar_lexical_batch3_'+uuid.uuid4().hex
if not name.startswith('luminar_lexical_batch3_'):
    raise RuntimeError('Unsafe isolated database name')


def run():
    with tempfile.TemporaryDirectory(prefix='luminar-core-lexical-') as temporary:
        root=Path(temporary)
        os.environ['MONGO_DB_NAME']=name
        os.environ['LUMINAR_SEARCH_INDEX_DIR']=str(root/'queue')
        os.environ['JWT_SECRET_KEY']='isolated-test-signing-key-'+uuid.uuid4().hex
        os.environ['LUMINAR_LEXICAL_SYNC_ENABLED']='false'
        os.environ['LEXICAL_SEARCH_ENABLED']='false'

        # Imports follow isolated environment binding. No production queue or
        # catalogue collection is opened by this process.
        from fastapi.testclient import TestClient
        from pymongo import MongoClient
        from backend.main import app
        from backend.services.auth_service import hash_password
        from backend.database.mongodb import (users_collection,books_collection,
                                              library_inventory_collection,issues_collection)
        from search.lexical_build import build_snapshot
        from search.lexical_delta import initialize_delta,LexicalDeltaWriter,LexicalOverlayStore
        from search.sync_queue import SyncQueue,index_root

        client=MongoClient(os.getenv('MONGO_URI','mongodb://localhost:27017'),
                           serverSelectionTimeoutMS=3000)
        if books_collection.database.name!=name or index_root()!=root/'queue':
            raise RuntimeError('Core did not bind to isolated database and queue')
        client.admin.command('ping')
        api=TestClient(app)
        password='Isolated Admin '+uuid.uuid4().hex
        email='batch3-'+uuid.uuid4().hex+'@example.com'
        work_id='TESTLEX'+uuid.uuid4().hex.upper()
        lexical_root=root/'lexical'
        lexical_root.mkdir()
        writer=None
        reader=None
        try:
            users_collection.insert_one({'user_id':1,'name':'Isolated admin',
                                         'email':email,'password_hash':hash_password(password),
                                         'role':'ADMIN','is_email_verified':True,'is_active':True})
            assert api.post('/books/',json={'work_id':work_id,'title':'Unauthorized'}).status_code in (401,403)
            login=api.post('/auth/staff-login',json={'email':email,'password':password})
            assert login.status_code==200,login.json().get('detail')
            token=login.json()['access_token']
            headers={'Authorization':'Bearer '+token}
            queue=SyncQueue(index_root())
            manifest=build_snapshot([{'work_id':'BASE_FIXTURE','title':'Base fixture',
                                      'authors':['Fixture author']}],lexical_root,source_db=name)
            initialize_delta(lexical_root,manifest,0,queue)
            writer=LexicalDeltaWriter(lexical_root,books_collection,queue,
                                      expected_source_db=name)
            reader=LexicalOverlayStore(lexical_root,expected_source_db=name,event_queue=queue)
            generation=writer.status()['lexical_generation']

            create=api.post('/books/',headers=headers,json={
                'work_id':work_id,'title':'Synthetic First Title',
                'authors':'Synthetic First Author','description':'Synthetic test book',
                'total_copies':1,'available_copies':1})
            assert create.status_code==200,create.text
            assert books_collection.count_documents({'work_id':work_id})==1
            assert queue.latest()==1 and writer.process_once()
            assert reader.exact('TITLE','Synthetic First Title')==[
                ('synthetic first title',work_id)]
            assert reader.exact('AUTHOR','Synthetic First Author')==[
                ('synthetic first author',work_id)]
            assert writer.status()['lexical_generation']==generation+1

            inventory=api.put('/books/'+work_id,headers=headers,
                              json={'available_copies':0})
            assert inventory.status_code==200,inventory.text
            assert queue.latest()==1 and not writer.process_once()
            assert writer.status()['lexical_generation']==generation+1
            assert books_collection.find_one({'work_id':work_id})['available_copies']==0

            title=api.put('/books/'+work_id,headers=headers,
                          json={'title':'Synthetic Revised Title'})
            assert title.status_code==200,title.text
            assert queue.latest()==2 and writer.process_once()
            assert reader.exact('TITLE','Synthetic First Title')==[]
            assert reader.exact('TITLE','Synthetic Revised Title')==[
                ('synthetic revised title',work_id)]
            assert writer.status()['lexical_generation']==generation+2

            author=api.put('/books/'+work_id,headers=headers,
                           json={'authors':'Synthetic Revised Author'})
            assert author.status_code==200,author.text
            assert queue.latest()==3 and writer.process_once()
            assert reader.exact('AUTHOR','Synthetic First Author')==[]
            assert reader.exact('AUTHOR','Synthetic Revised Author')==[
                ('synthetic revised author',work_id)]
            assert writer.status()['lexical_generation']==generation+3

            description=api.put('/books/'+work_id,headers=headers,
                                json={'description':'Description changed only'})
            assert description.status_code==200,description.text
            assert queue.latest()==4 and writer.process_once()
            assert writer.status()['lexical_generation']==generation+3
            assert writer.status()['source_event_checkpoint']==4

            deleted=api.delete('/books/'+work_id,headers=headers)
            assert deleted.status_code==200,deleted.text
            assert queue.latest()==5 and writer.process_once()
            assert books_collection.count_documents({'work_id':work_id})==0
            assert reader.exact('TITLE','Synthetic Revised Title')==[]
            assert reader.exact('AUTHOR','Synthetic Revised Author')==[]
            assert reader.work_id(work_id)==[]
            assert writer.status()['tombstone_count']==1
            assert writer.status()['source_event_checkpoint']==5
            assert library_inventory_collection.count_documents({'work_id':work_id})==0
            assert issues_collection.count_documents({'work_id':work_id})==0
            return {'database':'isolated','authenticated_core_routes':True,
                    'create':'PASS','inventory_only':'PASS','title':'PASS',
                    'author':'PASS','description_only':'PASS','delete':'PASS',
                    'cleanup':'PASS','source_checkpoint':5,
                    'lexical_generation':writer.status()['lexical_generation']}
        finally:
            if reader is not None: reader.close()
            if writer is not None: writer.close()
            # This name was generated by this fixture, and only its isolated
            # database is dropped after route-level cleanup assertions.
            client.drop_database(name)
            client.close()


if __name__=='__main__':
    print(json.dumps(run(),indent=2))
