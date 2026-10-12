"""Local disposable-reader evaluation. Reports contain counts/IDs, not PDF text."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from uuid import uuid4
import httpx
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
STATE = ROOT/'.scratch/knowledge_quality/session.json'
OUT = ROOT/'reports/knowledge_quality_live.json'

def save(path,value):
    path.write_text(json.dumps(value,indent=2,default=str),encoding='utf8')

def seed():
    from backend.database.mongodb import users_collection
    from backend.services.identity_service import next_user_id
    from backend.services.auth_service import hash_password
    from backend.utils.jwt_utils import create_access_token
    assert not STATE.exists(), 'Existing test session requires cleanup.'
    marker = 'knowledge-quality-'+uuid4().hex[:10]
    uid, email, password = next_user_id(), marker+'@example.com', 'Knowledge-quality-test-2026!'
    users_collection.insert_one({'user_id':uid,'name':'Knowledge quality reader','email':email,
        'password_hash':hash_password(password),'role':'GENERAL_USER','is_email_verified':True,
        'is_active':True,'created_at':datetime.now(timezone.utc),'knowledge_quality_marker':marker})
    save(STATE,{'user_id':uid,'email':email,'password':password,'marker':marker,
                'token':create_access_token(uid,email,'GENERAL_USER'),'documents':[]})
    print('Disposable reader email:',email)

def run():
    state = json.loads(STATE.read_text(encoding='utf8'))
    headers={'Authorization':'Bearer '+state['token']}
    report={'router_mode':'existing_qwen','documents':[], 'private_text_logged':False}
    fixture = json.loads((ROOT/'tests/fixtures/knowledge_educational.json').read_text())
    pdf = pymupdf.open()
    for c in fixture:
        page=pdf.new_page();page.insert_textbox((35,35,560,800),c['text'],fontsize=11)
    files=[('cn',Path(r'C:\Users\balak\Downloads\CN UNIT-2 NOTES.docx.pdf').read_bytes()),('educational',pdf.tobytes())]
    with httpx.Client(base_url='http://127.0.0.1:8005',headers=headers,timeout=120) as client:
        for name,blob in files:
            start=time.perf_counter()
            response=client.post('/rag/upload',files={'file':(name+'.pdf',blob,'application/pdf')})
            response.raise_for_status();doc=response.json()['document']['document_id']
            state['documents'].append(doc);save(STATE,state)
            row={'name':name,'upload_ms':round((time.perf_counter()-start)*1000,2),'artifacts':[]}
            outputs={}
            for kind in ('key-concepts','summary','flashcards','mindmap','quiz'):
                start=time.perf_counter();body={'questionTypes':['mcq','fill_blank','matching']} if kind=='quiz' else {}
                response=client.post(f'/rag/documents/{doc}/artifacts/{kind}',json=body)
                response.raise_for_status();result=response.json();artifact=result['artifact'];outputs[kind]=artifact
                row['artifacts'].append({'kind':kind,'wall_ms':round((time.perf_counter()-start)*1000,2),
                    'cached':result['cached'],'knowledge_cached':artifact['analysis']['knowledgeCached'],
                    'metrics':artifact['analysis']['metrics']})
            start=time.perf_counter()
            replay=client.post(f'/rag/documents/{doc}/artifacts/key-concepts',json={}).json()
            row['replay']={'cached':replay['cached'],'same_id':replay['artifact']['id']==outputs['key-concepts']['id'],
                           'wall_ms':round((time.perf_counter()-start)*1000,2)}
            for types in (['mcq'],['matching']):
                r=client.post(f'/rag/documents/{doc}/artifacts/quiz',json={'questionTypes':types,'questionCount':12})
                r.raise_for_status();outputs['quiz-'+types[0]]=r.json()['artifact']
            # Temporary outputs are private and removed after manual review.
            save(ROOT/f'.scratch/knowledge_quality/live_{name}.json',outputs)
            start=time.perf_counter()
            response=client.post(f'/__knowledge_quality/{doc}')
            row['quality_pass']={'status':response.status_code,'wall_ms':round((time.perf_counter()-start)*1000,2)}
            if response.is_success: row['quality_pass'].update(response.json())
            report['documents'].append(row);save(OUT,report)
    print(json.dumps(report,indent=2))

def cleanup():
    from backend.database.mongodb import users_collection
    state=json.loads(STATE.read_text(encoding='utf8'))
    with httpx.Client(base_url='http://127.0.0.1:8005',headers={'Authorization':'Bearer '+state['token']}) as client:
        for doc in state['documents']:
            response=client.delete('/rag/documents/'+doc)
            assert response.status_code in (200,404), response.status_code
    users_collection.delete_one({'user_id':state['user_id'],'knowledge_quality_marker':state['marker']})
    STATE.unlink()
    print('Removed only the disposable reader and owned evaluation documents.')

def refresh():
    state=json.loads(STATE.read_text(encoding='utf8'))
    report={'model_version':'3.2.1','documents':[]}
    with httpx.Client(base_url='http://127.0.0.1:8005',headers={'Authorization':'Bearer '+state['token']},timeout=120) as client:
        for name,doc in zip(('cn','educational'),state['documents']):
            outputs={};row={'name':name,'artifacts':[]}
            for kind in ('key-concepts','summary','flashcards','mindmap','quiz','quiz-mcq','quiz-matching'):
                slug='quiz' if kind.startswith('quiz') else kind
                body=({'questionTypes':['mcq','fill_blank','matching'],'questionCount':12} if kind=='quiz'
                      else {'questionTypes':[kind[5:]],'questionCount':12} if kind.startswith('quiz-') else {})
                start=time.perf_counter()
                response=client.post(f'/rag/documents/{doc}/artifacts/{slug}',json=body)
                response.raise_for_status();result=response.json();artifact=result['artifact'];outputs[kind]=artifact
                row['artifacts'].append({'kind':kind,'wall_ms':round((time.perf_counter()-start)*1000,2),
                    'cached':result['cached'],'analysis':artifact['analysis'],'counts':artifact['content'].get('generatedCounts')})
            save(ROOT/f'.scratch/knowledge_quality/live_{name}.json',outputs)
            report['documents'].append(row)
    save(ROOT/'reports/knowledge_quality_final_live.json',report)
    print([(d['name'],[(a['kind'],a['wall_ms'],a.get('counts')) for a in d['artifacts']]) for d in report['documents']])

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['seed','run','refresh','cleanup']);args=parser.parse_args()
    globals()[args.action]()
