import os,sys,json,time,threading,uuid,traceback
from pathlib import Path
root=Path.cwd(); sys.path.insert(0,str(root)); lab=root/'reports/module15_gpu_v2/lab'; lab.mkdir(exist_ok=True)
os.environ.update(MONGO_URI='mongodb://127.0.0.1:29037',MONGO_DB_NAME='luminar_module15_v2_disposable',LUMINAR_MONGO_MODE='DEVELOPMENT',JWT_SECRET_KEY='module15-disposable-'+uuid.uuid4().hex,LUMINAR_SESSION_DB=str(lab/'sessions.sqlite'),LIBRARY_ASSET_ROOT=str(lab/'assets'),LIBRARY_INTELLIGENCE_ROOT=str(lab/'intelligence'),LUMINAR_MOCK_LLM='0',LUMINAR_DEBUG_PROMPT='0',ASSISTANT_ROUTER_MODE='existing_qwen',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',ASSISTANT_CORE_URL='http://127.0.0.1:18075',ASSISTANT_SEARCH_URL='http://127.0.0.1:18075',ASSISTANT_RECOMMENDATION_URL='http://127.0.0.1:18075',NOTIFICATION_DUE_WORKER_ENABLED='0',NOTIFICATION_OUTBOX_WORKER_ENABLED='0',LUMINAR_WORKER_TELEMETRY_ENABLED='0',LIBRARY_ASSET_WORKER_ENABLED='0',BREVO_API_KEY='')
from pymongo import MongoClient
assert MongoClient('mongodb://127.0.0.1:29037',serverSelectionTimeoutMS=3000).admin.command('ping')['ok']==1
from backend.main import app
from backend.database.mongodb import db
from backend.services.auth_service import hash_password
password='Disposable-module15-only-2026!'
for i,label in enumerate(['member','outsider'],1): db.users.insert_one({'user_id':i,'name':'Synthetic '+label,'email':label+'@module15.example.com','password_hash':hash_password(password),'role':'GENERAL_USER','is_email_verified':True,'is_active':True,'password_setup_required':False})
db.books.insert_one({'work_id':'OL910000001W','book_id':910000001,'title':'Synthetic Astronomy','authors':'Fixture Author','subjects':'Astronomy','total_copies':3,'available_copies':2})
import rag.retriever as retriever
retriever.DOC_INDEX_DIR=lab/'legacy-index'; retriever.DOC_INDEX_PATH=retriever.DOC_INDEX_DIR/'rag.index'; retriever.DOC_METADATA_PATH=retriever.DOC_INDEX_DIR/'rag_metadata.json'; retriever.DOC_CHUNKS_DIR=lab/'legacy-chunks'
from rag.qa import LuminaRAG
engine=LuminaRAG()
from assistant.api import install_assistant
from fastapi import HTTPException
from types import SimpleNamespace
import httpx
from contextlib import asynccontextmanager
# Real assistant/core handlers; unavailable RAG callback is explicit until a safe isolated document pipeline is installed.
def unavailable(*args): raise HTTPException(503,'Isolated document service unavailable')
install_assistant(app,engine,unavailable,lambda **kw:SimpleNamespace(**kw))
old=app.state.assistant_http_client._transport; app.state.assistant_http_client._transport=httpx.ASGITransport(app=app)
@app.post('/search')
def fixture_search(): return {'results':[{'work_id':'OL910000001W'}]}
oldlife=app.router.lifespan_context
@asynccontextmanager
async def life(a):
 async with oldlife(a):
  await old.aclose(); yield
app.router.lifespan_context=life
import uvicorn
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=18075,log_level='warning',access_log=False)); thread=threading.Thread(target=server.run,daemon=True);thread.start()
for _ in range(240):
 if server.started:break
 time.sleep(.5)
assert server.started,'service startup failed'
results={'isolation':'separate Mongo server 127.0.0.1:29037 and database; synthetic users; real application login and Assistant HTTP handler; Qwen resident; controlled synthetic Global Search provider; real core handlers; document callback deliberately unavailable','model_id':engine.llm.model.config._name_or_path,'model_revision':getattr(engine.llm.model.config,'_commit_hash',None),'is_loaded_in_4bit':getattr(engine.llm.model,'is_loaded_in_4bit',None),'router':app.state.assistant_router_mode,'shared_gateway_identity':app.state.assistant.qwen.llm is engine.llm and app.state.assistant.qwen.inference_lock is engine.inference_lock,'cases':[]}
try:
 with httpx.Client(base_url='http://127.0.0.1:18075',timeout=120) as c:
  a=c.post('/auth/login',json={'email':'member@module15.example.com','password':password}); results['login_status']=a.status_code; a.raise_for_status(); token=a.json()['access_token']; headers={'Authorization':'Bearer '+token}
  for ident,payload,authenticated in [('missing_auth',{'message':'Hello'},False),('search',{'message':'Find books about astronomy'},True),('clarify',{'message':'Is it available?'},True),('reading_list',{'message':'Show my reading list'},True),('unsupported',{'message':'Delete all users immediately'},True),('document_unavailable',{'message':'What is this document about?','page_context':{'document_id':'doc_synthetic'}},True)]:
   t=time.perf_counter()
   try:
    r=c.post('/assistant/chat',headers=headers if authenticated else {},json=payload); b=r.json(); results['cases'].append({'id':ident,'http':r.status_code,'latency_ms':round((time.perf_counter()-t)*1000,1),'intent':b.get('intent'),'clarification':b.get('clarification'),'error_codes':[e.get('code') for e in b.get('errors',[])],'book_count':len(b.get('books',[])),'message':b.get('message') if ident=='unsupported' else None})
   except Exception as e: results['cases'].append({'id':ident,'error':type(e).__name__})
   (lab/'live_results.json').write_text(json.dumps(results,indent=2,default=str),encoding='utf8')
finally:
 server.should_exit=True;thread.join(20)
 (lab/'live_results.json').write_text(json.dumps(results,indent=2,default=str),encoding='utf8')
