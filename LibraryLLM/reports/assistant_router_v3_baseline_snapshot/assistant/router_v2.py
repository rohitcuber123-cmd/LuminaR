"""Descriptive, capability-bounded routing. No language phrase classifier.

Only identity context and validated decisions live here. Existing executors,
ownership checks, confirmations, ranking, pagination and RAG remain authority.
"""
from dataclasses import dataclass
import json
from typing import Literal

from pydantic import Field, create_model

from assistant.schemas import (AssistantIntentDecision, ClarificationType,
    Filters, Intent, ReferenceScope, SemanticGoal, StrictModel)
from assistant.semantic import bind_position, literal_ids, unique
from assistant.contextual import generic_title, normalize


class DecisionInvalid(ValueError):
    def __init__(self, reason, kind='SEMANTICALLY_INCONSISTENT'):
        self.reason, self.kind = reason, kind
        super().__init__(reason)


@dataclass
class Handle:
    key: str
    kind: str
    ids: list[str]
    identities: list[dict]


@dataclass
class Plan:
    handles: dict[str, Handle]
    primary: str | None
    focus: list[str]
    context: dict
    intents: list[str]
    positions: list[str]
    document: bool


def identity(book, position):
    # Model sees position and bounded identity text, never authoritative IDs.
    return {'position': position, 'title': str(book.get('title') or '')[:240],
            'authors': str(book.get('authors') or '')[:160]}


def allowed_intents(context, count):
    """Capabilities only; this function never sees the user message."""
    result = [Intent.SEARCH_BOOKS, Intent.RECOMMEND_BOOKS,
        Intent.COMPARE_BOOKS, Intent.CHECK_AVAILABILITY, Intent.BOOK_DETAILS,
        Intent.MORE_LIKE_THIS, Intent.BORROW_BOOK, Intent.RESERVE_BOOK,
        Intent.USER_LOANS, Intent.USER_RESERVATIONS, Intent.USER_HISTORY,
        Intent.USER_FEES, Intent.USER_READING_LIST, Intent.GENERAL_LIBRARY_HELP,
        Intent.BOOK_CONTENT_QUESTION, Intent.CLARIFICATION, Intent.UNKNOWN]
    if count:
        result += [Intent.RECOMMEND_FROM_BOOK, Intent.RECOMMEND_AVAILABLE_SIMILAR,
            Intent.ADD_TO_READING_LIST, Intent.REMOVE_FROM_READING_LIST, Intent.RETURN_BOOK]
    if count >= 2:
        result.append(Intent.RECOMMEND_FROM_SELECTION)
    if context.get('document_id'):
        result.append(Intent.DOCUMENT_QUESTION)
    return [i.value for i in result]


