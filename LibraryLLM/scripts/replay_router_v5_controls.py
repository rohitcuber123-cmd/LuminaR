"""Replay the same cached DEV decisions through unchanged executor, no Qwen."""
import asyncio
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from assistant import schemas,tools as tool_module
from assistant.orchestrator import AssistantOrchestrator
from assistant.state import ConversationStore,ResultContext
from router_v5_data import BOOKS
import evaluate_assistant_semantics as fixtures
from assistant.router_v5.contracts import BY_ID
from router_v5_evidence import write

class Cached:
    def __init__(self,decision):self.decision=schemas.AssistantIntentDecision.model_validate(decision)
    async def parse(self,*args):return self.decision.model_copy(deep=True)
    async def respond(self,message,response):return response.message or 'Verified fixture result.'

async def replay(row,decision):
    gateway=Cached(decision);orch=AssistantOrchestrator(gateway,ConversationStore());state=orch.store.get(None,'control-replay')
    ctx=row['context'];selected=[b['work_id'] for b in ctx.get('selected_books',[])]
    state.selected_work_ids=[] if ctx.get('selection_changed') else list(selected)
    state.last_comparison_work_ids=[b['work_id'] for b in ctx.get('previous_comparison',[])]
    state.last_referenced_work_ids=ctx.get('last_referenced_work_ids',[])
    state.last_intent=schemas.Intent(ctx['last_intent']) if ctx.get('last_intent') else None
    state.awaiting_criteria=ctx.get('awaiting_criteria',False)
    if 'active_result_context' in ctx:
        active=ctx['active_result_context'];state.active_result_work_ids=active.get('work_ids',[]);state.last_result_type=active.get('type')
        state.recent_result_work_ids=list(state.active_result_work_ids)
        if active.get('type') in {'search','recommendations'}:
            state.result_context=ResultContext(intent=schemas.Intent.SEARCH_BOOKS,query='original fixture query',has_more=True,
                candidate_work_ids=[b['work_id'] for b in BOOKS],delivered_work_ids=state.active_result_work_ids,next_offset=2,exhausted=False)
    reco=ctx.get('previous_recommendations',{})
    state.last_recommendation_work_ids=reco.get('work_ids',[]);state.last_recommendation_seed_work_ids=reco.get('seed_work_ids',[])
    request=schemas.AssistantRequest(message=row['message'],conversation_id=state.conversation_id,selected_work_ids=selected,
             page_context={'work_id':ctx['page_books'][0]['work_id']} if ctx.get('page_books') else {'document_id':ctx['document_id']} if ctx.get('document_id') else {})
    tools=fixtures.FixtureTools(schemas,tool_module)
    for i,b in enumerate(BOOKS):tools.records[b['work_id']]=schemas.Book(**b,authors='Public Fixture Author',subjects='Ecology | History',description='Public illustrative catalogue summary.',average_rating=4.5-i*.1,rating_count=30+i,available_copies=1,total_copies=1)
    writes=[]
    async def reading_add(wid):writes.append(('ADD',wid));return {}
    async def reading_remove(wid):writes.append(('REMOVE',wid));return {}
    async def synthetic_loans(history=False):return {'count':4,'issues':[{'issue_id':i+1,'work_id':b['work_id']} for i,b in enumerate(BOOKS)]}
    tools.reading_list.add=reading_add;tools.reading_list.remove=reading_remove
    tools.loans.loans=synthetic_loans
    response=await orch.chat(request,'control-replay',tools);c=BY_ID[row['contract_id']]
    ids=(response.seed_work_ids if response.intent.value in {'MORE_LIKE_THIS','RECOMMEND_FROM_SELECTION','RECOMMEND_FROM_BOOK'} else
         [b.work_id for b in response.comparison.books] if response.comparison else
         [a.work_id for a in response.availability] if response.availability else
         [b.work_id for b in response.books] if response.intent.value=='BOOK_DETAILS' else
         [response.pending_action.work_id] if response.pending_action else state.last_referenced_work_ids)
    checks={'intent':response.intent.value==c.intent,'errors':not response.errors}
    if row['expected_ids']:checks['binding']=ids==row['expected_ids']
    if c.id in {'BORROW','RETURN','RESERVE'}:checks['confirmation']=bool(response.pending_action)
    if c.id.startswith('COMPARE_'):
        checks['goal']=gateway.decision.goal.value==c.goal
        if row['field']:checks['field']=bool(response.comparison and row['field'] in response.comparison.requested_fields)
        if c.id=='COMPARE_PREFERENCE':
            checks['criterion']=bool(gateway.decision.criterion)==row['criterion_present']
            checks['clarification']=bool(response.clarification and response.clarification.type=='CRITERIA_AMBIGUITY')==(not row['criterion_present'])
    if c.id=='MISSING_REFERENCE':checks['clarification']=bool(response.clarification)
    return {'pass':all(checks.values()),'checks':checks,'actual_intent':response.intent.value,'resolved_ids':ids,
            'title_calls':tools.title_calls,'search_calls':tools.search_calls,'fixture_reading_list_writes':writes}

async def main():
    os.environ['ASSISTANT_ROUTER_MODE']='existing_qwen'
    report=json.loads((ROOT/'reports/assistant_router_v5_qwen_fallback.json').read_text(encoding='utf8'))
    dev={r['id']:r for r in json.loads((ROOT/'evaluation/assistant_router_v5/dev.json').read_text(encoding='utf8'))}
    hybrid={r['id']:r for r in json.loads((ROOT/'reports/assistant_router_v5_dev_hybrid.json').read_text(encoding='utf8'))['cases']}
    results=[]
    for case in report['control_cases']:
        r=dev[case['id']]
        results.append({'id':case['id'],'full_qwen':await replay(r,case['full_qwen_decision']),
                        'shortlisted_qwen':await replay(r,hybrid[case['id']]['decision'])})
    report['paired_product_replay']={'method':'Same cached one-call decisions replayed through unchanged executor/API fixtures; no new model calls, no threshold changes. Fixtures provide active loans and in-memory reading-list operations. Comparison goals/fields/criterion remain strict; harmless missing account/detail goal tags are not penalized. Circulation proposals require confirmation; legacy reading-list add/remove execute immediately.',
        'cases':results,'total':len(results),'full_qwen_correct':sum(r['full_qwen']['pass'] for r in results),
        'shortlist_correct':sum(r['shortlisted_qwen']['pass'] for r in results)}
    report['parse_control_warning']='The original strict parse score also penalizes goal tags and unbound IDs that existing_qwen leaves to the executor; do not use that score to claim a product improvement.'
    write('qwen_fallback',report)
    print('FAIR PAIRED REPLAY',report['paired_product_replay']['full_qwen_correct'],report['paired_product_replay']['shortlist_correct'],len(results))

if __name__=='__main__':asyncio.run(main())
