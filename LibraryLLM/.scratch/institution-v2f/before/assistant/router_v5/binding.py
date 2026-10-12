"""Request-local authority selects identities before semantic action scoring."""
from dataclasses import dataclass
from assistant.schemas import AssistantIntentDecision, ClarificationType, Intent, ReferenceScope, SemanticGoal
from assistant.semantic import bind_position, literal_ids, unique
from .contracts import CONTRACTS, BY_ID


@dataclass(frozen=True)
class Plan:
    source: ReferenceScope
    ids: tuple[str, ...]
    focus: tuple[str, ...]
    public_books: tuple[dict, ...]
    literal: bool
    document: bool
    book_access: bool
    authenticated: bool
    awaiting: bool
    last_intent: str | None
    results: bool
    redacted_tokens: tuple[str, ...]


def _literal_title(title, message):
    title = str(title or '').strip().casefold()
    if len(title) < 4:
        return False
    message = message.casefold()
    start = message.find(title)
    if start < 0:
        return False
    end = start + len(title)
    return (start == 0 or not message[start-1].isalnum()) and (end == len(message) or not message[end].isalnum())


def make_plan(context, message=''):
    selected = context.get('selected_books', [])
    previous = context.get('previous_comparison', [])
    page = context.get('page_books', [])
    active = context.get('active_result_context', {})
    active_ids = unique(active.get('work_ids', []))
    recommendation = context.get('previous_recommendations', {})
    recent = unique(context.get('last_referenced_work_ids', []))
    known = selected + previous + page + active.get('books', [])
    index = {b['work_id']: b for b in known}
    explicit_args = unique(context.get('structured_action_work_ids', []))
    literal = literal_ids(message)
    exact = unique([w for w in index if w in literal] + [b['work_id'] for b in known if _literal_title(b.get('title'), message)])
    # A canonical ID is a structured literal, never inferred from prose.
    exact += [s for s in literal if s.startswith('OL') and s[-1:] in {'W', 'M'} and s[2:-1].isdigit() and s not in exact]
    prior_ids = unique(b['work_id'] for b in previous)
    source, ids = ReferenceScope.AMBIGUOUS, []
    if explicit_args:
        source, ids = ReferenceScope.EXPLICIT_BOOK, explicit_args
    elif exact:
        source, ids = ReferenceScope.EXPLICIT_BOOK, exact
    elif selected:
        source, ids = ReferenceScope.SELECTED_BOOKS, unique(b['work_id'] for b in selected)
    elif prior_ids and ((active.get('type') == 'comparison' and active_ids) or
                        ('active_result_context' not in context) or
                        (active_ids and active.get('type') in {'details', 'availability'} and set(active_ids) <= set(prior_ids))):
        source, ids = ReferenceScope.PREVIOUS_COMPARISON, prior_ids
    elif active.get('type') == 'recommendations' and active_ids:
        source, ids = ReferenceScope.PREVIOUS_RECOMMENDATIONS, active_ids[:4]
    elif 'active_result_context' not in context and recommendation.get('work_ids'):
        source, ids = ReferenceScope.PREVIOUS_RECOMMENDATIONS, unique(recommendation['work_ids'])[:4]
    elif page:
        source, ids = ReferenceScope.CURRENT_PAGE_BOOK, unique(b['work_id'] for b in page)
    elif active_ids:
        source, ids = ReferenceScope.RECENT_RESULTS, active_ids[:4]
    elif 'active_result_context' not in context and recent:
        source, ids = ReferenceScope.RECENT_RESULTS, recent[:4]
    # Explicit empty active results never revive stale previous/focus state.
    focus = tuple(w for w in recent if w in ids and not context.get('selection_changed'))
    books = tuple({'position': i+1, 'title': str(index.get(w, {}).get('title') or '')[:80]}
                  for i, w in enumerate(ids[:4]))
    hidden = tuple(unique([*index,*active_ids,*recent,*explicit_args,*exact,
                          *[s for s in literal if s.startswith('OL')],
                          *([context['document_id']] if context.get('document_id') else [])]))
    return Plan(source, tuple(ids[:4]), focus, books, bool(explicit_args or exact),
                bool(context.get('document_id')), bool(context.get('book_rag_context')),
                bool(context.get('authenticated', True)), bool(context.get('awaiting_criteria')),
                getattr(context['last_intent'],'value',str(context['last_intent'])) if context.get('last_intent') else None,
                bool(active.get('type') in {'search', 'recommendations'} and active.get('has_more')),hidden)


def eligible(plan):
    result = []
    for c in CONTRACTS:
        if c.context == 'authenticated' and not plan.authenticated:
            continue
        if c.context == 'book_access' and not plan.book_access:
            continue
        if c.context == 'document' and not plan.document:
            continue
        if c.context == 'results' and not plan.results:
            continue
        if c.context == 'pair' and len(plan.ids) == 1:
            continue
        if c.id == 'RECOMMEND_FROM_SELECTION' and len(plan.ids) < 2:
            continue
        # Unknown explicit titles need extraction; retain book contracts in an
        # empty context so the router can request identification, not Search.
        result.append(c.id)
    return result