def make_plan(context):
    handles = {}
    def add(key, kind, books, ids=None):
        ids = unique(ids if ids is not None else [b['work_id'] for b in books])
        if ids:
            index = {b['work_id']: b for b in books}
            handles[key] = Handle(key, kind, ids, [identity(index.get(w, {}), i+1)
                for i, w in enumerate(ids[:4])])
    add('S', 'CURRENT SELECTION — PRIMARY', context.get('selected_books', []))
    active = context.get('active_result_context', {})
    active_ids = active.get('work_ids', [])
    comparison = context.get('previous_comparison', [])
    # Active empty results are authoritative; older references stay unavailable.
    if active_ids and active.get('type') == 'comparison':
        add('C', 'PREVIOUS COMPARISON', comparison, active_ids)
    elif comparison and 'active_result_context' not in context:
        add('C', 'PREVIOUS COMPARISON', comparison)
    recommendations = context.get('previous_recommendations', {})
    if active_ids:
        add('R' if active.get('type') == 'recommendations' else 'T',
            'ACTIVE RESULTS', active.get('books', []), active_ids)
    elif 'active_result_context' not in context and recommendations.get('work_ids'):
        add('R', 'PREVIOUS RECOMMENDATIONS', [], recommendations['work_ids'])
    add('P', 'PAGE BOOK', context.get('page_books', []))
    focus = context.get('last_referenced_work_ids', [])
    if focus and 'active_result_context' not in context:
        known = context.get('selected_books', []) + context.get('page_books', []) + comparison
        add('F', 'RECENT RESOLVED BOOKS', known, focus)
    primary = next((key for key in ['S', 'C', 'R', 'T', 'P', 'F'] if key in handles), None)
    # Duplicate sources do not create another model choice. Fallbacks are server
    # state, not equal-looking candidates competing with current selection.
    count = len(handles[primary].ids) if primary else 0
    focus = [w for w in focus if primary and w in handles[primary].ids]
    if context.get('selection_changed'):
        focus = []
    positions = ['FOCUS'] if count == 1 else ['ALL','FIRST','SECOND'] if count >= 2 else []
    if count >= 3:
        positions += ['THIRD','LAST']
    if count >= 4:
        positions.append('FOURTH')
    if len(focus) == 1 and count > 1:
        positions.append('FOCUS')
        if count == 2:
            positions.append('OTHER')
    model_context = {}
    if primary:
        model_context['book_context'] = {'handle': primary, 'kind': handles[primary].kind,
            'books': handles[primary].identities}
        if len(focus) == 1:
            model_context['focused_position'] = handles[primary].ids.index(focus[0]) + 1
    if context.get('last_intent'):
        model_context['previous_intent'] = str(context['last_intent'])
    if context.get('awaiting_criteria'):
        model_context['awaiting_reading_goal'] = True
    if context.get('document_id'):
        model_context['document_selected'] = True
    if active.get('has_more'):
        model_context['more_results_available'] = True
    if active.get('query'):
        model_context['active_query'] = active['query'][:200]
    if active.get('filters'):
        model_context['active_filters'] = active['filters']
    return Plan(handles, primary, focus, model_context,
        allowed_intents(context, count), positions, bool(context.get('document_id')))


FIELDS = Literal['average_rating','rating_count','availability','subjects','authors','title','due_date']


def flat_model(plan, dynamic=True, handles=True):
    intents = plan.intents if dynamic else [i.value for i in Intent]
    definitions = {'intent': (Literal[tuple(intents)], ...),
        'entity_text': (str | None, Field(default=None, max_length=300)),
        'compare_mode': (Literal['FACTUAL','FIELD','PREFERENCE'] | None, None),
        'criterion': (str | None, Field(default=None, max_length=300)),
        'fields': (list[FIELDS], Field(default_factory=list, max_length=7)),
        'query': (str | None, Field(default=None, max_length=2000))}
    if plan.positions:
        definitions['position'] = (Literal[tuple(plan.positions)] | None, None)
    # The single permitted primary context is pre-bound by the server. The
    # model has no scope question and no work-ID output field.
    if plan.context.get('active_query'):
        definitions['result_action'] = (Literal['CONTINUE','REFINE'] | None, None)
        definitions['filters'] = (Filters | None, None)
    return create_model('DescriptiveHandleDecision', __base__=StrictModel, **definitions)


FAMILY_ACTIONS = {
    'DISCOVER': {'SEARCH':Intent.SEARCH_BOOKS, 'RECOMMEND':Intent.RECOMMEND_BOOKS,
        'MORE_LIKE_THIS':Intent.MORE_LIKE_THIS,
        'AVAILABLE_SIMILAR':Intent.RECOMMEND_AVAILABLE_SIMILAR},
    'BOOK': {'DETAILS':Intent.BOOK_DETAILS, 'AVAILABILITY':Intent.CHECK_AVAILABILITY,
        'BORROW':Intent.BORROW_BOOK, 'RESERVE':Intent.RESERVE_BOOK,
        'RETURN':Intent.RETURN_BOOK, 'ADD_TO_READING_LIST':Intent.ADD_TO_READING_LIST,
        'REMOVE_FROM_READING_LIST':Intent.REMOVE_FROM_READING_LIST},
    'ACCOUNT': {'LOANS':Intent.USER_LOANS, 'RESERVATIONS':Intent.USER_RESERVATIONS,
        'HISTORY':Intent.USER_HISTORY, 'FEES':Intent.USER_FEES,
        'READING_LIST':Intent.USER_READING_LIST},
    'CONTENT': {'BOOK_RAG':Intent.BOOK_CONTENT_QUESTION, 'DOCUMENT_RAG':Intent.DOCUMENT_QUESTION},
}


