"""Controlled real-Qwen V2 experiments using the existing RAG engine once.

Never invoke the old runner (its report destinations are frozen). All model
calls use its existing QwenGateway and the production decoding settings.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'scripts'))
import evaluate_assistant_semantics as fixtures
from assistant import schemas, tools as tool_module
from assistant.qwen import (QwenGateway, AssistantDecodingSchema, INTENT_KEYS,
    FILTER_KEYS, INTENT_CODES, SCOPE_CODES, GOAL_CODES, CLARIFICATION_CODES)
from assistant.orchestrator import AssistantOrchestrator
from assistant.state import ConversationStore
from assistant import router_v2
from assistant.router_v2_legacy import DescriptiveSchema, legacy_prompt, legacy_problem
from assistant.profiling import current


def write(name, data):
    path=ROOT/'reports'/name
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,indent=2,default=str),encoding='utf8')
    os.replace(temp,path)






class VariantGateway:
    def __init__(self,gateway,variant,retry=False):
        self.gateway,self.variant,self.retry=gateway,variant,retry
        self.decision=None;self.raw=[];self.telemetry={};self.prompt_hash=None;self.schema_hash=None
    async def parse(self,message,context):
        self.raw=[]
        if self.variant in {'D','E','E2'}:
            outer=self
            class Observe:
                async def generate(self,prompt,schema,stage):
                    outer.prompt_hash=hashlib.sha256(prompt.encode()).hexdigest()
                    outer.schema_hash=hashlib.sha256(json.dumps(schema.model_json_schema(),sort_keys=True).encode()).hexdigest()
                    value=await outer.gateway.generate(prompt,schema,stage)
                    outer.raw.append(value)
                    return value
            self.decision,self.telemetry=await router_v2.decide(Observe(),message,context,self.variant,self.retry)
        elif self.variant=='A':
            outer=self
            class Observe:
                async def generate(self,prompt,schema,stage):
                    outer.prompt_hash=hashlib.sha256(prompt.encode()).hexdigest()
                    outer.schema_hash=hashlib.sha256(json.dumps(schema.model_json_schema(),sort_keys=True).encode()).hexdigest()
                    value=await outer.gateway.generate(prompt,schema,stage);outer.raw.append(value);return value
            self.decision=await QwenGateway.parse(Observe(),message,context)
            self.telemetry={'router_variant':'A','first_pass_valid':True,'retry_used':False}
            from assistant.qwen import validated_intent
            try:validated_intent(self.raw[-1])
            except (ValueError,TypeError):self.telemetry.update(first_pass_valid=False,invalid_kind='SCHEMA_INVALID')
        else:
            schema=DescriptiveSchema(context,self.variant=='C')
            prompt=await legacy_prompt(message,context)
            if self.variant=='C':prompt='Allowed intents: '+', '.join(router_v2.make_plan(context).intents)+'\n'+prompt
            self.prompt_hash=hashlib.sha256(prompt.encode()).hexdigest()
            self.schema_hash=hashlib.sha256(json.dumps(schema.model_json_schema(),sort_keys=True).encode()).hexdigest()
            raw=await self.gateway.generate(prompt,schema,'intent');self.raw.append(raw)
            self.telemetry={'router_variant':self.variant,'first_pass_valid':True,'retry_used':False}
            try:
                data=json.loads(raw)
                if data.get('clarification_type'):data['clarification_needed']=True
                self.decision=schemas.AssistantIntentDecision.model_validate(data)
            except (ValueError,TypeError):
                self.telemetry.update(first_pass_valid=False,invalid_kind='SCHEMA_INVALID')
                self.decision=schemas.AssistantIntentDecision(intent=schemas.Intent.CLARIFICATION,
                    reference_scope=schemas.ReferenceScope.AMBIGUOUS,clarification_needed=True,
                    clarification_type=schemas.ClarificationType.REFERENCE_AMBIGUITY)
        if self.retry and self.variant in {'A','B','C'}:
            problem=legacy_problem(self.decision,context,message,self.telemetry)
            if problem:
                self.telemetry.update(first_pass_valid=False,retry_used=True,invalid_kind=problem[0])
                started=perf_counter()
                schema=DescriptiveSchema(context,self.variant=='C')
                focused=('Context: Correct one inconsistent library routing decision. JSON only. '
                    'Problem: '+problem[1]+'. intent is a public enum; confidence is 0..1. '
                    'reference_scope is SELECTED_BOOKS,PREVIOUS_COMPARISON,CURRENT_PAGE_BOOK,RECENT_RESULTS,ACCOUNT,EXPLICIT_BOOK,NONE,AMBIGUOUS. '
                    'reference_position is ALL,FIRST,SECOND,LAST,OTHER,FOCUS. '
                    'COMPARE_BOOKS goal: FACTUAL_COMPARE describes differences; COMPARE_BY_FIELD compares comparison_fields; '
                    'PREFERENCE_COMPARE chooses suitability and copies stated purpose into criterion. '
                    'No reading criterion: clarification_type=CRITERIA_AMBIGUITY; missing book: REFERENCE_AMBIGUITY. '
                    'Never invent titles or IDs. Explicit mentioned_titles must occur in the request. '
                    'Allowed intents: '+','.join(router_v2.make_plan(context).intents)+
                    '\nCONTEXT: '+json.dumps(context,separators=(',',':'))+'\nREQUEST: '+json.dumps(message))
                raw=await self.gateway.generate(focused,schema,'semantic_retry');self.raw.append(raw)
                try:
                    data=json.loads(raw)
                    if data.get('clarification_type'):data['clarification_needed']=True
                    retried=schemas.AssistantIntentDecision.model_validate(data)
                    if legacy_problem(retried,context,message,{'first_pass_valid':True}):raise ValueError('Retry inconsistent')
                    self.decision=retried
                except (ValueError,TypeError):
                    self.decision=schemas.AssistantIntentDecision(intent=schemas.Intent.CLARIFICATION,
                        reference_scope=schemas.ReferenceScope.AMBIGUOUS,clarification_needed=True,
                        clarification_type=schemas.ClarificationType.REFERENCE_AMBIGUITY)
                self.telemetry['retry_ms']=(perf_counter()-started)*1000
        profile=current.get()
        if profile is not None:profile['router_v2']=self.telemetry
        return self.decision
    async def respond(self,message,response):return await self.gateway.respond(message,response)




def score(case,response,state,observed,titles,searches,profile,index):
    ids=response.seed_work_ids if response.intent in {'MORE_LIKE_THIS','RECOMMEND_FROM_SELECTION','RECOMMEND_FROM_BOOK'} else state.last_referenced_work_ids
    if case['expected_intent']=='CLARIFICATION':ids=[]
    intent_ok=response.intent.value==case['expected_intent'];reference_ok=ids==case['expected_ids']
    fields_ok=not case['fields'] or bool(response.comparison and set(case['fields'])<=set(response.comparison.requested_fields))
    criterion_ok=not case['criterion'] or bool(observed.decision and observed.decision.criterion and not response.clarification)
    clarification_ok=True
    if case['category']=='factual_comparison':clarification_ok=not response.clarification
    if case['category']=='preference':clarification_ok=bool(response.clarification and response.clarification.type=='CRITERIA_AMBIGUITY')
    if case['expected_intent']=='CLARIFICATION':clarification_ok=bool(response.clarification)
    gated=case['category'] not in {'explicit_entity','search'}
    return {**case,'index':index,'actual_intent':response.intent.value,'resolved_ids':ids,
        'semantic_decision':observed.decision.model_dump(mode='json') if observed.decision else None,
        'raw_output':list(observed.raw),'telemetry':dict(observed.telemetry),
        'prompt_sha256':observed.prompt_hash,'schema_sha256':observed.schema_hash,
        'message_result':response.message,'comparison_fields':response.comparison.requested_fields if response.comparison else [],
        'clarification':response.clarification.model_dump() if response.clarification else None,
        'profile':profile,'title_calls':titles,'search_calls':searches,'errors':[e.code for e in response.errors],
        'intent_ok':intent_ok,'reference_ok':reference_ok,'criterion_ok':criterion_ok,'clarification_ok':clarification_ok,
        'pass':bool(intent_ok and reference_ok and fields_ok and criterion_ok and clarification_ok and not response.errors and (not gated or not titles and not searches))}


def percentile(values,p):
    values=sorted(values)
    return values[min(len(values)-1,int((len(values)-1)*p))] if values else None


def normalize_scoring(rows):
    """Goal is part of correctness, even when the executor rendered a table.

    Keep compatibility scores separately; never rewrite the original evidence.
    These labels follow category definitions, not phrase-specific rules.
    """
    for row in rows:
        goal={'factual_comparison':'FACTUAL_COMPARE','preference':'PREFERENCE_COMPARE',
            'preference_criterion':'PREFERENCE_COMPARE','field_comparison':'COMPARE_BY_FIELD',
            'subject_comparison':'COMPARE_BY_FIELD'}.get(row['category'])
        if row.get('fields') and row['expected_intent']=='COMPARE_BOOKS':goal='COMPARE_BY_FIELD'
        row.setdefault('compatibility_pass',row['pass'])
        row.setdefault('criterion_presence_ok',row['criterion_ok'])
        row['criterion_ok']=bool(row['criterion_presence_ok'] and row.get('criterion_semantic_ok',True))
        row['expected_goal']=goal
        row['goal_ok']=not goal or (row.get('semantic_decision') or {}).get('goal')==goal
        row['pass']=bool(row['compatibility_pass'] and row['goal_ok'] and row.get('criterion_semantic_ok',True))
    return rows


def metrics(rows):
    normalize_scoring(rows)
    n=len(rows)
    def fraction(key,pool=rows):return {'passed':sum(bool(r.get(key)) for r in pool),'total':len(pool),
        'percent':round(100*sum(bool(r.get(key)) for r in pool)/len(pool),2) if pool else None}
    critical=[r for r in rows if r['context'] in {'selected','comparison','changed','page'} and r['category'] not in {'explicit_entity','search'}]
    nonentity=[r for r in rows if r['category'] not in {'explicit_entity','search'}]
    calls=[len(r['profile']['qwen_calls']) for r in rows]
    timings=[r['profile']['total_ms'] for r in rows]
    qwen=[c for r in rows for c in r['profile']['qwen_calls']]
    book_references=[r for r in rows if r['expected_ids'] and r['category']!='explicit_entity']
    for r in book_references:
        expected_handle={'selected':'S','changed':'S','comparison':'C','page':'P'}.get(r['context'])
        data=r.get('semantic_decision') or {}
        scope=data.get('reference_scope')
        actual_handle={'SELECTED_BOOKS':'S','PREVIOUS_COMPARISON':'C','CURRENT_PAGE_BOOK':'P',
            'PREVIOUS_RECOMMENDATIONS':'R','RECENT_RESULTS':'T'}.get(scope)
        if scope=='NONE':actual_handle=expected_handle
        r['expected_reference_handle']=expected_handle
        r['reference_handle_ok']=actual_handle==expected_handle
        pools={'selected':[fixtures.A,fixtures.B],'comparison':[fixtures.A,fixtures.B],
            'changed':[fixtures.C,fixtures.D],'page':[fixtures.B]}
        pool=pools.get(r['context'],[])
        try:
            bound=data.get('resolved_work_ids') or router_v2.bind_position(pool,data.get('reference_position') or 'ALL',[])
            r['position_ok']=bound==r['expected_ids']
        except ValueError:r['position_ok']=False
    categories={k:fraction('pass',[r for r in rows if r['category']==k]) for k in sorted({r['category'] for r in rows})}
    return {'strict':fraction('pass'),'intent':fraction('intent_ok'),'reference_position':fraction('reference_ok'),
        'reference_handle':fraction('reference_handle_ok',book_references),
        'position':fraction('position_ok',book_references),
        'criterion':fraction('criterion_ok',[r for r in rows if r['criterion']]),'clarification':fraction('clarification_ok'),
        'criterion_presence':fraction('criterion_presence_ok',[r for r in rows if r['criterion']]),
        'comparison_goal':fraction('goal_ok',[r for r in rows if r['expected_goal']]),
        'compatibility_strict':fraction('compatibility_pass'),
        'critical_context':fraction('pass',critical),'categories':categories,
        'fuzzy_false_positives':sum(bool(r['title_calls']) for r in nonentity),
        'unrelated_search_fallbacks':sum(bool(r['search_calls']) for r in nonentity),
        'schema_invalid':sum(r['telemetry'].get('invalid_kind')=='SCHEMA_INVALID' for r in rows),
        'semantic_invalid':sum(r['telemetry'].get('invalid_kind')=='SEMANTICALLY_INCONSISTENT' for r in rows),
        'first_pass_valid':sum(r['telemetry'].get('first_pass_valid',False) for r in rows),
        'retry_requests':sum(r['telemetry'].get('retry_used',False) for r in rows),
        'median_ms':statistics.median(timings) if timings else None,'p90_ms':percentile(timings,.9),
        'qwen_calls_per_request':sum(calls)/n if n else None,'max_qwen_calls':max(calls,default=0),
        'prose_calls':sum(c.get('stage')=='response' for c in qwen),
        'median_input_tokens':statistics.median([c['input_tokens'] for c in qwen if 'input_tokens' in c]) if any('input_tokens' in c for c in qwen) else None,
        'median_output_tokens':statistics.median([c['generated_tokens'] for c in qwen if 'generated_tokens' in c]) if any('generated_tokens' in c for c in qwen) else None}


async def run_cases(engine,label,variant,cases,retry=False):
    gateway=QwenGateway(engine.llm,engine.inference_lock)
    observed=VariantGateway(gateway,variant,retry)
    orch=AssistantOrchestrator(observed,ConversationStore());rows=[]
    existing=ROOT/'reports'/f'assistant_router_v2_{label}_cases.json'
    if existing.exists():
        previous=json.loads(existing.read_text(encoding='utf8'))
        if previous['architecture']!=variant or previous['retry']!=retry:
            archive=existing.with_name(existing.stem+'_superseded_'+previous['architecture']+existing.suffix)
            assert not archive.exists(),'Preserve superseded experiments uniquely'
            existing.rename(archive)
        else:
            rows=previous['cases']
            assert all(rows[i]['message']==cases[i]['message'] for i in range(len(rows)))
            normalize_scoring(rows)
    try:
        for index,case in enumerate(cases):
            if index<len(rows):continue
            tools=fixtures.FixtureTools(schemas,tool_module)
            request=fixtures.establish(orch,case,schemas)
            response,profile,titles,searches=await fixtures.measured_case(orch,tools,request)
            row=score(case,response,orch.store.entries[request.conversation_id],observed,titles,searches,profile,index)
            rows.append(row)
            write(f'assistant_router_v2_{label}_cases.json',{'variant':label,'architecture':variant,'retry':retry,
                'method':'real resident Qwen; unchanged authoritative API fixtures','complete':len(rows)==len(cases),
                'metrics':metrics(rows),'cases':rows})
            print('V2',label,index+1,'/',len(cases),response.intent.value,row['pass'],round(profile['total_ms']),flush=True)
    finally:gateway.close()
    write(f'assistant_router_v2_{label}_cases.json',{'variant':label,'architecture':variant,'retry':retry,
        'method':'real resident Qwen; unchanged authoritative API fixtures','complete':len(rows)==len(cases),
        'metrics':metrics(rows),'cases':rows})
    return {'architecture':variant,'retry':retry,'metrics':metrics(rows),'case_report':f'assistant_router_v2_{label}_cases.json'}


async def evaluate(engine):
    cases=fixtures.corpus();assert len(cases)==116
    matrix={'method':'same 116 utterances, fixtures, resident Qwen and generation settings; no model change',
        'model':'Qwen2.5-3B-Instruct 4-bit NF4 CUDA','max_new_tokens':180,
        'critical_definition':'selected/comparison/changed/page contexts, excluding literal-entity and search cases',
        'variants':{},'complete':False}
    requested=os.environ.get('ROUTER_V2_VARIANTS','A,B,C,D,E,E2').split(',')
    for label in requested:
        matrix['variants'][label]=await run_cases(engine,label,label,cases)
        write('assistant_router_v2_experiments.json',matrix)
    if set('ABCDE')<=set(matrix['variants']):
        best=max(matrix['variants'],key=lambda k:(matrix['variants'][k]['metrics']['strict']['percent'],
            matrix['variants'][k]['metrics']['critical_context']['percent'],-matrix['variants'][k]['metrics']['median_ms']))
        matrix['best_before_retry']=best
        matrix['variants']['F']=await run_cases(engine,'F',best,cases,True)
        matrix['complete']='F' in matrix['variants']
        write('assistant_router_v2_experiments.json',matrix)
    return matrix


if __name__=='__main__':
    os.environ['ASSISTANT_PROFILE_PATH']=str(ROOT/'reports/assistant_router_v2_http_profiles.jsonl')
    import rag.api
    async def startup():
        async def task():
            try:
                await evaluate(rag.api.engine)
                trigger=ROOT/'reports/.router_v2_run'
                while True:
                    await asyncio.sleep(1)
                    if trigger.exists():
                        mode=trigger.read_text().strip();trigger.unlink()
                        if mode=='matrix':await evaluate(rag.api.engine)
                        elif mode.startswith('hidden:'):
                            import assistant_router_v2_corpus
                            _,variant,retry=mode.split(':')
                            await run_cases(rag.api.engine,'hidden',variant,assistant_router_v2_corpus.hidden(),retry=='retry')
            except Exception as exc:
                write('assistant_router_v2_eval_error.json',{'type':type(exc).__name__,'message':str(exc)})
                import traceback;traceback.print_exc()
        rag.api.app.state.router_v2_evaluation=asyncio.create_task(task())
    rag.api.app.router.add_event_handler('startup',startup)
    import uvicorn
    uvicorn.run(rag.api.app,host='127.0.0.1',port=8005,workers=1)
