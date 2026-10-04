"""Authoritative compact context and bounded semantic reference binding.

No natural-language intent grammar. Qwen interprets language once; this module
only validates its structured decision against current canonical context.
"""
import re

from assistant.schemas import AssistantIntentDecision, ReferenceScope, Intent, SemanticGoal


def unique(ids):
    return list(dict.fromkeys(ids))


def literal_ids(message):
    return set(re.findall(r'\b[A-Za-z0-9_-]+\b', message))


def reference_sources(request, state):
    selected = unique(request.selected_work_ids)
    page = unique(([request.page_context.work_id] if request.page_context.work_id else [])
                  + request.page_context.work_ids)
    active = state.active_result_work_ids
    recent = active if active is not None else state.recent_result_work_ids or request.recent_work_ids
    return {
        ReferenceScope.SELECTED_BOOKS: selected,
        ReferenceScope.CURRENT_PAGE_BOOK: page,
        ReferenceScope.PREVIOUS_COMPARISON: list(state.last_comparison_work_ids),
        ReferenceScope.PREVIOUS_RECOMMENDATIONS: list(state.last_recommendation_work_ids),
        ReferenceScope.RECENT_RESULTS: unique(recent),
    }


async def router_context(request, state, tools):
    sources = reference_sources(request, state)
    selected = sources[ReferenceScope.SELECTED_BOOKS]
    page = sources[ReferenceScope.CURRENT_PAGE_BOOK]
    active_ids = sources[ReferenceScope.RECENT_RESULTS][:20]
    # Metadata is only identity-level and bounded; no descriptions or chunks.
    identities = unique(selected + page + state.last_comparison_work_ids[:4]
                        + state.last_referenced_work_ids[:4] + active_ids[:4])[:16]
    books = await tools.catalogue.books(identities) if identities else []
    index = {b.work_id: {'work_id': b.work_id, 'title': b.title, 'authors': b.authors} for b in books}
    brief = lambda ids: [index.get(wid, {'work_id': wid}) for wid in ids]
    changed = bool(selected and selected != state.selected_work_ids)
    focus = [wid for wid in state.last_referenced_work_ids if not changed or wid in selected]
    result_type = state.last_result_type
    if state.result_context and result_type not in ('comparison', 'details', 'availability'):
        result_type = 'search' if state.result_context.intent == Intent.SEARCH_BOOKS else 'recommendations'
    context = {
        'selected_books': brief(selected), 'selection_changed': changed,
        'page_books': brief(page), 'document_id': request.page_context.document_id,
        'previous_turns': state.semantic_turns[-2:],
        'last_intent': state.last_intent,
        'last_referenced_work_ids': focus,
        'previous_comparison': brief(state.last_comparison_work_ids[:4]),
        'previous_recommendations': {'work_ids': state.last_recommendation_work_ids[:20],
                                     'seed_work_ids': state.last_recommendation_seed_work_ids[:4]},
        'active_result_context': {'type': result_type, 'books': brief(active_ids[:4]),
            'work_ids': active_ids, 'has_more': bool(state.result_context and state.result_context.has_more),
            'query': state.result_context.query if state.result_context else None,
            'filters': state.result_context.filters.model_dump(exclude_defaults=True) if state.result_context else {}},
        'awaiting_criteria': state.awaiting_criteria and not changed,
    }
    # Keep context compact: absent sources and empty default facts add no meaning.
    context = {key: value for key, value in context.items() if value not in (None, [], False)}
    if not state.last_recommendation_work_ids:
        context.pop('previous_recommendations', None)
    if not active_ids and state.active_result_work_ids is None:
        context.pop('active_result_context', None)
    return context