def family_model(plan):
    # Conditional JSON branches reduce irrelevant fields, not merely rename
    # one flat enum. Only the selected branch's output fields are permitted.
    branches = []
    book_fields = {'entity_text':(str | None,Field(default=None,max_length=300))}
    if plan.positions:
        book_fields['position'] = (Literal[tuple(plan.positions)] | None, None)
    for family, actions in FAMILY_ACTIONS.items():
        available = [a for a,i in actions.items() if i.value in plan.intents]
        if not available:
            continue
        fields = {'intent_family':(Literal[family],...),
            'action':(Literal[tuple(available)],...)}
        if family != 'ACCOUNT': fields.update(book_fields)
        if family == 'DISCOVER':
            fields['query'] = (str | None,Field(default=None,max_length=2000))
            fields['criterion'] = (str | None,Field(default=None,max_length=300))
            if plan.context.get('active_query'):
                fields['result_action'] = (Literal['CONTINUE','REFINE'] | None,None)
                fields['filters'] = (Filters | None,None)
        branches.append(create_model(f'{family}Decision',__base__=StrictModel,**fields))
    branches.append(create_model('COMPAREDecision',__base__=StrictModel,
        intent_family=(Literal['COMPARE'],...),
        compare_mode=(Literal['FACTUAL','FIELD','PREFERENCE'],...),
        criterion=(str | None,Field(default=None,max_length=300)),
        fields=(list[FIELDS],Field(default_factory=list,max_length=7)),**book_fields))
    for family in ['HELP','CLARIFY']:
        branches.append(create_model(f'{family}Decision',__base__=StrictModel,
            intent_family=(Literal[family],...)))
    class FamilySchema:
        @classmethod
        def model_json_schema(cls):
            defs = {}; choices = []
            for model in branches:
                schema = model.model_json_schema()
                defs.update(schema.pop('$defs', {}));choices.append(schema)
            return {'anyOf':choices,'$defs':defs}
        @classmethod
        def model_validate(cls, raw):
            family = raw.get('intent_family') if isinstance(raw,dict) else None
            model = next((m for m in branches if m.model_fields['intent_family'].annotation.__args__[0]==family),None)
            if model is None: raise ValueError('Unknown intent family')
            return model.model_validate(raw)
    return FamilySchema


def strict_family_model(plan):
    """E2: mode-specific required fields; comparison references are pre-bound.

    Keeping criterion optional made the small model close its object before
    extracting an explicitly stated purpose. Require a nullable criterion only
    for PREFERENCE, and nonempty fields only for FIELD. FACTUAL has neither.
    """
    base=family_model(plan)
    original=base.model_json_schema()
    entity={'entity_text':(str | None,Field(default=None,max_length=300))}
    compare_models=[]
    for mode in ['FACTUAL','FIELD','PREFERENCE']:
        fields={'intent_family':(Literal['COMPARE'],...),
            'compare_mode':(Literal[mode],...),**entity}
        if mode=='PREFERENCE':fields['criterion']=(str | None,Field(...,max_length=300))
        if mode=='FIELD':fields['fields']=(list[FIELDS],Field(...,min_length=1,max_length=7))
        compare_models.append(create_model(f'{mode}Comparison',__base__=StrictModel,**fields))
    class StrictFamilySchema:
        @classmethod
        def model_json_schema(cls):
            branches=[s for s in original['anyOf'] if s['properties']['intent_family'].get('const')!='COMPARE']
            return {'anyOf':branches+[m.model_json_schema() for m in compare_models],'$defs':original['$defs']}
        @classmethod
        def model_validate(cls,raw):
            if isinstance(raw,dict) and raw.get('intent_family')=='COMPARE':
                mode=raw.get('compare_mode')
                index={'FACTUAL':0,'FIELD':1,'PREFERENCE':2}.get(mode)
                if index is None:raise ValueError('Unknown comparison mode')
                return compare_models[index].model_validate(raw)
            return base.model_validate(raw)
    return StrictFamilySchema