def model_payload(message, plan):
    sanitized = message
    for w in sorted(plan.redacted_tokens,key=len,reverse=True):
        sanitized = sanitized.replace(w, '[source identifier]')
    last_meaning = next((c.meaning for c in CONTRACTS if c.intent == plan.last_intent and not c.mutation), '')
    return {'message': sanitized[:4000], 'count': len(plan.ids), 'focus_positions': [plan.ids.index(w)+1 for w in plan.focus],
            'last_meaning': last_meaning, 'awaiting_criteria': plan.awaiting,
            'eligible': eligible(plan), 'literal': plan.literal}


async def enrich_context(context,request,tools):
    """Server-side permission capability only; private records never reach scoring."""
    if request.action_work_ids:
        context['structured_action_work_ids']=list(request.action_work_ids)
    plan=make_plan(context,request.message)
    context['authenticated']=True
    if plan.ids and hasattr(tools,'transport'):
        from assistant.tools import ToolFailure
        try:
            result=await tools.transport.call('core','GET','/know-more/books')
            permitted={row['work_id'] for row in result.get('books',[]) if row.get('work_id')}
            context['book_rag_context']=bool(set(plan.ids)&permitted)
        except ToolFailure:
            context['book_rag_context']=False
    return context


def clarify(kind=ClarificationType.REFERENCE_AMBIGUITY):
    return AssistantIntentDecision(intent=Intent.CLARIFICATION, confidence=1, reference_scope=ReferenceScope.AMBIGUOUS,
                                   clarification_needed=True, clarification_type=kind)


def decision(contract_id, plan, message, position='ALL', field=None, criterion=None, titles=()):
    c = BY_ID.get(contract_id)
    if c is None or c.id == 'UNSUPPORTED':
        return AssistantIntentDecision(intent=Intent.UNKNOWN, confidence=1)
    if c.id == 'MISSING_REFERENCE':
        return clarify()
    if c.context == 'authenticated' and not plan.authenticated or c.context == 'document' and not plan.document or c.context == 'book_access' and not plan.book_access:
        return clarify()
    common = {'intent': Intent(c.intent), 'confidence': 1, 'goal': SemanticGoal(c.goal), 'requires_confirmation': c.mutation}
    if c.context == 'authenticated':
        return AssistantIntentDecision(**common, reference_scope=ReferenceScope.ACCOUNT)
    if c.id == 'CATALOGUE_TOPIC_SEARCH':
        if len(message) > 2000:
            return clarify()
        return AssistantIntentDecision(**common, query=message, reference_scope=ReferenceScope.NONE)
    if c.id in {'PERSONALIZED_RECOMMEND', 'GENERAL_LIBRARY_HELP', 'DOCUMENT_QUESTION'}:
        return AssistantIntentDecision(**common, reference_scope=ReferenceScope.NONE)
    if c.id in {'CONTINUE_RESULTS', 'REFINE_RESULTS'}:
        if not plan.results:
            return clarify()
        return AssistantIntentDecision(**common, context_operation='SHOW_MORE' if c.id == 'CONTINUE_RESULTS' else 'REFINE_RESULTS')
    if titles and not plan.literal:
        valid = [t for t in titles if t and t.casefold() in message.casefold()]
        if not valid or len(valid) != len(titles):
            return clarify()
        return AssistantIntentDecision(**common, mentioned_titles=valid, reference_scope=ReferenceScope.EXPLICIT_BOOK,
                                       comparison_fields=[field] if field else [], criterion=criterion)
    if not plan.ids:
        return clarify()
    if c.context == 'pair':
        if len(plan.ids) < 2:
            return clarify(ClarificationType.INSUFFICIENT_SELECTION)
        position = 'ALL'
    try:
        bound = bind_position(list(plan.ids), position, list(plan.focus))
    except ValueError:
        return clarify()
    if c.id in {'MORE_LIKE_THIS', 'AVAILABLE_ALTERNATIVES', 'BOOK_DETAILS', 'RECOMMEND_FROM_ONE', 'BOOK_CONTENT_QUESTION',
                'BORROW', 'RETURN', 'RESERVE', 'ADD_READING_LIST', 'REMOVE_READING_LIST'} and len(bound) != 1:
        return clarify()
    if c.id == 'COMPARE_FIELD' and not field:
        return clarify(ClarificationType.CRITERIA_AMBIGUITY)
    pref = c.id == 'COMPARE_PREFERENCE'
    return AssistantIntentDecision(**common, resolved_work_ids=bound, reference_scope=plan.source,
        reference_position=position, comparison_fields=[field] if c.id == 'COMPARE_FIELD' else [],
        criterion=criterion if pref else None, clarification_needed=pref and not criterion,
        clarification_type=ClarificationType.CRITERIA_AMBIGUITY if pref and not criterion else None)
