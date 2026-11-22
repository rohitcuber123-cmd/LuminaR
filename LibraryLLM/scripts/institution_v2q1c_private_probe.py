"""Real authenticated HTTP private-library/asset matrix on the task-owned lab.

No response text, bearer token, access code or private prompt is persisted.
Generation mode is stated explicitly; controlled mode is not Qwen evidence.
"""
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
from time import perf_counter,sleep
import hashlib,json
import httpx
from pymongo import MongoClient

ROOT=Path(__file__).resolve().parents[1]
SCOPE=ROOT/'.scratch/institution-v2q/continuation/lab'
OUTPUT=ROOT/'reports/institution_v2q1c_private_controlled_final.json'

def main():
    assert not OUTPUT.exists(),'Keep existing experiment evidence; choose a new explicit run name'
    config=json.loads((SCOPE/'configuration.json').read_text());fixture=json.loads((SCOPE/'manifest.json').read_text())
    assert config['database'].startswith('luminar_v2q1c_')
    libraries={lib['alias']:lib for lib in fixture['libraries']}
    aliases={book['library_book_id']:book['alias'] for lib in fixture['libraries'] for book in lib['books']}
    aliases.update({book['work_id']:book['alias'] for book in fixture['global_books']})
    results={'started_at':datetime.now(timezone.utc).isoformat(),'run_id':uuid4().hex,
        'environment':'task-owned isolated DB and HTTP host 18005','model':'Controlled generator; real cached CPU MiniLM and native FAISS/HNSW. NO QWEN.',
        'cases':[],'setup':[],'limits':'External recommendation candidates and Global retrieval are controlled fixtures; no relevance or private Qwen-quality score is inferred.'}
    tokens={}
    def save():OUTPUT.write_text(json.dumps(results,indent=2),encoding='utf8')
    def gate_count():
        file=ROOT/'reports/institution_v2q1c_generator_gate.jsonl'
        return len(file.read_text().splitlines()) if file.exists() else 0
    with httpx.Client(base_url='http://127.0.0.1:18005',timeout=180) as client:
        def request(method,path,user=None,**kwargs):
            return client.request(method,path,headers={'Authorization':'Bearer '+tokens[user]} if user else {},**kwargs)
        def check(identifier,method,path,user,expected,*,no_generation=False,library=None,expected_books=None,expect_denial=False,minimum_generation_calls=0,**kwargs):
            before=gate_count();start=perf_counter()
            response=request(method,path,user,**kwargs);elapsed=(perf_counter()-start)*1000
            try:body=response.json()
            except ValueError:body={}
            books=body.get('books',body.get('results',[])) if isinstance(body,dict) else []
            generated=gate_count()-before
            record={'id':identifier,'user_alias':user,'expected_http':list(expected),'http_status':response.status_code,
                'elapsed_ms':round(elapsed,3),'generator_calls':generated,'expected_generator_calls_zero':no_generation,
                'intent':body.get('intent'),'returned_book_aliases':[aliases.get(book.get('library_book_id') or book.get('work_id'),'UNRECOGNIZED_ID') for book in books],
                'error_codes':[error['code'] for error in body.get('errors',[])],
                'availability':[{'book':aliases.get(item.get('work_id'),'UNRECOGNIZED_ID'),'copies':item.get('available_copies')} for item in body.get('availability',[])],
                'rag_source_scopes':[hashlib.sha256(str(source.get('work_id') or source.get('document_id')).encode()).hexdigest() for source in (body.get('rag') or body).get('sources',[])],
                'search_source':(body.get('source') or {}).get('search_source')}
            record['pass']=response.status_code in expected and (not no_generation or generated==0) and generated>=minimum_generation_calls
            if response.status_code==200:
                if expect_denial:record['pass'] &= not books and not body.get('availability') and not body.get('rag') and bool(body.get('errors') or body.get('clarification'))
                else:record['pass'] &= not body.get('errors')
            if library and books:record['pass'] &= all(book.get('library_id')==library['library_id'] for book in books)
            if expected_books is not None:record['pass'] &= len(books)==expected_books
            if body.get('conversation_id'):record['conversation_hash']=hashlib.sha256(body['conversation_id'].encode()).hexdigest()[:16]
            results['cases'].append(record);save();print(identifier,response.status_code,'PASS' if record['pass'] else 'FAIL',flush=True)
            return body,response
        for user in fixture['users']:
            response=client.post('/auth/login',json={'email':user['email'],'password':config['password']})
            assert response.status_code==200,('fixture login failed',user['label'],response.status_code)
            tokens[user['label']]=response.json()['access_token']
        for alias,users in [('A',['member','librarian','revoked']),('B',['second'])]:
            for user in users:
                response=request('POST',f"/libraries/{libraries[alias]['library_id']}/join",user,json={'access_code':config['private_code']})
                assert response.status_code==200,('private-code rejoin failed',alias,user,response.status_code)
        A,B,I=(libraries[k] for k in ['A','B','I'])
        for lib in [A,B]:
            for asset in lib['assets']:
                for attempt in range(90):
                    response=request('GET',f"/libraries/{lib['library_id']}/assets/{asset['asset_id']}",'owner')
                    assert response.status_code==200,('asset status failed',response.status_code)
                    body=response.json();state=body.get('status',body.get('asset',{}).get('status'))
                    if state in ('READY','FAILED'):break
                    sleep(2)
                results['setup'].append({'asset_library':lib['alias'],'linked':asset['linked'],'status':state})
                save();assert state=='READY',('fixture asset not ready',lib['alias'],state)
        # Explicit initial builds only for these new task-owned libraries.
        for lib in [A,B,I]:
            initial=request('GET',f"/libraries/{lib['library_id']}/intelligence",'owner').json().get('search',{}).get('status')
            if initial!='READY':
                response=request('POST',f"/libraries/{lib['library_id']}/intelligence/builds",'owner',json={'target':'SEARCH_INDEX'})
                assert response.status_code==202,('fixture Search build rejected',lib['alias'],response.status_code)
            for attempt in range(90):
                state=request('GET',f"/libraries/{lib['library_id']}/intelligence",'owner').json()
                current=state.get('search',{}).get('status')
                if current in ('READY','FAILED','RECOVERY_REQUIRED'):break
                sleep(2)
            results['setup'].append({'library':lib['alias'],'search_status':current,'existing_fixture_generation_reused':initial=='READY'})
            save();assert current=='READY',('fixture Search not ready',lib['alias'],current)
        check('PRIVATE_CODE_WRONG','POST',f"/libraries/{A['library_id']}/join",'outsider',(403,),no_generation=True,json={'access_code':'incorrect-task-code'})
        for lib,user in [(A,'member'),(B,'second'),(I,'member')]:
            check('STRUCTURED_SUBJECT_SEARCH_'+lib['alias'],'GET',f"/libraries/{lib['library_id']}/catalogue/search",user,(200,),
                library=lib,params={'search':'computer networks','limit':10,'personalized':'false'})
            body,_=check('NATIVE_SEARCH_'+lib['alias'],'GET',f"/libraries/{lib['library_id']}/catalogue/search",user,(200,),
                library=lib,params={'search':'reliable packet transport','limit':10,'personalized':'false'})
            results['cases'][-1]['native_semantic_observed']=(body.get('source') or {}).get('search_source')=='TENANT_SEMANTIC'
            results['cases'][-1]['pass'] &= results['cases'][-1]['native_semantic_observed'];save()
            check('ASSISTANT_FOR_YOU_'+lib['alias'],'POST','/assistant/chat',user,(200,),library=lib,expected_books=10,
                json={'message':'Recommend','action':'RECOMMEND','library_id':lib['library_id']})
        check('LOCAL_ONLY_SIMILAR','POST','/assistant/chat','member',(200,),library=A,
            json={'message':'Recommend','action':'RECOMMEND_SIMILAR','library_id':A['library_id'],'selected_work_ids':[A['books'][0]['library_book_id']]})
        unavailable,_=check('UNAVAILABLE_LOCAL_HOLDING','POST','/assistant/chat','member',(200,),library=A,
            json={'message':'Check availability','action':'CHECK_AVAILABILITY','library_id':A['library_id'],'selected_work_ids':[A['books'][9]['library_book_id']]})
        assert unavailable['availability'][0]['available_copies']==0
        check('EXACT_NO_MATCH','GET',f"/libraries/{A['library_id']}/catalogue/search",'member',(200,),library=A,expected_books=0,
            params={'search':'Unfindable Q1C fixture title','mode':'EXACT','limit':10})
        owner_conversation,_=check('OWNER_A_CONVERSATION','POST','/assistant/chat','owner',(200,),library=A,
            json={'message':'Recommend','action':'RECOMMEND','library_id':A['library_id']})
        for destination in [B,None]:
            check('CROSS_SCOPE_'+('B' if destination else 'GLOBAL'),'POST','/assistant/chat','owner',(404,),no_generation=True,
                json={'message':'Check availability','action':'CHECK_AVAILABILITY','conversation_id':owner_conversation['conversation_id'],
                    **({'library_id':destination['library_id']} if destination else {}),'selected_work_ids':[A['books'][1]['library_book_id']]})
        check('STALE_CONVERSATION','POST','/assistant/chat','member',(404,),no_generation=True,
            json={'message':'Recommend','action':'RECOMMEND','library_id':A['library_id'],'conversation_id':uuid4().hex})
        check('FOREIGN_BOOK','POST','/assistant/chat','member',(200,),no_generation=True,library=A,expected_books=0,expect_denial=True,
            json={'message':'Check availability','action':'CHECK_AVAILABILITY','library_id':A['library_id'],'selected_work_ids':[B['books'][0]['library_book_id']]})
        assetA=A['assets'][0];assetB=B['assets'][0]
        path=lambda lib,asset:f"/libraries/{lib['library_id']}/assets/{asset['asset_id']}/rag"
        for user in ['member','librarian','owner']:
            check('ASSET_AUTHORIZED_'+user,'POST',path(A,assetA),user,(200,),minimum_generation_calls=1,json={'query':'What calibration code is recorded?'})
        for user in ['outsider','second',None]:
            check('ASSET_DENIED_'+str(user),'POST',path(A,assetA),user,(404,) if user else (401,403),no_generation=True,
                json={'query':'What calibration code is recorded?'})
        check('ASSET_FOREIGN','POST',path(B,assetB),'member',(404,),no_generation=True,json={'query':'What calibration code is recorded?'})
        check('ASSET_FORGED_LIBRARY','POST',f"/libraries/{uuid4()}/assets/{assetA['asset_id']}/rag",'member',(404,),no_generation=True,
            json={'query':'What calibration code is recorded?'})
        check('ASSET_FORGED_ID','POST',f"/libraries/{A['library_id']}/assets/{uuid4()}/rag",'member',(404,),no_generation=True,
            json={'query':'What calibration code is recorded?'})
        check('RAG_NO_PROOF','POST','/rag/ask',None,(401,),no_generation=True,
            json={'query':'What calibration code is recorded?','document_id':f"library:{A['library_id']}:asset:{assetA['asset_id']}"})
        check('PUBLIC_BOOK_NO_READING_PROOF','POST','/rag/ask','member',(403,404),no_generation=True,
            json={'query':'What does this source say?','work_id':fixture['global_books'][0]['work_id']})
        conversation=None
        for asset in A['assets']:
            body,_=check('DOCUMENT_SWITCH_'+str(asset['linked']),'POST','/assistant/chat','member',(200,),minimum_generation_calls=1,
                json={'message':'Question about the selected document','action':'DOCUMENT_QUESTION','library_id':A['library_id'],
                    'conversation_id':conversation,'page_context':{'document_id':f"library:{A['library_id']}:asset:{asset['asset_id']}"}})
            assert body.get('rag',{}).get('asset_id')==asset['asset_id']
            conversation=body['conversation_id']
        check('FOREIGN_DOCUMENT_CONTEXT','POST','/assistant/chat','member',(200,),no_generation=True,expected_books=0,expect_denial=True,
            json={'message':'Question about the selected document','action':'DOCUMENT_QUESTION','library_id':A['library_id'],
                'conversation_id':conversation,'page_context':{'document_id':f"library:{B['library_id']}:asset:{assetB['asset_id']}"}})
        check('INVALID_DOCUMENT_CONTEXT','POST','/assistant/chat','member',(200,),no_generation=True,expected_books=0,expect_denial=True,
            json={'message':'Question about the selected document','action':'DOCUMENT_QUESTION','library_id':A['library_id'],
                'page_context':{'document_id':'invalid-task-document'}})
        former,_=check('BEFORE_REVOCATION','POST','/assistant/chat','revoked',(200,),minimum_generation_calls=1,
            json={'message':'Question about the selected document','action':'DOCUMENT_QUESTION','library_id':A['library_id'],
                'page_context':{'document_id':f"library:{A['library_id']}:asset:{assetA['asset_id']}"}})
        with MongoClient('mongodb://127.0.0.1:27017') as mongo:
            membership=mongo[config['database']].institution_memberships.find_one({'library_id':A['library_id'],'user_id':6})
        changed=request('PATCH',f"/libraries/{A['library_id']}/memberships/{membership['membership_id']}",'owner',json={'status':'REMOVED'})
        assert changed.status_code==200,('revocation failed',changed.status_code)
        check('AFTER_REVOCATION_CONVERSATION','POST','/assistant/chat','revoked',(404,),no_generation=True,
            json={'message':'Question about the selected document','action':'DOCUMENT_QUESTION','library_id':A['library_id'],
                'conversation_id':former['conversation_id'],'page_context':{'document_id':f"library:{A['library_id']}:asset:{assetA['asset_id']}"}})
        check('AFTER_REVOCATION_ASSET','POST',path(A,assetA),'revoked',(404,),no_generation=True,json={'query':'What calibration code is recorded?'})
    results['totals']={'passed':sum(row['pass'] for row in results['cases']),'failed':sum(not row['pass'] for row in results['cases']),
        'real_qwen_calls':0,'controlled_generator_calls':gate_count()}
    save();print(json.dumps(results['totals']),flush=True)

if __name__=='__main__':main()