def examples(plan, hierarchical):
    # Fixed conceptual examples chosen by capability availability, never by a
    # regex, semantic retrieval, or test-message lookup.
    if plan.primary and len(plan.handles[plan.primary].ids) >= 2:
        rows = [('Contrast their recorded metadata', {'intent':'COMPARE_BOOKS','compare_mode':'FACTUAL','position':'ALL'}),
            ('Help choose between my selections', {'intent':'COMPARE_BOOKS','compare_mode':'PREFERENCE','position':'ALL'}),
            ('Choose a reading pick for an advanced researcher', {'intent':'COMPARE_BOOKS','compare_mode':'PREFERENCE','criterion':'advanced researcher','position':'ALL'}),
            ('Are any copies of these free?', {'intent':'CHECK_AVAILABILITY','position':'ALL'}),
            ('Author of item number two', {'intent':'BOOK_DETAILS','position':'SECOND'})]
    elif plan.primary:
        rows = [('Check its stock',{'intent':'CHECK_AVAILABILITY','position':'FOCUS'}),
            ('Find related titles for this book',{'intent':'MORE_LIKE_THIS','position':'FOCUS'}),
            ('Outstanding charges on my account',{'intent':'USER_FEES'})]
    else:
        rows = [('Outstanding charges on my account',{'intent':'USER_FEES'}),
            ('Records of my earlier loans',{'intent':'USER_HISTORY'}),
            ('Books about soil science',{'intent':'SEARCH_BOOKS','query':'soil science'}),
            ('Author of The Martian',{'intent':'BOOK_DETAILS','entity_text':'The Martian'})]
    if hierarchical:
        rows = [(text, to_family(data)) for text,data in rows]
    return rows


def to_family(data):
    data = dict(data); intent=data.pop('intent')
    if intent=='COMPARE_BOOKS': return {'intent_family':'COMPARE',**data}
    for family,actions in FAMILY_ACTIONS.items():
        action=next((a for a,i in actions.items() if i.value==intent),None)
        if action:return {'intent_family':family,'action':action,**data}
    return {'intent_family':'HELP' if intent=='GENERAL_LIBRARY_HELP' else 'CLARIFY'}


