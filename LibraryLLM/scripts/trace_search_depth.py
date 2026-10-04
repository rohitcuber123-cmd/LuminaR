"""Read-only candidate-count and zero-Qwen continuation trace using disposable account."""
import asyncio,json,contextlib,io,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import httpx
from recommendation import recommendation_service as service
from assistant.orchestrator import AssistantOrchestrator
from assistant.state import ConversationStore
from assistant.tools import AssistantTools
from assistant.schemas import AssistantRequest
creds=json.loads((ROOT/'.search_depth_validation.json').read_text(encoding='utf-8'));auth='Bearer '+creds['token'];report=json.loads((ROOT/'reports/recommendation_pagination.json').read_text(encoding='utf-8'))
seeds=[x['work_id'] for x in json.loads((ROOT/'reports/search_manage_money_ranking.json').read_text(encoding='utf-8'))['results'][:2]]
trace=[];original_post=service.requests.post;mode=''
def traced_post(url,**kw):
 response=original_post(url,**kw)
 if url==service.SEARCH_API_URL:
  trace.append({'mode':mode,'requested':kw['json']['top_k'],'received':len(response.json().get('results',[])),'query':kw['json']['query'],'status':response.status_code})
 return response
service.requests.post=traced_post
try:
 with contextlib.redirect_stdout(io.StringIO()):
  for label,seed in [('personalized',None),('single_seed',seeds[0]),('multi_seed_first',seeds[0]),('multi_seed_second',seeds[1])]:
   mode=label;rows=service.get_recommendations(creds['user_id'],auth,limit=50,seed_work_id=seed,strict_service_errors=True);trace[-1]['post_scoring_count']=len(rows)
finally:service.requests.post=original_post
assert all(x['requested']==50 and x['received']==50 for x in trace)
class NoQwen:
 def __init__(self):self.calls=0
 async def interpret(self,*args,**kwargs):self.calls+=1;raise AssertionError('Unexpected Qwen')
 async def respond(self,*args,**kwargs):self.calls+=1;raise AssertionError('Unexpected Qwen')
 async def generate(self,*args,**kwargs):self.calls+=1;raise AssertionError('Unexpected Qwen')
async def rag(*args,**kwargs):raise AssertionError('Unexpected RAG')
async def live():
 qwen=NoQwen();orch=AssistantOrchestrator(qwen,ConversationStore());results=[];calls=[]
 async def record(response):
  await response.aread()
  if response.request.url.port==8004:
   data=response.json();calls.append({'path':response.request.url.path,'requested':50,'returned':len(data.get('recommendations',[]))})
 async with httpx.AsyncClient(timeout=90,event_hooks={'response':[record]}) as client:
  tools=AssistantTools(client,auth,rag)
  for action,selected in [('RECOMMEND',[]),('RECOMMEND_SIMILAR',seeds[:1]),('RECOMMEND_FROM_SELECTION',seeds)]:
   calls_before=len(calls)
   first=await orch.chat(AssistantRequest(message='Recommend books',action=action,selected_work_ids=selected),str(creds['user_id']),tools)
   second=await orch.chat(AssistantRequest(message='Show more',action='SHOW_MORE',conversation_id=first.conversation_id,selected_work_ids=['OL19545719W']),str(creds['user_id']),tools)
   assert len(first.books)==len(second.books)==10,(action,first.errors,second.errors,first.clarification)
   assert first.seed_work_ids==second.seed_work_ids==selected
   assert first.recommendation_mode==second.recommendation_mode
   assert not {x.work_id for x in first.books}&{x.work_id for x in second.books}
   assert len(calls)-calls_before==(len(selected) or 1)
   results.append({'action':action,'mode':str(first.recommendation_mode),'seed_work_ids':selected,'page1':[x.work_id for x in first.books],'page2':[x.work_id for x in second.books],'offset':second.result_offset,'has_more':second.has_more,'overlap':0,'recommendation_calls':len(calls)-calls_before,'qwen_calls':qwen.calls})
 assert qwen.calls==0
 return {'cases':results,'calls':calls,'qwen_calls':qwen.calls}
report['actual_candidate_trace']=trace;report['actual_assistant_continuation']=asyncio.run(live())
(ROOT/'reports/recommendation_pagination.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Actual Search candidate traces:',[(x['mode'],x['requested'],x['received'],x['post_scoring_count']) for x in trace]);print('Actual assistant continuation: three modes, retained seeds, disjoint pages, no extra recommendation calls, zero Qwen calls.')
