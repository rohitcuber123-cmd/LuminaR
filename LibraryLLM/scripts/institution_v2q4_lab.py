"""Task-only isolated AI lab. Never installs a diagnostic route in production.

prepare uses no models; serve refuses a concurrent ordinary RAG process.
All application handlers/guards remain original. Instrumentation is process-local.
"""
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from contextvars import ContextVar
from contextlib import asynccontextmanager
from types import SimpleNamespace
import argparse,asyncio,base64,hashlib,inspect,json,logging,os,re,secrets,socket,sys,time

ROOT=Path(__file__).resolve().parents[1]
SCOPE=(ROOT/'.scratch/institution-v2q/q4-review/lab').resolve()
CONFIG=SCOPE/'configuration.json'
TRACE=ROOT/'reports/institution_v2q4_decision_traces.jsonl'
DIAGNOSTIC=ContextVar('owned_ai_diagnostic',default=None)

def configure(create=False):
    if create:
        assert not CONFIG.exists(),'An owned lab already exists; reuse it explicitly'
        SCOPE.mkdir(parents=True,exist_ok=True)
        config={'database':'luminar_v2q4_'+uuid4().hex[:20],
                'jwt_secret':secrets.token_urlsafe(40),'password':'Disposable-Q4-Local-Only-2026!',
                'private_code':secrets.token_urlsafe(16),'port':18005}
        CONFIG.write_text(json.dumps(config,indent=2),encoding='utf8')
    config=json.loads(CONFIG.read_text(encoding='utf8'))
    assert config['database'].startswith('luminar_v2q4_') and config['database']!='luminar_library'
    assert SCOPE.is_relative_to((ROOT/'.scratch/institution-v2q').resolve())
    os.environ.update(MONGO_URI='mongodb://127.0.0.1:27017',MONGO_DB_NAME=config['database'],
        LUMINAR_MONGO_MODE='DEVELOPMENT',JWT_SECRET_KEY=config['jwt_secret'],
        LUMINAR_SESSION_DB=str(SCOPE/'sessions.sqlite'),LIBRARY_ASSET_ROOT=str(SCOPE/'assets'),
        LIBRARY_INTELLIGENCE_ROOT=str(SCOPE/'intelligence'),
        NOTIFICATION_DUE_WORKER_ENABLED='0',NOTIFICATION_OUTBOX_WORKER_ENABLED='0',
        LUMINAR_WORKER_TELEMETRY_ENABLED='0',ASSISTANT_ROUTER_MODE='existing_qwen',
        ASSISTANT_CORE_URL='http://127.0.0.1:18005',ASSISTANT_SEARCH_URL='http://127.0.0.1:18005',
        ASSISTANT_RECOMMENDATION_URL='http://127.0.0.1:18005',
        ISBN_LOOKUP_DB=str(SCOPE/'no-isbn.duckdb'),ASSISTANT_PROFILE_PATH=str(SCOPE/'numeric_profiles.jsonl'),
        HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',BREVO_API_KEY='',
        KNOW_MORE_CACHE_MASTER_KEY=base64.b64encode(hashlib.sha256((config['jwt_secret']+':q3-cache').encode()).digest()).decode())
    sys.path.insert(0,str(ROOT))
    return config