def prompt(message, plan, hierarchical=False, retry_reason=None, strict_compare=False):
    mode = 'intent_family and its action' if hierarchical else 'intent'
    if retry_reason:
        return ('Context: Correct one structurally inconsistent library routing decision. '
            f'Problem: {retry_reason}. Choose {mode}; JSON only. '
            'COMPARE modes: FACTUAL describes differences, FIELD compares recorded fields, '
            'PREFERENCE chooses suitability. Copy a stated audience/purpose into criterion; '
            'never ask for a criterion already supplied. Entity text must be literal user text. '
            + options(plan,hierarchical) + '\nBOOK CONTEXT: ' + json.dumps(plan.context,separators=(',',':'))
            + '\nUSER REQUEST: '+json.dumps(message))
    instructions = (
        f'Context: Interpret the USER REQUEST as a library routing decision. Return {mode} in JSON only. '
        'Never answer or invent book facts. Book context is server-defined. '
        'Contrast or differences with no choice asked = COMPARE FACTUAL. '
        'Highest rating or topic count = COMPARE FIELD, fields average_rating/rating_count/subjects. '
        'Choosing suitability = COMPARE PREFERENCE; criterion is stated purpose/audience, otherwise null. '
        'With a known pair, missing preference criteria still means COMPARE PREFERENCE; the server asks for a reading goal. '
        'Stock/copies/borrowability = AVAILABILITY, not a borrowing transaction. '
        'Title/author/catalogue subjects = DETAILS; narrative/chapter meaning = CONTENT. '
        'Related/like/connected titles around one book = MORE_LIKE_THIS. '
        'Recommendations from picks = RECOMMEND; finding books on a topic = SEARCH with query. '
        'Own checked-out items = LOANS; past borrowing = HISTORY; holds = RESERVATIONS; '
        'money owed = FEES; saved future reads = READING_LIST. Account queries need no book target. '
    )
    if plan.primary:
        instructions += ('Book references default to the primary handle. Position ALL includes the set; '
            'FIRST/SECOND/LAST identify order. OTHER is the remaining member after one focused book; '
            'FOCUS uses the single last referenced book. Only choose positions listed below. '
            'Literal entity_text overrides contextual books, and must be copied from the request. '
            'An elliptical follow-up inherits the previous intent; if awaiting a reading goal, continue COMPARE PREFERENCE. ')
    else:
        instructions += ('No contextual book exists. A literal title may use entity_text; '
            'unresolved pronouns need CLARIFY. Never treat pronouns as titles. ')
    rows=examples(plan,hierarchical)
    if strict_compare:
        instructions+=('COMPARE always uses the whole primary set; omit position. '
            'FACTUAL describes similarities/differences without choosing an objective field or a reading winner. '
            'FIELD must supply the recorded fields being compared. PREFERENCE must supply criterion, using null only when no purpose/audience is stated. ')
        rows=[(text,{k:v for k,v in data.items() if not (data.get('intent_family')=='COMPARE' and k=='position')}) for text,data in rows]
        if plan.primary and len(plan.handles[plan.primary].ids)>=2:
            for text,data in rows:
                if data.get('compare_mode')=='PREFERENCE':data.setdefault('criterion',None)
            rows.append(('Which entry has the largest recorded rating?',
                {'intent_family':'COMPARE','compare_mode':'FIELD','fields':['average_rating']}))
    return (instructions + options(plan,hierarchical) + '\nEXAMPLES: '
        + json.dumps(rows,separators=(',',':'))
        + '\nBOOK CONTEXT: '+json.dumps(plan.context,separators=(',',':'))
        + '\nUSER REQUEST: '+json.dumps(message))


def options(plan, hierarchical):
    if hierarchical:
        actions = {f:[a for a,i in acts.items() if i.value in plan.intents]
                   for f,acts in FAMILY_ACTIONS.items()}
        actions = {f:a for f,a in actions.items() if a}
        actions.update(COMPARE=['FACTUAL','FIELD','PREFERENCE'],HELP=[],CLARIFY=[])
        allowed = json.dumps(actions,separators=(',',':'))
    else:
        allowed = ','.join(plan.intents)
    return ('Allowed decisions: '+allowed+'. '
        + ('Allowed positions: '+','.join(plan.positions)+'. ' if plan.positions else '')
        + 'Optional fields only when relevant: entity_text, criterion, fields, query. '
        + ('Result lists may use result_action CONTINUE or REFINE with validated filters. ' if plan.context.get('active_query') else ''))


