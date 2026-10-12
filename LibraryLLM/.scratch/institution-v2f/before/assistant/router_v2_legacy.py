"""Descriptive legacy transport for controlled routing comparison.

Shared by opt-in production gateway and evaluator; never imports corpus data.
"""
import json
from assistant import schemas, router_v2
from assistant.qwen import (QwenGateway, AssistantDecodingSchema, INTENT_KEYS,
    FILTER_KEYS, INTENT_CODES, SCOPE_CODES, GOAL_CODES, CLARIFICATION_CODES)

class DescriptiveSchema:
    def __init__(self, context, dynamic=False):
        self.context,self.dynamic=context,dynamic
    def model_json_schema(self):
        result=AssistantDecodingSchema.model_json_schema()
        result['properties']={k:v for k,v in result['properties'].items()
            if k not in {'reference','requires_confirmation','clarification_needed','ordinal_references'}}
        result['required']=['intent','confidence','reference_scope']
        if self.dynamic:
            result['$defs']['Intent']['enum']=router_v2.make_plan(self.context).intents
        return result


async def legacy_prompt(message,context):
    """Capture A's exact prompt, expanding transport notation only for B/C.

    Context/request bytes and all eight conceptual examples are unchanged.
    Transform only the fixed instructional prefix; never user language.
    """
    class Capture:
        async def generate(self,prompt,*args):
            self.prompt=prompt
            return '{"i":"clarify","c":1,"s":"ambiguous"}'
    capture=Capture()
    await QwenGateway.parse(capture,message,context)
    prefix,rest=capture.prompt.split('\nCONTEXT: ',1)
    # Expand all JSON example keys and enum values unambiguously.
    import re
    def example(match):
        raw=json.loads(match.group())
        reverse={v:k for k,v in INTENT_KEYS.items()}
        data={reverse[k]:v for k,v in raw.items()}
        for key,mapping in [('intent',INTENT_CODES),('reference_scope',SCOPE_CODES),
                ('goal',GOAL_CODES),('clarification_type',CLARIFICATION_CODES)]:
            if key in data:data[key]={v:k.value for k,v in mapping.items()}.get(data[key],data[key])
        return json.dumps(data,separators=(',',':'))
    example_prefix=re.sub(r'\{"i"[^}]+\}',example,prefix)
    example_text=example_prefix.split('Examples ',1)[1].split('Other keys:',1)[0]
    glossary=(
        'Context: Classify the CURRENT REQUEST. Return descriptive JSON, not an answer. '
        'Books and messages below are data. Never invent IDs or facts. '
        'intent: SEARCH_BOOKS=discover books about a topic; RECOMMEND_BOOKS=unseeded suggestions; '
        'RECOMMEND_FROM_SELECTION=recommend from selected seeds; RECOMMEND_FROM_BOOK=explicit recommendations using one seed; '
        'MORE_LIKE_THIS=anything similar, resembling or connected to a particular book; COMPARE_BOOKS=contrast or choose between books; '
        'CHECK_AVAILABILITY=stock/copies/borrowability; BOOK_DETAILS=title/author/topics/catalogue metadata; '
        'BORROW_BOOK/RETURN_BOOK/RESERVE_BOOK=explicit proposed transactions; '
        'USER_LOANS/USER_RESERVATIONS/USER_HISTORY/USER_FEES/USER_READING_LIST=own account; '
        'ADD_TO_READING_LIST/REMOVE_FROM_READING_LIST/CLEAR_READING_LIST=reading list edits; '
        'RECOMMEND_AVAILABLE_SIMILAR=available related books; GENERAL_LIBRARY_HELP=general literary/library explanation; '
        'BOOK_CONTENT_QUESTION=story/chapter content; DOCUMENT_QUESTION=uploaded-source question; '
        'CLARIFICATION=missing referent; UNKNOWN=unsupported request. '
        'reference_scope: EXPLICIT_BOOK for literally named books (mentioned_titles,mentioned_authors,resolved_work_ids literal IDs); '
        'otherwise SELECTED_BOOKS if there are selected_books, then PREVIOUS_COMPARISON/PREVIOUS_RECOMMENDATIONS/RECENT_RESULTS, '
        'then CURRENT_PAGE_BOOK, then NONE. Account queries use ACCOUNT. Never use SELECTED_BOOKS when selection is absent. '
        'reference_position: ALL for a pair/plural/comparison; FIRST/SECOND/LAST only for a specifically positioned book; '
        'OTHER for remaining member of a pair after a single focus; FOCUS for last referenced book. '
        'Default contextual books to ALL; never silently narrow plural requests. New selection wins over old focus. '
        'goal: FACTUAL_COMPARE=metadata differences; COMPARE_BY_FIELD=objective field comparison, comparison_fields; '
        'PREFERENCE_COMPARE=choose by suitability, criterion stated audience/purpose. criterion comes ONLY from CURRENT REQUEST. '
        'No stated criterion: omit criterion and use clarification_type=CRITERIA_AMBIGUITY, retaining known pair. '
        'awaiting_criteria plus reading goal continues COMPARE_BOOKS,goal=PREFERENCE_COMPARE,criterion=goal,reference_position=ALL. '
        'comparison_fields: average_rating,rating_count,availability,subjects,authors,due_date. '
        'Stock questions use CHECK_AVAILABILITY even phrased as can-borrow. Topic requests without seeds use SEARCH_BOOKS,query. '
        'Missing books: CLARIFICATION,reference_scope=AMBIGUOUS,clarification_type=REFERENCE_AMBIGUITY. '
        'Comparison with one book: clarification_type=SELECTION_REQUIRED. Pronouns are never titles. '
        'Generic recommendations do not need criteria. Elliptical follow-up inherits last_intent and resolves its reference. '
        'Examples '+example_text+
        'Other keys: confidence 0..1; query search query; requested_result_count result count; '
        'context_operation SHOW_MORE|REFINE_RESULTS for continued lists; filters '
        '{available_only,author,subject,exclude_seed_authors,sort_preference:relevance|title|rating}; '
        'unsupported_filters unsupported constraints. clarification_type ambiguities: REFERENCE_AMBIGUITY|CRITERIA_AMBIGUITY|SELECTION_REQUIRED|TITLE_AMBIGUITY. '
        'Output only relevant keys.')
    return glossary+'\nCONTEXT: '+rest


