"""Local synthetic OCR and real-CN evaluation. Reports omit private source text."""
import json
from pathlib import Path
import sys
import time
import pymupdf as fitz

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
TMP=ROOT/'.scratch/knowledge_tools_v2_1'
TMP.mkdir(parents=True,exist_ok=True)

PAGES=[
    'Network protocols\n\nTCP is a transport protocol that delivers reliable ordered data between applications.\nUDP is a transport protocol that sends datagrams without connection establishment.\nHTTP is an application protocol that transfers web resources between browsers and servers.\nDNS is an application protocol that maps domain names to numerical network addresses.',
    'Network devices\n\nRouter is a network device that forwards packets between separate networks.\nSwitch is a network device that forwards frames using destination hardware addresses.\nHub is a network device that broadcasts received signals to every connected port.\nBridge is a network device that connects segments by filtering local traffic.',
    'Network services\n\nEncryption is a security technique that transforms readable data into protected ciphertext.\nAuthentication is a security technique that verifies the identity of an accessing principal.\nAuthorization is a security technique that determines the permissions granted to verified identities.\nChecksum is an error detection technique that calculates a compact value from transmitted data.'
]

def save(name,value):
    (ROOT/'reports'/name).write_text(json.dumps(value,indent=2),encoding='utf8')

def fixtures():
    for name,kinds in [('native',['text']*3),('scanned',['scan']*3),('mixed',['text','scan','text']),('blank',['blank']),('lowquality',['noise'])]:
        pdf=fitz.open()
        for i,kind in enumerate(kinds):
            page=pdf.new_page(width=595,height=842)
            if kind=='text':
                assert page.insert_textbox(fitz.Rect(48,48,547,770),PAGES[i],fontsize=15)>=0
            elif kind=='scan':
                source=fitz.open();p=source.new_page(width=595,height=842)
                assert p.insert_textbox(fitz.Rect(48,48,547,770),PAGES[i],fontsize=15)>=0
                page.insert_image(page.rect,stream=p.get_pixmap(dpi=220).tobytes('png'))
                source.close()
            elif kind=='noise':
                page.insert_text((48,60),'12345 %%% @@@ 00000 [] {} 987654321')
        pdf.save(TMP/f'{name}.pdf');pdf.close()
    with fitz.open(TMP/'scanned.pdf') as p:
        p[0].get_pixmap(dpi=110).save(TMP/'fixture_review.png')

def ocr():
    from rag.services.document_service import DocumentService
    from rag.services import private_document_ocr as o
    from rag.services.document_knowledge import build
    from rag.services.knowledge_quiz import generate_from_knowledge
    processor=DocumentService.__new__(DocumentService)
    report={'engine':o.capability(),'fixtures':[]}
    for name in ['native','scanned','mixed','blank','lowquality']:
        path=TMP/f'{name}.pdf'
        native=processor.extract_pdf(path)
        start=time.perf_counter();pages,stats=o.prepare(path,native)
        chunks=processor.create_chunks('fixture_'+name,name+'.pdf',pages)
        model=build(chunks)
        quiz=generate_from_knowledge(model,{'questionTypes':['mcq','matching','fill_blank'],'questionCount':12})
        expected={'native':(3,0),'scanned':(0,3),'mixed':(2,1),'blank':(0,0),'lowquality':(0,0)}[name]
        assert (stats['native_pages'],stats['ocr_pages'])==expected,(name,stats)
        assert [p['page'] for p in pages]==list(range(1,len(pages)+1))
        if name in {'scanned','mixed'}:
            assert model.concepts and quiz['generatedCounts']['mcq'] and quiz['generatedCounts']['matching']
        report['fixtures'].append({'name':name,'stats':stats,'methods':[p['extraction_method'] for p in pages],
            'chunks':len(chunks),'concepts':len(model.concepts),'cards':len(__import__('rag.services.document_knowledge',fromlist=['generate']).generate('FLASHCARDS',model,name,{})['cards']),'quiz':quiz['generatedCounts'],
            'total_ms':round((time.perf_counter()-start)*1000,2)})
    save('knowledge_tools_v2_1_ocr.json',report)
    print([(r['name'],r['stats']['native_pages'],r['stats']['ocr_pages']) for r in report['fixtures']])