def expand(raw, plan, message):
    data=raw.model_dump(exclude_none=True)
    if 'intent_family' in data:
        family=data.pop('intent_family')
        if family=='COMPARE': intent=Intent.COMPARE_BOOKS
        elif family=='HELP': intent=Intent.GENERAL_LIBRARY_HELP
        elif family=='CLARIFY': intent=Intent.CLARIFICATION
        else:intent=FAMILY_ACTIONS[family][data.pop('action')]
    else:intent=Intent(data.pop('intent'))
    if intent.value not in plan.intents and intent not in {Intent.CLARIFICATION,Intent.GENERAL_LIBRARY_HELP}:
        raise DecisionInvalid('That intent is unavailable for the supplied capabilities.')
    entity=data.get('entity_text')
    position=data.get('position')
    mode=data.get('compare_mode')
    criterion=data.get('criterion')
    fields=data.get('fields',[])
    account={Intent.USER_LOANS,Intent.USER_RESERVATIONS,Intent.USER_HISTORY,Intent.USER_FEES,Intent.USER_READING_LIST}
    values={'intent':intent,'confidence':1.0}
    if intent in account:
        if entity or position or mode or criterion or fields:
            raise DecisionInvalid('Account queries have no book reference, comparison mode or criterion.')
        values['reference_scope']=ReferenceScope.ACCOUNT
    elif intent==Intent.CLARIFICATION:
        values.update(reference_scope=ReferenceScope.AMBIGUOUS,clarification_needed=True,
                      clarification_type=ClarificationType.REFERENCE_AMBIGUITY)
    elif intent==Intent.GENERAL_LIBRARY_HELP:
        values['reference_scope']=ReferenceScope.NONE
    elif entity:
        if generic_title(entity) or normalize(entity) not in normalize(message):
            raise DecisionInvalid('Explicit entity_text must be a literal named entity in the user request.')
        values.update(reference_scope=ReferenceScope.EXPLICIT_BOOK,mentioned_titles=[entity])
        if entity in literal_ids(message) and any(entity in h.ids for h in plan.handles.values()):
            values.update(resolved_work_ids=[entity],mentioned_titles=[])
    elif plan.primary:
        handle=plan.handles[plan.primary]
        position=position or ('FOCUS' if len(handle.ids)==1 else 'ALL')
        if position not in plan.positions:
            raise DecisionInvalid('That position is unavailable in the primary context.')
        try:
            if position in {'THIRD','FOURTH'}:
                ids=[handle.ids[2 if position=='THIRD' else 3]]
            else:ids=bind_position(handle.ids,position,plan.focus)
        except ValueError as exc:raise DecisionInvalid(str(exc)) from exc
        values.update(reference_scope={'S':ReferenceScope.SELECTED_BOOKS,'C':ReferenceScope.PREVIOUS_COMPARISON,
            'P':ReferenceScope.CURRENT_PAGE_BOOK,'R':ReferenceScope.PREVIOUS_RECOMMENDATIONS,
            'T':ReferenceScope.RECENT_RESULTS,'F':ReferenceScope.NONE}[plan.primary],resolved_work_ids=ids)
    else:
        values['reference_scope']=ReferenceScope.NONE
    if intent==Intent.COMPARE_BOOKS:
        if mode is None:raise DecisionInvalid('COMPARE needs FACTUAL, FIELD or PREFERENCE mode.')
        if mode=='FIELD' and not fields:raise DecisionInvalid('FIELD comparison needs an authoritative field name.')
        if mode=='FACTUAL' and criterion:raise DecisionInvalid('A reading criterion belongs to PREFERENCE, not FACTUAL.')
        values.update(goal={'FACTUAL':SemanticGoal.FACTUAL_COMPARE,'FIELD':SemanticGoal.COMPARE_BY_FIELD,
            'PREFERENCE':SemanticGoal.PREFERENCE_COMPARE}[mode],comparison_fields=fields,criterion=criterion)
        ids=values.get('resolved_work_ids',[])
        if not entity and len(ids)<2:raise DecisionInvalid('Comparison requires at least two contextual books.')
        if mode=='PREFERENCE' and not criterion:
            values.update(clarification_needed=True,clarification_type=ClarificationType.CRITERIA_AMBIGUITY)
    elif mode or fields and intent!=Intent.BOOK_DETAILS:
        raise DecisionInvalid('Comparison mode/fields are irrelevant to this non-comparison intent.')
    elif criterion and intent not in {Intent.SEARCH_BOOKS,Intent.RECOMMEND_BOOKS,
            Intent.RECOMMEND_FROM_SELECTION,Intent.RECOMMEND_FROM_BOOK,Intent.RECOMMEND_AVAILABLE_SIMILAR}:
        raise DecisionInvalid('A reading criterion is irrelevant to this intent.')
    if intent==Intent.MORE_LIKE_THIS and not entity and len(values.get('resolved_work_ids',[]))!=1:
        raise DecisionInvalid('More Like This needs one seed. Choose one valid position.')
    if intent in {Intent.BOOK_DETAILS,Intent.CHECK_AVAILABILITY,Intent.BORROW_BOOK,Intent.RESERVE_BOOK,
                  Intent.RETURN_BOOK,Intent.BOOK_CONTENT_QUESTION,Intent.ADD_TO_READING_LIST,Intent.REMOVE_FROM_READING_LIST}:
        if not entity and not values.get('resolved_work_ids'):
            raise DecisionInvalid('A book operation needs contextual books or a literal entity.')
    if intent==Intent.BOOK_DETAILS:values['comparison_fields']=fields
    if intent==Intent.SEARCH_BOOKS:
        if not data.get('query'):raise DecisionInvalid('Topic search needs a useful query.')
        values['query']=data['query']
        values['resolved_work_ids']=[];values['reference_scope']=ReferenceScope.NONE
    if intent in {Intent.RECOMMEND_BOOKS,Intent.RECOMMEND_FROM_SELECTION,Intent.RECOMMEND_FROM_BOOK}:
        n=len(values.get('resolved_work_ids',[]))
        values['intent']=Intent.RECOMMEND_FROM_SELECTION if n>1 else Intent.RECOMMEND_FROM_BOOK if n==1 else Intent.RECOMMEND_BOOKS
    if data.get('result_action'):
        if intent not in {Intent.SEARCH_BOOKS,Intent.RECOMMEND_BOOKS,Intent.RECOMMEND_FROM_BOOK,Intent.RECOMMEND_FROM_SELECTION}:
            raise DecisionInvalid('Result continuation/refinement is only valid for result lists.')
        values['context_operation']='SHOW_MORE' if data['result_action']=='CONTINUE' else 'REFINE_RESULTS'
        if data.get('filters'):values['filters']=data['filters']
    return AssistantIntentDecision.model_validate(values)


