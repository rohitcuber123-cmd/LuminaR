"""Structured UI action router; natural language belongs to semantic Qwen.

An action establishes an operation, never identity, authorization or catalogue
truth. Existing authoritative tools still resolve every supplied work_id.

Part 3 additions:
- Reading list fast routes (USER_READING_LIST, ADD_TO_READING_LIST,
  REMOVE_FROM_READING_LIST, CLEAR_READING_LIST).
- Available alternatives fast route (RECOMMEND_AVAILABLE_SIMILAR).
- Explain fast routes (EXPLAIN_RECOMMENDATION, EXPLAIN_COMPARISON).
Typed conversation semantics are supplied by the compact context-aware router.
"""
from assistant.schemas import AssistantIntent, Filters, Intent


class FastRouteError(Exception):
    def __init__(self, reason):
        self.reason, self.choices = reason, []


ACTION_INTENTS = {
    'COMPARE': Intent.COMPARE_BOOKS,
    'RECOMMEND': Intent.RECOMMEND_BOOKS,
    'RECOMMEND_SIMILAR': Intent.RECOMMEND_FROM_BOOK,
    'RECOMMEND_FROM_SELECTION': Intent.RECOMMEND_FROM_SELECTION,
    'CHECK_AVAILABILITY': Intent.CHECK_AVAILABILITY,
    'AVAILABLE_NOW': Intent.SEARCH_BOOKS,
    'USER_LOANS': Intent.USER_LOANS,
    'USER_FEES': Intent.USER_FEES,
    'USER_RESERVATIONS': Intent.USER_RESERVATIONS,
    'BOOK_CONTENT_QUESTION': Intent.BOOK_CONTENT_QUESTION,
    'DOCUMENT_QUESTION': Intent.DOCUMENT_QUESTION,
    # Part 3 reading list
    'USER_READING_LIST': Intent.USER_READING_LIST,
    'ADD_TO_READING_LIST': Intent.ADD_TO_READING_LIST,
    'REMOVE_FROM_READING_LIST': Intent.REMOVE_FROM_READING_LIST,
    'CLEAR_READING_LIST': Intent.CLEAR_READING_LIST,
    # Part 3 available alternatives
    'RECOMMEND_AVAILABLE_SIMILAR': Intent.RECOMMEND_AVAILABLE_SIMILAR,
}


def fast_route(request):
    if request.action_work_ids:
        request = request.model_copy(update={'selected_work_ids': list(dict.fromkeys(request.action_work_ids))})
    selected = list(dict.fromkeys(request.selected_work_ids))
    page = ([request.page_context.work_id] if request.page_context.work_id
            else list(dict.fromkeys(request.page_context.work_ids)))
    action = request.action
    if action:
        # Explain actions are handled specially — they are allowed to go through
        # the normal Qwen path but we still bypass structured routing.
        if action in ('EXPLAIN_RECOMMENDATION', 'EXPLAIN_COMPARISON'):
            return None  # Falls through to Qwen.respond path

        if action not in ACTION_INTENTS:
            # Confirm/cancel handled upstream
            return None

        intent = ACTION_INTENTS[action]
        count = len(selected)
        valid = {'COMPARE': 2 <= count <= 4, 'RECOMMEND': count == 0,
            'RECOMMEND_SIMILAR': count == 1, 'RECOMMEND_FROM_SELECTION': 2 <= count <= 4}
        if action in valid and not valid[action]:
            raise FastRouteError('Select the required number of books for this action.')
        if action in {'CHECK_AVAILABILITY', 'BOOK_CONTENT_QUESTION'}:
            targets = selected or page
            if len(targets) != 1:
                raise FastRouteError('Select one book for this action.')
            # Bind the explicitly selected/page target ahead of prior result context.
            request = request.model_copy(update={'selected_work_ids': targets})
        if action == 'DOCUMENT_QUESTION' and not request.page_context.document_id:
            raise FastRouteError('Provide the uploaded document_id in page_context.')
        if action in {'ADD_TO_READING_LIST', 'REMOVE_FROM_READING_LIST'}:
            targets = selected or page
            if len(targets) < 1:
                raise FastRouteError('Select at least one book for this action.')
            request = request.model_copy(update={'selected_work_ids': targets})
        if action == 'RECOMMEND_AVAILABLE_SIMILAR':
            targets = selected or page
            if len(targets) != 1:
                raise FastRouteError('Select one book to find available alternatives.')
            request = request.model_copy(update={'selected_work_ids': targets})
        parsed = AssistantIntent(intent=intent, confidence=1)
        if action == 'AVAILABLE_NOW':
            parsed = parsed.model_copy(update={'query': 'books', 'filters': Filters(available_only=True)})
        return parsed, request

    # Every typed natural-language request enters the semantic router.
    return None


def needs_prose(request, intent, parsed=None):
    """Structured facts render deterministically; prose is opt-in or help."""
    return intent == Intent.GENERAL_LIBRARY_HELP or request.action in {
        'EXPLAIN_RECOMMENDATION', 'EXPLAIN_COMPARISON'}
