"""Process-local, read-only stage tracing for owned synthetic private fixtures."""
from contextvars import ContextVar
from pathlib import Path
from time import perf_counter
import hashlib,json,os
ACTIVE=ContextVar('q3_private_trace',default=None)
PHASE=ContextVar('q3_model_phase',default='answer')
def digest(value):return hashlib.sha256(str(value).encode()).hexdigest()
def facts(value):
 text=str(value).upper();return {'A_fact':'ALPHA-SEVEN' in text,'B_fact':'BRAVO-NINE' in text}
def install(engine,app,root,manifest):
 import rag.qa as qa
 import rag.citation_boundary as citation
 destination=root/'reports/institution_v2q4_private_stages.jsonl'
 aliases={x['library_id']:x['alias'] for x in manifest['libraries']}
 def observe(obj,name,label,summarize):
  original=getattr(obj,name)
  def traced(*args,**kwargs):
   start=perf_counter()
   try:
    result=original(*args,**kwargs)
    row=ACTIVE.get()
    if row is not None:row['stages'].append({'stage':label,'elapsed_ms':round((perf_counter()-start)*1000,3),**summarize(result,args,kwargs)})
    return result
   except Exception as e:
    row=ACTIVE.get()
    if row is not None:row['stages'].append({'stage':label,'elapsed_ms':round((perf_counter()-start)*1000,3),'error_type':type(e).__name__})
    raise
  setattr(obj,name,traced)
 def search(result,args,kwargs):return {'count':len(result.get('results',[])),**facts([x.get('text','') for x in result.get('results',[])]),'timing_ms':result.get('timing_ms')}
 observe(engine.reranker.retriever,'search','embedding_faiss_candidates',search)
 observe(engine.reranker,'search','reranking_and_evidence_scores',search)
 observe(qa,'select_definition_evidence','document_evidence_selection',lambda r,a,k:{'before_count':len(a[1]),'after_count':len(r),'before_facts':facts(a[1]),'after_facts':facts(r)})
 observe(engine,'build_context','chunk_context_selection',lambda r,a,k:{'synthetic_context':r[0],'synthetic_selected_chunks':r[1],'context_chars':len(r[0]),'chunks':len(r[1]),**facts(r[0])})
 observe(engine,'build_prompt','prompt_construction',lambda r,a,k:{'chars':len(r),'sha256':digest(r),**facts(r)})
 observe(qa,'run_fast_filter','fast_grounding_gate',lambda r,a,k:{'decision':r.get('decision'),'reason_hashes':[digest(x) for x in r.get('reasons',[])]})
 for method,label in [('analyze_intent','intent'),('validate_evidence','grounding')]:
  original=getattr(engine.llm,method)
  def wrap(original,label):
   def call(*args,**kwargs):
    token=PHASE.set(label);start=perf_counter()
    try:
     r=original(*args,**kwargs);row=ACTIVE.get()
     if row is not None:row['stages'].append({'stage':label,'elapsed_ms':round((perf_counter()-start)*1000,3),'verdict':r.get('verdict') if isinstance(r,dict) else None,'validator_details':r.get('details') if isinstance(r,dict) and label=='grounding' else None,'synthetic_question':args[0] if args else None,'synthetic_intent':args[1] if len(args)>1 else None,'input_fact_presence':facts(args),'query_type':r.get('query_type') if isinstance(r,dict) else None})
     return r
    finally:PHASE.reset(token)
   return call
  setattr(engine.llm,method,wrap(original,label))
 original_generate=engine.llm.generate
 def generate(prompt,*args,**kwargs):
  start=perf_counter();r=original_generate(prompt,*args,**kwargs);row=ACTIVE.get()
  if row is not None:row['stages'].append({'stage':'qwen_'+PHASE.get(),'elapsed_ms':round((perf_counter()-start)*1000,3),'prompt_chars':len(prompt),'prompt_fact_presence':facts(prompt),'output_fact_presence':facts(r),'output_sha256':digest(r)})
  return r
 engine.llm.generate=generate
 service=app.state.library_assets
 observe(service.repository,'authorize_asset','membership_document_authorization',lambda r,a,k:{'allowed':True,'ready_required':k.get('ready',False)})
 observe(service,'prepared','artifact_identity_extraction_chunks',lambda r,a,k:{'chunks':len(r[3]),'pages':[x.get('page') for x in r[3]],'generation_hash':digest(r[0].get('active_generation_id')),'chunk_hashes':[digest(x['text']) for x in r[3]],**facts(r[3])})
 observe(citation,'validate_page_claims','citation_validation',lambda r,a,k:{'input_verdict':a[0].get('verdict'),'output_verdict':r.get('verdict'),'source_count':len(r.get('sources',[]))})
 original=service.ask
 def ask(library_id,asset_id,actor,query,depth='normal'):
  row={'variant':os.environ.get('Q4_VARIANT','baseline'),'validator_proposal_only_in_owned_process':False,'library':aliases.get(library_id,'UNKNOWN'),'asset_hash':digest(asset_id),'query_hash':digest(query),'stages':[]};token=ACTIVE.set(row);start=perf_counter()
  try:
   result=original(library_id,asset_id,actor,query,depth)
   row['final']={'synthetic_answer':result.get('answer'),'synthetic_sources':result.get('sources'),'verdict':result.get('verdict'),'sources':len(result.get('sources',[])),'answer_facts':facts(result.get('answer','')),'answer_sha256':digest(result.get('answer','')),'profile':result.get('profile'),'timing_ms':result.get('timing_ms'),'fast_filter_decision':result.get('fast_filter_decision')}
   return result
  finally:
   row['total_ms']=round((perf_counter()-start)*1000,3);ACTIVE.reset(token)
   with destination.open('a',encoding='utf8') as f:f.write(json.dumps(row,default=str)+'\n')
 service.ask=ask