def prepare():
    config=configure(True)
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.database.mongodb import db
    from backend.services.auth_service import hash_password
    users=[]
    for number,label in enumerate(['owner','member','librarian','second','outsider','revoked'],1):
        email=f'{label}@q4.example.com';users.append({'id':number,'label':label,'email':email})
        db.users.insert_one({'user_id':number,'name':'Disposable '+label,'email':email,
            'password_hash':hash_password(config['password']),'role':'GENERAL_USER',
            'is_email_verified':True,'is_active':True,'password_setup_required':False})
    manifest={'database':config['database'],'scope_root':str(SCOPE),'users':users,'libraries':[],
              'created_at':datetime.now(timezone.utc).isoformat(),'credential_storage':'Task-owned scratch configuration only; no credentials in reports.'}
    with TestClient(app) as client:
        tokens={}
        for user in users:
            response=client.post('/auth/login',json={'email':user['email'],'password':config['password']})
            assert response.status_code==200,response.text
            tokens[user['id']]=response.json()['access_token']
        owner={'Authorization':'Bearer '+tokens[1]}
        topics=[('Network Foundations',['Computer networks','Technical education'],2),
                ('Network Practice',['Computer networks','Technical education'],1),
                ('Database Foundations',['Databases','Technical education'],2),
                ('Database Advanced',['Databases','Research'],1),
                ('Garden Notes',['Gardening'],1),('Duplicate Title',['Computer networks'],1),
                ('Duplicate Title',['Databases'],1),('Sparse Record',['Unclassified'],1),
                ('New Acquisition',['Computer networks'],1),('Unavailable Network',['Computer networks'],0)]
        for letter,kind in [('A','PRIVATE_INSTITUTION'),('B','PRIVATE_INSTITUTION'),('I','PUBLIC_LIBRARY')]:
            private=letter!='I'
            response=client.post('/libraries/register',headers=owner,json={'name':'Q4 '+letter,'slug':'q3-'+letter.lower()+'-'+uuid4().hex[:8],
                'library_type':kind,'access_mode':'PRIVATE_CODE' if private else 'PUBLIC',
                **({'access_code':config['private_code']} if private else {})})
            assert response.status_code==201,response.text
            lib=response.json()['library']['library_id']
            library={'alias':letter,'library_id':lib,'books':[]}
            for number,(title,subjects,copies) in enumerate(topics,1):
                row=client.post(f'/libraries/{lib}/inventory/books',headers=owner,json={'title':f'{letter} {title}',
                    'authors':['Disposable Author'],'subjects':subjects,'copies':max(1,copies),'idempotency_key':str(uuid4())})
                assert row.status_code==201,row.text
                identity=row.json()['library_book_id']
                library['books'].append({'alias':f'{letter}-book-{number:02d}','library_book_id':identity,
                    'title':f'{letter} {title}','subjects':subjects})
                if copies==0:
                    db.institution_holdings.update_one({'library_id':lib,'library_book_id':identity},
                        {'$set':{'available_copies':0,'unavailable_stock':1}})
            for user_id in ([2,3,6] if letter=='A' else [4] if letter=='B' else [2,3]):
                joined=client.post(f'/libraries/{lib}/join',headers={'Authorization':'Bearer '+tokens[user_id]},
                    json={'access_code':config['private_code']} if private else {})
                assert joined.status_code==200,joined.text
            if letter in ('A','I'):
                db.institution_memberships.update_one({'library_id':lib,'user_id':3},{'$set':{'role':'LIBRARIAN'}})
            manifest['libraries'].append(library)
        # These global rows are deterministic retrieval fixtures in the owned
        # DB, never edits to the real five-million-book catalogue.
        manifest['global_books']=[]
        for number,(title,subjects,copies) in enumerate(topics,1):
            work=f'OL{910000000+number}W'
            db.books.insert_one({'work_id':work,'book_id':910000000+number,'title':title,
                'authors':'Disposable Author','subjects':'; '.join(subjects),'total_copies':max(1,copies),'available_copies':copies})
            manifest['global_books'].append({'alias':f'G-book-{number:02d}','work_id':work,'title':title})
        import fitz
        for library in manifest['libraries'][:2]:
            library['assets']=[]
            for linked in ([True,False] if library['alias']=='A' else [True]):
                pdf=fitz.open();page=pdf.new_page()
                for line,text in enumerate([f"Disposable private {library['alias']} sensor manual.",
                    'The calibration code is '+('ALPHA-SEVEN.' if library['alias']=='A' else 'BRAVO-NINE.'),
                    'Routine checks take '+('12 minutes.' if library['alias']=='A' else '47 minutes.')]):
                    page.insert_text((50,70+line*30),text)
                content=pdf.tobytes();pdf.close()
                body={'title':library['alias']+' fixture manual','visibility':'MEMBERS'}
                if linked:body['library_book_id']=library['books'][0]['library_book_id']
                uploaded=client.post(f"/libraries/{library['library_id']}/assets",headers={**owner,'X-Luminar-Upload':str(uuid4())},
                    data=body,files={'file':('fixture.pdf',content,'application/pdf')})
                assert uploaded.status_code==202,uploaded.text
                result=uploaded.json();asset=result.get('asset',result)
                library['assets'].append({'asset_id':asset['asset_id'],'linked':linked})
    (SCOPE/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    # The ordinary frontend is reused under an isolated proxy configuration.
    vite=(ROOT/'frontend/vite.config.ts').read_text(encoding='utf8')
    vite=vite.replace("fileURLToPath(new URL('./src', import.meta.url))",json.dumps(str(ROOT/'frontend/src').replace('\\','/')))
    vite=re.sub(r'http://127\.0\.0\.1:800[2345]',f"http://127.0.0.1:{config['port']}",vite)
    vite=vite.replace('export default defineConfig({', 'export default defineConfig({\n  root: '+json.dumps(str(ROOT/'frontend').replace('\\','/'))+',')
    vite=vite.replace('port: 5173','port: 18017')
    vite=vite.replace('process.env.LUMINAR_CORE_API_TARGET ||','undefined ||')
    vite_path=ROOT/'frontend/.scratch/q4-vite.config.ts';vite_path.parent.mkdir(parents=True,exist_ok=True)
    vite_path.write_text(vite,encoding='utf8')
    public={**manifest,'scope':'Disposable isolated DB; real login/JWT/private-code membership path; no production data mutation.'}
    (ROOT/'reports/institution_v2q4_fixture_manifest.json').write_text(json.dumps(public,indent=2),encoding='utf8')
    print(json.dumps({'prepared':True,'database':config['database'],'libraries':len(manifest['libraries']),
        'serve_command':'.venv/Scripts/python.exe scripts/institution_v2q4_lab.py serve',
        'single_qwen_guard':'serve refuses while the regular RAG listener/process exists'}))

def instrumentation(app,manifest,real_model):
    from assistant.profiling import current
    from assistant.tools import ServiceTransport,AssistantAvailabilityTool
    orch=app.state.assistant
    aliases={book['library_book_id']:book['alias'] for lib in manifest['libraries'] for book in lib['books']}
    aliases.update({book['work_id']:book['alias'] for book in manifest['global_books']})
    lib_aliases={lib['library_id']:lib['alias'] for lib in manifest['libraries']}
    mode='REAL_QWEN' if real_model else 'NO_QWEN_REAL_MINILM' if app.state.q4_has_encoder else 'NO_MODEL_SETUP_SMOKE'
    original_parse=orch.qwen.parse;original_chat=orch.chat;original_generate=orch.qwen.generate
    original_call=ServiceTransport.call;original_availability=AssistantAvailabilityTool.availability
    def ids(values):return [aliases.get(str(v),'UNRECOGNIZED_ID') for v in values][:20]
    async def generate(prompt,*args,**kwargs):
        raw=await original_generate(prompt,*args,**kwargs)
        stage=kwargs.get('stage',args[1] if len(args)>1 else 'response')
        row=DIAGNOSTIC.get()
        if row is not None and stage in {'intent','repair','semantic_retry'}:
            try:
                wire=json.loads(raw)
                from assistant.qwen import INTENT_CODES,SCOPE_CODES,GOAL_CODES,CLARIFICATION_CODES
                enums={'i':set(INTENT_CODES.values()),'s':set(SCOPE_CODES.values()),
                    'g':set(GOAL_CODES.values()),'d':set(CLARIFICATION_CODES.values()),
                    'z':{'NONE','SHOW_MORE','REFINE_RESULTS'},
                    'e':{'ALL','FIRST','SECOND','THIRD','FOURTH','LAST','OTHER','FOCUS'}}
                row['model_wire_fields']={key:(value if value in enums[key] else 'INVALID_ENUM')
                    for key,value in wire.items() if key in enums and isinstance(value,str)}
                row['model_wire_fields'].update({key:value for key,value in wire.items()
                    if key in {'c','e','h'} and isinstance(value,(int,float,bool))})
            except (ValueError,TypeError,AttributeError):row['model_wire_json_valid']=False
        return raw
    async def parse(message,context):
        decision=await original_parse(message,context)
        row=DIAGNOSTIC.get()
        if row is not None:
            row['parsed']={key:getattr(value,'value',value) for key,value in decision.model_dump().items()
                if key in {'intent','reference','reference_scope','reference_position','ordinal_references','goal','context_operation','confidence','clarification_needed'}}
            row['model_context_counts']={'selected':len(context.get('selected_books',[])),
                'page':len(context.get('page_books',[])),
                'recent':len(context.get('active_result_context',{}).get('work_ids',[]))}
        return decision
    async def call(transport,service,method,path,**kwargs):
        started=time.perf_counter();row=DIAGNOSTIC.get()
        entry={'service':service,'method':method,'route':re.sub(r'[0-9a-f]{8}-[0-9a-f-]{27,}', '{uuid}',path)}
        if row is not None and len(row['tools'])<250:row['tools'].append(entry)
        try:
            result=await original_call(transport,service,method,path,**kwargs)
            entry['ok']=True
            if isinstance(result,dict):
                entry['search_source']=(result.get('source') or {}).get('search_source')
                if isinstance(result.get('results'),list):entry['result_count']=len(result['results'])
            return result
        except Exception as error:
            entry['ok']=False;entry['error_type']=type(error).__name__;entry['error_code']=getattr(error,'code',None);raise
        finally:entry['ms']=round((time.perf_counter()-started)*1000,3)
    def availability(tool,book):
        result=original_availability(tool,book);row=DIAGNOSTIC.get()
        if row is not None:row['availability'].append({'book':aliases.get(book.work_id,'UNRECOGNIZED_ID'),
            'available_copies':result.available_copies,'total_copies':result.total_copies})
        return result
    async def chat(request,owner,tools):
        assert owner.split(':')[0] in {str(u['id']) for u in manifest['users']}
        row={'run_variant':os.environ.get('Q4_VARIANT','baseline'),'captured_at':datetime.now(timezone.utc).isoformat(),'library':lib_aliases.get(str(request.library_id),'GLOBAL'),
            'execution_mode':mode,
            'conversation_hash':hashlib.sha256((request.conversation_id or '').encode()).hexdigest()[:16],
            'action':request.action,'selected':ids(request.selected_work_ids),'recent':ids(request.recent_work_ids),
            'page':ids(([request.page_context.work_id] if request.page_context.work_id else [])+request.page_context.work_ids),
            'tools':[],'availability':[],'request_hash':hashlib.sha256(request.message.encode()).hexdigest(),'validated_library':str(request.library_id) if request.library_id else None}
        token=DIAGNOSTIC.set(row);started=time.perf_counter()
        try:
            response=await original_chat(request,owner,tools)
            row['response']={'intent':response.intent.value,'books':ids([book.work_id for book in response.books]),
                'clarification_type':getattr(response.clarification.type,'value',None) if response.clarification else None,
                'error_codes':[error.code for error in response.errors]}
            return response
        finally:
            row['elapsed_ms']=round((time.perf_counter()-started)*1000,3)
            profile=current.get()
            if profile is not None:
                row['trace_id']=profile['trace_id'];row['qwen_calls']=list(profile['qwen_calls'])
                row['stages_ms']=dict(profile['stages_ms'])
            DIAGNOSTIC.reset(token)
            # Only the task-owned process can write; no HTTP diagnostic endpoint.
            destination=TRACE if real_model else TRACE.with_name('institution_v2q4_retrieval_traces.jsonl' if app.state.q4_has_encoder else 'institution_v2q4_smoke_traces.jsonl')
            existing=destination.stat().st_size if destination.exists() else 0
            if existing<8*1024*1024:
                with destination.open('a',encoding='utf8') as handle:handle.write(json.dumps(row,default=str)+'\n')
    orch.qwen.generate=generate;orch.qwen.parse=parse;orch.chat=chat
    ServiceTransport.call=call;AssistantAvailabilityTool.availability=availability

def make_app(engine,real_model=True):
    import httpx
    from backend.main import app
    from assistant.api import install_assistant
    from rag.services.library_asset_routes import install_library_assets
    from search.library_intelligence_api import install as install_search
    manifest=json.loads((SCOPE/'manifest.json').read_text(encoding='utf8'))
    app.state.q4_has_encoder=engine.reranker.retriever.model is not None
    startup_at=len(app.router.on_startup);shutdown_at=len(app.router.on_shutdown)
    rag_ask=lambda *args:None;rag_request=lambda **kwargs:None
    if app.state.q4_has_encoder:
        # Reuse the actual API ask function, without executing rag.api's
        # module-level model loader or opening its real personal registry.
        import ast,contextlib
        from fastapi import Depends,HTTPException
        from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
        from pydantic import BaseModel,model_validator
        from backend.dependencies import get_current_user
        from rag.services.private_documents import PrivateDocuments
        from rag.services.private_document_routes import install_private_documents
        from rag.services.book_access import authorize_selection
        from rag.book_assets import valid_work_id
        from rag.services.book_runtime import BookRuntime
        personal=PrivateDocuments(SCOPE/'personal',engine.reranker.retriever.model,
            engine.reranker.retriever,getattr(engine,'_document_latency',None))
        install_private_documents(app,personal,engine)
        namespace={'app':app,'BaseModel':BaseModel,'model_validator':model_validator,'Depends':Depends,
            'HTTPException':HTTPException,'HTTPAuthorizationCredentials':HTTPAuthorizationCredentials,
            'optional_auth':HTTPBearer(auto_error=False),'engine':engine,'private_documents':personal,
            'contextlib':contextlib,'valid_work_id':valid_work_id,'authorize_selection':authorize_selection,
            'get_current_user':get_current_user,'book_runtime':BookRuntime(engine.reranker.retriever)}
        tree=__import__('ast').parse((ROOT/'rag/api.py').read_text(encoding='utf8'))
        module=ast.Module(body=[node for node in tree.body if isinstance(node,(ast.ClassDef,ast.FunctionDef)) and node.name in {'RAGRequest','ask'}],type_ignores=[])
        exec(compile(module,'rag/api.py','exec'),namespace)
        rag_ask,rag_request=namespace['ask'],namespace['RAGRequest']
        public_queries={row['query']:row['id'] for name in ['institution_v2q1_public_rag_results.json','institution_v2q1_public_rag_resumed.json']
            for row in json.loads((ROOT/'reports'/name).read_text(encoding='utf8'))['queries'] if row['id'] in {'RAG001','RAG013','RAG019','RAG027'}}
        original_ask=engine.ask
        def observed_ask(*args,**kwargs):
            result=original_ask(*args,**kwargs)
            if real_model and kwargs.get('question') in public_queries and not kwargs.get('document_id') and not kwargs.get('work_id'):
                record={'case':public_queries[kwargs['question']],'raw_answer':result.get('answer'),
                    'raw_verdict':result.get('verdict'),'source_pages':[source.get('page') for source in result.get('sources',[])],
                    'profile':result.get('profile')}
                with (ROOT/'reports/institution_v2q4_public_grounding_traces.jsonl').open('a',encoding='utf8') as handle:handle.write(json.dumps(record)+'\n')
            return result
        engine.ask=observed_ask
    install_assistant(app,engine,rag_ask,rag_request)
    install_library_assets(app,engine)
    install_search(app,SimpleNamespace(embedding_model=engine.reranker.retriever.model,reranker=engine.reranker.model))
    # Loopback-equivalent ASGI transport invokes the real authenticated handlers.
    # No get_current_user/dependency overrides and no additional model process.
    previous=app.state.assistant_http_client
    original_transport=previous._transport
    previous._transport=httpx.ASGITransport(app=app)
    @app.get('/recommendations')
    def fixture_candidates():
        # Controlled diagnostic provider revision 2: owned Global fixture rows;
        # private libraries still intersect canonical tenant holdings.
        return {'recommendations':[{**row,'authors':['Disposable Author']} for row in manifest['global_books']]}
    @app.post('/search')
    def controlled_global_search():
        return {'results':[{'work_id':row['work_id']} for row in manifest['global_books']]}
    old_lifespan=app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(instance):
        async with old_lifespan(instance):
            await original_transport.aclose()
            for handler in app.router.on_startup[startup_at:]:
                result=handler()
                if inspect.isawaitable(result):await result
            yield
            for handler in app.router.on_shutdown[shutdown_at:]:
                result=handler()
                if inspect.isawaitable(result):await result
            await previous.aclose()
    app.router.lifespan_context=lifespan
    if real_model:
        from scripts.institution_v2q4_trace import install
        install(engine,app,ROOT,manifest)
    instrumentation(app,manifest,real_model)
    return app

def check():
    config=configure()
    os.environ['LIBRARY_ASSET_WORKER_ENABLED']='0'
    from threading import RLock
    from fastapi.testclient import TestClient
    engine=SimpleNamespace(llm=SimpleNamespace(),inference_lock=RLock(),
        reranker=SimpleNamespace(retriever=SimpleNamespace(model=None),model=None))
    manifest=json.loads((SCOPE/'manifest.json').read_text())
    with TestClient(make_app(engine,False)) as client:
        response=client.post('/auth/login',json={'email':'member@q4.example.com','password':config['password']})
        assert response.status_code==200,response.text
        token=response.json()['access_token']
        library=manifest['libraries'][0]
        result=client.post('/assistant/chat',headers={'Authorization':'Bearer '+token},json={
            'message':'Recommend','action':'RECOMMEND','library_id':library['library_id']})
        assert result.status_code==200,result.text
        body=result.json();assert not body['errors'] and len(body['books'])==10,body
        assert {book['library_id'] for book in body['books']}=={library['library_id']}
        denied=client.post('/assistant/chat',json={'message':'Recommend','action':'RECOMMEND','library_id':library['library_id']})
        assert denied.status_code in (401,403),denied.text
    print(json.dumps({'authenticated_core_smoke':'PASS','anonymous_denial':denied.status_code,
        'returned':10,'real_qwen_executed':False,'dependency_overrides_used':False}))

def serve():
    config=configure()
    os.environ['LIBRARY_ASSET_WORKER_ENABLED']='1'
    import psutil
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1',8005))!=0,'Ordinary RAG is running; no second Qwen process allowed'
    for process in psutil.process_iter(['pid','cmdline','name']):
        arguments=process.info['cmdline'] or []
        is_rag=(process.info['name'] or '').lower() in {'python.exe','pythonw.exe','uvicorn.exe'} and any(arg in {'rag.api','rag.api:app'} for arg in arguments)
        assert process.pid==os.getpid() or not is_rag, 'A RAG process is starting/running; no second Qwen process allowed'
    # Redirect only the old uploaded-document corpus; global public book data
    # remains read-only. Real personal/private registries are never opened.
    import rag.retriever as retriever
    retriever.DOC_INDEX_DIR=SCOPE/'legacy-document-index'
    retriever.DOC_INDEX_PATH=retriever.DOC_INDEX_DIR/'rag.index'
    retriever.DOC_METADATA_PATH=retriever.DOC_INDEX_DIR/'rag_metadata.json'
    retriever.DOC_CHUNKS_DIR=SCOPE/'legacy-document-chunks'
    from rag.qa import LuminaRAG
    engine=LuminaRAG()
    from rag.document_latency import install_document_latency
    install_document_latency(engine)
    logging.getLogger('luminar.assistant').setLevel(logging.WARNING)
    import uvicorn,faulthandler
    if os.environ.get('Q4_STACK_TRACE')=='1':
        trace_file=(ROOT/'reports/institution_v2q4_thread_stacks.log').open('a',encoding='utf8')
        faulthandler.dump_traceback_later(30,repeat=True,file=trace_file)
    app=make_app(engine)
    (ROOT/'reports/institution_v2q4_final_runtime.json').write_text(json.dumps({'variant':os.environ.get('Q4_VARIANT'),'pid':os.getpid(),'qwen_model':'Qwen2.5-3B-Instruct NF4 CUDA0; unchanged','validator_proposal_active':os.environ.get('Q4_VALIDATOR_PROPOSAL')=='1','source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['assistant/qwen.py','assistant/orchestrator.py','assistant/digital_availability.py','assistant/schemas.py','backend/services/book_digital_availability.py','rag/qa.py','rag/llm.py','rag/citation_boundary.py']},'owned_database':config['database']},indent=2),encoding='utf8')
    uvicorn.run(app,host='127.0.0.1',port=config['port'],log_level='warning')

def serve_retrieval():
    """Real cached CPU MiniLM/FAISS, controlled generator; no Qwen is loaded."""
    config=configure();os.environ['LIBRARY_ASSET_WORKER_ENABLED']='1'
    from threading import RLock
    import numpy as np
    import rag.retriever as retriever
    retriever.DEVICE='cpu'
    retriever.DOC_INDEX_DIR=SCOPE/'legacy-document-index';retriever.DOC_INDEX_PATH=retriever.DOC_INDEX_DIR/'rag.index'
    retriever.DOC_METADATA_PATH=retriever.DOC_INDEX_DIR/'rag_metadata.json';retriever.DOC_CHUNKS_DIR=SCOPE/'legacy-document-chunks'
    import rag.reranker as reranker
    reranker.DEVICE='cpu'
    ranking=reranker.RAGReranker()
    def controlled_ask(question,document_id=None,**kwargs):
        source=ranking.retriever
        if not document_id or source.doc_index is None:
            from fastapi import HTTPException
            raise HTTPException(503,'Controlled generator requires an authorized fixture document.')
        vector=np.asarray(source.model.encode([question],normalize_embeddings=True,convert_to_numpy=True),dtype=np.float32)
        _,labels=source.doc_index.search(vector,min(3,len(source.doc_metadata)))
        selected=[source.doc_metadata[int(label)] for label in labels[0] if int(label)>=0]
        assert selected and all(row['document_id']==document_id for row in selected)
        record={'captured_at':datetime.now(timezone.utc).isoformat(),'execution_mode':'CONTROLLED_GENERATOR_REAL_MINILM_FAISS',
            'document_scope_hash':hashlib.sha256(document_id.encode()).hexdigest(),
            'source_scope_count':len({row['document_id'] for row in selected}),'chunks':len(selected),
            'selected_text_sha256':[hashlib.sha256(source.doc_chunk_texts[row['chunk_id']].encode()).hexdigest() for row in selected]}
        with (ROOT/'reports/institution_v2q4_generator_gate.jsonl').open('a',encoding='utf8') as handle:handle.write(json.dumps(record)+'\n')
        return {'question':question,'answer':'The controlled generator received authorized synthetic fixture passages.',
            'verdict':'SUPPORTED','sources':[{**row,'work_id':document_id} for row in selected]}
    engine=SimpleNamespace(llm=SimpleNamespace(),inference_lock=RLock(),reranker=ranking,ask=controlled_ask)
    logging.getLogger('luminar.assistant').setLevel(logging.WARNING)
    import uvicorn
    uvicorn.run(make_app(engine,False),host='127.0.0.1',port=config['port'],log_level='warning')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','serve','serve-retrieval','check']);args=parser.parse_args()
    {'prepare':prepare,'serve':serve,'serve-retrieval':serve_retrieval,'check':check}[args.mode]()
