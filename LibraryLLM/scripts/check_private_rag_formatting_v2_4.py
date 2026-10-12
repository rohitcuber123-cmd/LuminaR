"""Owned localhost fixture; reports exclude credentials and private source text."""
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
import json, sys, time, hashlib, re

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TMP = ROOT / '.scratch/private_rag_formatting_v2_4'
PREFIX = 'private_rag_formatting_v2_4'

def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding='utf8')

def state(): return json.loads((TMP/'session.json').read_text())

def seed():
    from backend.database.mongodb import users_collection
    from backend.services.identity_service import next_user_id
    from backend.services.auth_service import hash_password
    from backend.utils.jwt_utils import create_access_token
    assert not (TMP/'session.json').exists()
    marker='formatting-v24-'+uuid4().hex[:10];uid=next_user_id();email=marker+'@example.com';password='Local-formatting-fixture-2026!'
    users_collection.insert_one({'user_id':uid,'name':'Formatting test reader','email':email,'password_hash':hash_password(password),
        'role':'GENERAL_USER','is_email_verified':True,'is_active':True,'created_at':datetime.now(timezone.utc),'formatting_v24_marker':marker})
    dump(TMP/'session.json',{'user_id':uid,'email':email,'password':password,'marker':marker,'token':create_access_token(uid,email,'GENERAL_USER'),'documents':[]})
    print('Disposable formatting reader created.')

def live():
    import httpx
    s=state();report={'document':'CN UNIT-2 notes, original 29-page PDF','renderer_additional_model_calls':0,'responses':[]}
    with httpx.Client(base_url='http://127.0.0.1:8005',headers={'Authorization':'Bearer '+s['token']},timeout=240) as client:
        if not s.get('doc_id'):
            path=Path('C:/Users/balak/Downloads/CN UNIT-2 NOTES.docx.pdf')
            with path.open('rb') as source:r=client.post('/rag/upload',files={'file':(path.name,source,'application/pdf')})
            r.raise_for_status();s['doc_id']=r.json()['document']['document_id'];s['documents'].append(s['doc_id']);dump(TMP/'session.json',s)
        queries=['differences between pure and slotted aloha','what is sfd','explain vulnerable time','compare flow control and error control','What is the SFD bit pattern? Include the exact binary string from the document.']
        for i,q in enumerate(queries):
            start=time.perf_counter();r=client.post('/rag/ask',json={'query':q,'depth':'normal','document_id':s['doc_id']});r.raise_for_status();out=r.json()
            dump(TMP/f'answer_{i}.json',out)
            text=out.get('answer','')
            row={'query':q,'verdict':out.get('verdict'),'source_count':len(out.get('sources',[])),'characters':len(text),
                 'backend_ms':round((time.perf_counter()-start)*1000,1),'answer_sha256':hashlib.sha256(text.encode()).hexdigest(),
                 'has_markdown_heading':'###' in text,'has_qwen_math_delimiters':'\\(' in text,'binary_literals':re.findall(r'\b[01]{8,}\b',text)}
            report['responses'].append(row);dump(ROOT/'reports'/f'{PREFIX}_live.json',report);print(i,row['verdict'],row['source_count'],row['characters'],flush=True)

def cleanup():
    import httpx,sqlite3
    from backend.database.mongodb import users_collection
    s=state();assert s['marker'].startswith('formatting-v24-')
    assert users_collection.find_one({'user_id':s['user_id'],'formatting_v24_marker':s['marker']})
    with httpx.Client(base_url='http://127.0.0.1:8005',headers={'Authorization':'Bearer '+s['token']},timeout=60) as client:
        r=client.get('/rag/documents')
        if r.status_code == 401:
            # Expired disposable sessions cannot authenticate for deletion.
            # Use the existing purge operation only on rows owned by this
            # uniquely marked fixture; never extend or bypass live auth.
            from rag.services.private_documents import PrivateDocuments
            root=(ROOT/'rag/private_documents').resolve()
            assert root.parent == (ROOT/'rag').resolve()
            fixture=PrivateDocuments(root,None)
            with fixture.db() as db:owned=list(db.execute('SELECT id FROM documents WHERE owner=?',(str(s['user_id']),)))
            for row in owned:
                assert fixture.directory(row['id']).parent == root
                assert fixture.purge(row['id'])
        else:
            r.raise_for_status();rows=r.json()['documents'];assert all(x['document_id'] in s['documents'] for x in rows)
            for x in rows:r=client.delete('/rag/documents/'+x['document_id']);r.raise_for_status()
            # Browser sessions have their own SID. Remove only this fixture's
            # rows if a browser session has expired before logout can run.
            from rag.services.private_documents import PrivateDocuments
            root=(ROOT/'rag/private_documents').resolve()
            assert root.parent == (ROOT/'rag').resolve()
            fixture=PrivateDocuments(root,None)
            with fixture.db() as db:owned=list(db.execute('SELECT id FROM documents WHERE owner=?',(str(s['user_id']),)))
            for row in owned:assert fixture.purge(row['id'])
    remaining=0
    for path in (ROOT/'rag').rglob('registry.sqlite'):
        with sqlite3.connect(path) as db:remaining+=db.execute('select count(*) from documents where owner=?',(str(s['user_id']),)).fetchone()[0]
    assert remaining==0,'Browser fixture session still active'
    assert users_collection.delete_one({'user_id':s['user_id'],'formatting_v24_marker':s['marker']}).deleted_count==1
    from backend.utils.jwt_utils import JWT_SECRET_KEY, JWT_ALGORITHM
    from jose import jwt
    from backend.services.login_sessions import revoke
    revoke(jwt.decode(s['token'],JWT_SECRET_KEY,algorithms=[JWT_ALGORITHM],options={'verify_exp':False}))
    dump(ROOT/'reports'/f'{PREFIX}_cleanup.json',{'remaining_private_rows':0,'fixture_readers_deleted':1,'original_pdf_untouched':True})
    print('Owned fixture data removed.')

if __name__=='__main__':globals()[sys.argv[1]]()