def bind_position(pool, position, last_focus):
    if position in {'FIRST','SECOND','LAST'}:
        index = {'FIRST':0,'SECOND':1,'LAST':len(pool)-1}[position]
        if index < 0 or index >= len(pool):
            raise ValueError('That position is not in the current book list.')
        return [pool[index]]
    if position in {'OTHER','FOCUS'}:
        focus = [wid for wid in last_focus if wid in pool]
        if position == 'FOCUS' and len(pool) == 1:
            return list(pool)
        if len(focus) != 1 or (position == 'OTHER' and len(pool) != 2):
            raise ValueError('Which book are you referring to?')
        return focus if position == 'FOCUS' else [wid for wid in pool if wid not in focus]
    return unique(pool)


def contextual_ids(request, decision, state):
    """Honor exact structured scope/ordinals. Never interpret prose as a title.

    Return None only for genuine named-entity resolution. Unknown model IDs
    are rejected; callers must clarify, never silently search for them.
    """
    sources = reference_sources(request, state)
    if request.action_work_ids:
        return unique(request.action_work_ids)
    scope = decision.reference_scope
    literal = literal_ids(request.message)
    ids = unique(decision.resolved_work_ids)
    if scope == ReferenceScope.EXPLICIT_BOOK:
        if ids:
            allowed = set().union(*[set(v) for v in sources.values()]) | literal
            if not set(ids) <= allowed:
                raise ValueError('The referenced book is not in the supplied context.')
            return ids
        return None
    if ids and set(ids) <= literal:
        return ids
    if scope in {ReferenceScope.ACCOUNT, ReferenceScope.AMBIGUOUS}:
        return []
    pool = sources.get(scope, [])
    # Selection wins over stale contexts, while a resolved subset is retained
    # for a safe ordinal or focus reference within the current selection.
    if sources[ReferenceScope.SELECTED_BOOKS] and scope in {
            ReferenceScope.PREVIOUS_COMPARISON, ReferenceScope.PREVIOUS_RECOMMENDATIONS,
            ReferenceScope.RECENT_RESULTS, ReferenceScope.CURRENT_PAGE_BOOK}:
        pool = sources[ReferenceScope.SELECTED_BOOKS]
    if not pool and scope == ReferenceScope.NONE:
        if state.active_result_work_ids == [] and not sources[ReferenceScope.SELECTED_BOOKS] and not request.page_context.work_id:
            return []
        if decision.reference == 'previous_recommendation':
            pool = sources[ReferenceScope.PREVIOUS_RECOMMENDATIONS]
        elif decision.reference != 'none' or sources[ReferenceScope.SELECTED_BOOKS] or decision.intent not in {
                Intent.RECOMMEND_BOOKS, Intent.SEARCH_BOOKS, Intent.GENERAL_LIBRARY_HELP}:
            pool = (sources[ReferenceScope.SELECTED_BOOKS]
                    or sources[ReferenceScope.RECENT_RESULTS]
                    or sources[ReferenceScope.CURRENT_PAGE_BOOK]
                    or state.last_referenced_work_ids)
    # A pending reading-goal answer continues the known comparison. A
    # preference comparison is relational; one positional output cannot
    # silently discard the other member of the established pair.
    if (state.awaiting_criteria and decision.intent == Intent.COMPARE_BOOKS
            and decision.goal == SemanticGoal.PREFERENCE_COMPARE and decision.criterion
            and len(pool) >= 2):
        return unique(pool)
    if ids:
        if not set(ids) <= set(pool):
            raise ValueError('The referenced book is not in the current book context.')
        return ids
    if decision.reference_position:
        return bind_position(pool, decision.reference_position, state.last_referenced_work_ids)
    if decision.ordinal_references:
        if any(n < 1 or n > len(pool) for n in decision.ordinal_references):
            raise ValueError('That result number is not in the current book list.')
        return unique([pool[n-1] for n in decision.ordinal_references])
    return unique(pool)


def as_decision(parsed):
    return (parsed if isinstance(parsed, AssistantIntentDecision)
            else AssistantIntentDecision.model_validate({**parsed.model_dump(),
                **({'reference_scope': ReferenceScope.EXPLICIT_BOOK} if parsed.mentioned_titles or parsed.mentioned_authors else {})}))