def cn():
    from rag.services.document_knowledge import DocumentKnowledgeModel
    from rag.services import knowledge_quiz as q,knowledge_quiz_evidence as e,knowledge_encoder
    model=DocumentKnowledgeModel(**json.loads((TMP/'cn_model.json').read_text(encoding='utf8')))
    start=time.perf_counter();e.attach(model,knowledge_encoder.encode)
    prep_ms=round((time.perf_counter()-start)*1000,2)
    report={'source':'real CN 29-page PDF','core_version':model.version,'quiz_facet_version':e.VERSION,'facet_preparation_ms':prep_ms,'runs':[]}
    for types in [['mcq'],['matching'],list(q.QUESTION_TYPES)]:
        start=time.perf_counter();result=q.generate_from_knowledge(model,{'questionTypes':types,'questionCount':12})
        filename='cn_'+','.join(types)+'.json';(TMP/filename).write_text(json.dumps(result,ensure_ascii=False),encoding='utf8')
        report['runs'].append({'types':types,'counts':result['generatedCounts'],'wall_ms':round((time.perf_counter()-start)*1000,2),
            'ids':[r['id'] for r in result['questions']],'coverage':result['coverage']})
    save('knowledge_tools_v2_1_cn_quiz.json',report)
    print([(r['types'],r['counts']) for r in report['runs']])

def seed():
    from datetime import datetime,timezone
    from uuid import uuid4
    from backend.database.mongodb import users_collection
    from backend.services.identity_service import next_user_id
    from backend.services.auth_service import hash_password
    from backend.utils.jwt_utils import create_access_token
    state=TMP/'session.json';assert not state.exists()
    marker='knowledge-v2-1-'+uuid4().hex[:10];uid=next_user_id();email=marker+'@example.com';password='Knowledge-test-local-2026!'
    users_collection.insert_one({'user_id':uid,'name':'Knowledge V2.1 reader','email':email,'password_hash':hash_password(password),
        'role':'GENERAL_USER','is_email_verified':True,'is_active':True,'created_at':datetime.now(timezone.utc),'knowledge_v2_1_marker':marker})
    state.write_text(json.dumps({'user_id':uid,'email':email,'password':password,'marker':marker,
        'token':create_access_token(uid,email,'GENERAL_USER'),'documents':[]}),encoding='utf8')
    print('Created disposable local reader.')

def live():
    import httpx
    state_path=TMP/'session.json';state=json.loads(state_path.read_text());headers={'Authorization':'Bearer '+state['token']}
    report={'router_mode':'existing_qwen','documents':[]}
    with httpx.Client(base_url='http://127.0.0.1:8005',headers=headers,timeout=180) as client:
        for name,path in [('cn',Path('C:/Users/balak/Downloads/CN UNIT-2 NOTES.docx.pdf')),('native',TMP/'native.pdf'),('scanned',TMP/'scanned.pdf'),('mixed',TMP/'mixed.pdf')]:
            start=time.perf_counter()
            with path.open('rb') as file: response=client.post('/rag/upload',files={'file':(path.name,file,'application/pdf')})
            response.raise_for_status();meta=response.json()['document'];doc=meta['document_id'];state['documents'].append(doc)
            state_path.write_text(json.dumps(state));row={'name':name,'id':doc,'preparation_ms':round((time.perf_counter()-start)*1000,2),'pages':meta['pages'],'ocr':meta.get('ocr'),'artifacts':[]};outputs={}
            for kind in ('key-concepts','summary','flashcards','mindmap','quiz','quiz-mcq','quiz-matching'):
                slug='quiz' if kind.startswith('quiz') else kind
                body=({'questionTypes':['mcq','fill_blank','matching'],'questionCount':12} if kind=='quiz' else {'questionTypes':[kind[5:]],'questionCount':12} if kind.startswith('quiz-') else {})
                start=time.perf_counter();response=client.post(f'/rag/documents/{doc}/artifacts/{slug}',json=body);response.raise_for_status()
                result=response.json();artifact=result['artifact'];outputs[kind]=artifact
                item={'kind':kind,'ms':round((time.perf_counter()-start)*1000,2),'cached':result['cached'],'analysis':artifact['analysis'],'counts':artifact['content'].get('generatedCounts')}
                start=time.perf_counter();repeat=client.post(f'/rag/documents/{doc}/artifacts/{slug}',json=body);repeat.raise_for_status()
                assert repeat.json()['cached'] and repeat.json()['artifact']['id']==artifact['id']
                item['cache_ms']=round((time.perf_counter()-start)*1000,2);row['artifacts'].append(item)
            refs=outputs['flashcards']['content']['cards'][0]['sourceChunkIds']
            response=client.get(f'/rag/documents/{doc}/sources/{refs[0]}');response.raise_for_status()
            assert outputs['flashcards']['content']['cards'][0]['sourceExcerpt'] in response.json()['text']
            row['source_verified']=True
            if name=='scanned':
                start=time.perf_counter();answer=client.post('/rag/ask',json={'query':'What does a router do according to this document?','document_id':doc,'depth':'concise'});answer.raise_for_status()
                payload=answer.json();row['ask_document']={'status':answer.status_code,'ms':round((time.perf_counter()-start)*1000,2),'sources':len(payload.get('sources',[])),'answer_present':bool(payload.get('answer'))}
                assert payload.get('answer') and payload.get('sources')
            (TMP/f'live_{name}.json').write_text(json.dumps(outputs,ensure_ascii=False),encoding='utf8')
            report['documents'].append(row);save('knowledge_tools_v2_1_live.json',report)
            print(name,row['pages'],row['ocr'],flush=True)

