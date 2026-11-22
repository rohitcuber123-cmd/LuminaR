"""Real authenticated HTTP private-library/asset matrix on the task-owned lab.

No response text, bearer token, access code or private prompt is persisted.
Generation mode is stated explicitly; controlled mode is not Qwen evidence.
"""
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
from time import perf_counter,sleep
import hashlib,json,socket
import httpx
from pymongo import MongoClient

ROOT=Path(__file__).resolve().parents[1]
SCOPE=ROOT/'.scratch/institution-v2q/validator-review/lab'
OUTPUT=ROOT/'reports/institution_v2q2_fixture_setup.json'

def main():
    assert not OUTPUT.exists(),'Keep existing experiment evidence; choose a new explicit run name'
    config=json.loads((SCOPE/'configuration.json').read_text());fixture=json.loads((SCOPE/'manifest.json').read_text())
    assert config['database'].startswith('luminar_v2q2_')
    libraries={lib['alias']:lib for lib in fixture['libraries']}
    aliases={book['library_book_id']:book['alias'] for lib in fixture['libraries'] for book in lib['books']}
    aliases.update({book['work_id']:book['alias'] for book in fixture['global_books']})
    results={'started_at':datetime.now(timezone.utc).isoformat(),'run_id':uuid4().hex,
        'environment':'task-owned isolated DB and HTTP host 18005','model':'REAL_QWEN; setup invokes no inference.',
        'cases':[],'setup':[],'limits':'External recommendation candidates and Global retrieval are controlled fixtures; no relevance or private Qwen-quality score is inferred.'}
    tokens={}
    def save():OUTPUT.write_text(json.dumps(results,indent=2),encoding='utf8')
    def gate_count():
        file=ROOT/'reports/institution_v2q2_generator_gate.jsonl'
        return len(file.read_text().splitlines()) if file.exists() else 0
    for _ in range(120):
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1',18005))==0:break
        sleep(1)
    else:raise RuntimeError('Owned lab not ready')
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
        results['setup_complete']=True;save();print('Owned fixture assets and native Search ready.',flush=True)

if __name__=='__main__':main()