async def decide(gateway, message, context, variant='E', retry=False):
    plan=make_plan(context);hierarchical=variant in {'E','E2'}
    schema=strict_family_model(plan) if variant=='E2' else family_model(plan) if hierarchical else flat_model(plan)
    telemetry={'router_variant':variant,'first_pass_valid':False,'retry_used':False,
        'reference_handle':plan.primary,'position':None,'criterion_present':False,
        'invalid_kind':None,'router_ms':0.0,'retry_ms':0.0}
    from time import perf_counter
    from assistant.profiling import current
    decision=None; problem=None
    for attempt in range(2 if retry else 1):
        started=perf_counter()
        raw=await gateway.generate(prompt(message,plan,hierarchical,problem if attempt else None,variant=='E2'),schema,
            'semantic_retry' if attempt else 'intent')
        telemetry['retry_ms' if attempt else 'router_ms']=(perf_counter()-started)*1000
        try:
            try:parsed=schema.model_validate(json.loads(raw))
            except (ValueError,TypeError) as exc:raise DecisionInvalid('Output does not satisfy the decision schema.','SCHEMA_INVALID') from exc
            decision=expand(parsed,plan,message)
            telemetry['first_pass_valid']=not attempt
            telemetry['position']=getattr(parsed,'position',None)
            telemetry['criterion_present']=bool(decision.criterion)
            break
        except DecisionInvalid as exc:
            telemetry['invalid_kind']=exc.kind;problem=exc.reason
            if not attempt and retry:telemetry['retry_used']=True
    if decision is None:
        decision=AssistantIntentDecision(intent=Intent.CLARIFICATION,
            reference_scope=ReferenceScope.AMBIGUOUS,clarification_needed=True,
            clarification_type=ClarificationType.REFERENCE_AMBIGUITY)
    telemetry['intent']=decision.intent.value
    telemetry['goal']=decision.goal.value
    if decision.reference_scope in {ReferenceScope.ACCOUNT,ReferenceScope.AMBIGUOUS} or decision.intent in {
            Intent.SEARCH_BOOKS,Intent.GENERAL_LIBRARY_HELP}:
        telemetry['reference_handle']=None
    elif decision.reference_scope==ReferenceScope.EXPLICIT_BOOK:
        telemetry['reference_handle']='EXPLICIT_ENTITY'
    profile=current.get()
    if profile is not None:profile['router_v2']=telemetry
    return decision,telemetry