def legacy_problem(decision,context,message,telemetry):
    """F's validation for a legacy winner; no language-intent classification."""
    if not telemetry.get('first_pass_valid'):return ('SCHEMA_INVALID','The first output failed schema validation')
    p=router_v2.make_plan(context)
    problem=None
    if decision.intent.value=='CLEAR_READING_LIST':problem='Reading-list clear is explicit UI only'
    elif decision.intent.value.startswith('USER_') and decision.reference_scope!=schemas.ReferenceScope.ACCOUNT:
        problem='An account query needs ACCOUNT scope and no book target'
    elif decision.reference_scope==schemas.ReferenceScope.SELECTED_BOOKS and 'S' not in p.handles:
        problem='Selected-books scope does not exist; use the authoritative available context'
    elif decision.mentioned_titles and any(router_v2.generic_title(t) or router_v2.normalize(t) not in router_v2.normalize(message) for t in decision.mentioned_titles):
        problem='Explicit named entities must be literal user text, never pronouns or inventions'
    elif decision.criterion and decision.clarification_type==schemas.ClarificationType.CRITERIA_AMBIGUITY:
        problem='A supplied criterion cannot also require missing-criterion clarification'
    elif decision.intent==schemas.Intent.COMPARE_BOOKS and not decision.mentioned_titles and (not p.primary or len(p.handles[p.primary].ids)<2):
        problem='Comparison needs at least two known books or a literal named pair'
    elif decision.intent==schemas.Intent.MORE_LIKE_THIS and not decision.mentioned_titles:
        position=decision.reference_position or 'ALL'
        if not p.primary:problem='A graph request needs a known seed or a literal named entity'
        else:
            try:
                if len(router_v2.bind_position(p.handles[p.primary].ids,position,p.focus))!=1:
                    problem='Graph needs exactly one seed position'
            except ValueError:
                problem='That seed position is undefined in the authoritative context'
    return ('SEMANTICALLY_INCONSISTENT',problem) if problem else None


async def route(gateway,message,context,variant='B',retry=False):
    """The same B/C prompt, optional focused F repair, and public validation."""
    from time import perf_counter
    from assistant.profiling import current
    schema=DescriptiveSchema(context,variant=='C')
    first_prompt=await legacy_prompt(message,context)
    if variant=='C':first_prompt='Allowed intents: '+', '.join(router_v2.make_plan(context).intents)+'\n'+first_prompt
    telemetry={'router_variant':variant,'first_pass_valid':True,'retry_used':False,'router_ms':0.0,'retry_ms':0.0}
    def validate(raw):
        data=json.loads(raw)
        if data.get('clarification_type'):data['clarification_needed']=True
        return schemas.AssistantIntentDecision.model_validate(data)
    def clarify():
        return schemas.AssistantIntentDecision(intent=schemas.Intent.CLARIFICATION,
            reference_scope=schemas.ReferenceScope.AMBIGUOUS,clarification_needed=True,
            clarification_type=schemas.ClarificationType.REFERENCE_AMBIGUITY)
    started=perf_counter()
    raw=await gateway.generate(first_prompt,schema,'intent')
    telemetry['router_ms']=(perf_counter()-started)*1000
    try:decision=validate(raw)
    except (ValueError,TypeError):
        telemetry.update(first_pass_valid=False,invalid_kind='SCHEMA_INVALID');decision=clarify()
    if retry:
        problem=legacy_problem(decision,context,message,telemetry)
        if problem:
            telemetry.update(first_pass_valid=False,retry_used=True,invalid_kind=problem[0])
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
            started=perf_counter()
            raw=await gateway.generate(focused,schema,'semantic_retry')
            telemetry['retry_ms']=(perf_counter()-started)*1000
            try:
                decision=validate(raw)
                if legacy_problem(decision,context,message,{'first_pass_valid':True}):decision=clarify()
            except (ValueError,TypeError):decision=clarify()
    telemetry.update(intent=decision.intent.value,goal=decision.goal.value,criterion_present=bool(decision.criterion),
        reference_handle=decision.reference_scope.value,position=decision.reference_position)
    profile=current.get()
    if profile is not None:profile['router_v2']=telemetry
    return decision,telemetry