def cleanup():
    import httpx
    from backend.database.mongodb import users_collection
    state=json.loads((TMP/'session.json').read_text())
    with httpx.Client(base_url='http://127.0.0.1:8005',headers={'Authorization':'Bearer '+state['token']},timeout=30) as client:
        active=client.get('/rag/documents');active.raise_for_status()
        owned=[r['document_id'] for r in active.json()['documents']]
        for doc in owned:
            response=client.delete('/rag/documents/'+doc);response.raise_for_status()
            assert not (ROOT/'rag/private_documents'/doc).exists()
        assert client.get('/rag/documents').json()['count']==0
    import sqlite3
    with sqlite3.connect(ROOT/'rag/private_documents/registry.sqlite') as db:
        assert db.execute('SELECT count(*) FROM documents WHERE owner=?',(str(state['user_id']),)).fetchone()[0]==0
    users_collection.delete_one({'user_id':state['user_id'],'knowledge_v2_1_marker':state['marker']})
    assert users_collection.count_documents({'knowledge_v2_1_marker':state['marker']})==0
    save('knowledge_tools_v2_1_cleanup.json',{'removed_documents':len(owned),'private_directories_remaining':0,'fixture_account_removed':True})
    print('Owned fixture documents and account removed.')

def final_live():
    from concurrent.futures import ThreadPoolExecutor
    from uuid import uuid4
    import httpx
    import psutil
    state_path=TMP/'session.json';state=json.loads(state_path.read_text());headers={'Authorization':'Bearer '+state['token']}
    key=str(uuid4());stages=[];peak_worker_rss=0
    server=next((psutil.Process(c.pid) for c in psutil.net_connections(kind='tcp') if c.laddr.port==8005 and c.status=='LISTEN'),None)
    def upload():
        with (TMP/'scanned.pdf').open('rb') as file:
            return httpx.post('http://127.0.0.1:8005/rag/upload',headers={**headers,'X-Luminar-Preparation':key},files={'file':('scanned.pdf',file,'application/pdf')},timeout=90)
    with ThreadPoolExecutor(max_workers=1) as pool:
        task=pool.submit(upload)
        with httpx.Client(base_url='http://127.0.0.1:8005',headers=headers,timeout=30) as client:
            while not task.done():
                result=client.get('/rag/preparation/'+key)
                if result.status_code==200:stages.append(result.json()['stage'])
                if server:
                    for worker in server.children(recursive=True):
                        try:peak_worker_rss=max(peak_worker_rss,worker.memory_info().rss)
                        except psutil.NoSuchProcess:pass
                time.sleep(.15)
            response=task.result();response.raise_for_status();doc=response.json()['document'];state['documents'].append(doc['document_id']);state_path.write_text(json.dumps(state))
            assert 'READING_SCANNED_PAGES' in stages
            assert client.get('/rag/preparation/'+key).status_code==404
            report={'health':client.get('/health').json(),'observed_stages':sorted(set(stages)),'worker_peak_rss_bytes':peak_worker_rss,'ocr':doc['ocr']}
            exported=client.post('/rag/documents/'+doc['document_id']+'/cache/export');exported.raise_for_status();blob=exported.content
            deleted=client.delete('/rag/documents/'+doc['document_id']);deleted.raise_for_status()
            start=time.perf_counter();restored=client.post('/rag/local-cache/restore',content=blob,headers={'Content-Type':'application/octet-stream'});restored.raise_for_status();meta=restored.json()['document'];state['documents'].append(meta['document_id']);state_path.write_text(json.dumps(state))
            report['cache_restore']={'ms':round((time.perf_counter()-start)*1000,2),'ocr':meta['ocr'],'bundle_bytes':len(blob)}
            path=ROOT/'rag/private_documents'/meta['document_id'];chunks=json.loads((path/'chunks.json').read_text())
            assert all(c['extraction_method']=='OCR' for c in chunks)
            assert not list(path.glob('*.pdf')) and not (path/'extracted.json').exists()
            report['cache_restore']['no_pdf_or_rasters']=True
            question=client.post('/rag/documents/'+meta['document_id']+'/artifacts/quiz',json={'questionTypes':['mcq','matching'],'questionCount':12});question.raise_for_status()
            report['restored_quiz_counts']=question.json()['artifact']['content']['generatedCounts']
            report['private_text_in_report']=False
            save('knowledge_tools_v2_1_final_live.json',report)
            print('OCR status and encrypted restore verified.',report['observed_stages'],report['restored_quiz_counts'])

if __name__=='__main__':
    globals()[sys.argv[1]]()
