"""Add graph-only fast routes while retaining the original router verbatim."""
from assistant.routing import fast_route as existing_fast_route, FastRouteError
from assistant.schemas import AssistantIntent, Intent
from assistant.contextual import normalize


def fast_route(request):
    phrase = normalize(request.message)
    graph_action = request.action == 'MORE_LIKE_THIS'
    graph_phrase = not request.action and phrase in {'more like this', 'show related books', 'what books are connected to this',
                                                                    'show books connected to this', 'books connected to this', 'find related books'}
    if not (graph_action or graph_phrase):
        return existing_fast_route(request)
    selected = list(dict.fromkeys(request.action_work_ids or request.selected_work_ids))
    page = [request.page_context.work_id] if request.page_context.work_id else list(dict.fromkeys(request.page_context.work_ids))
    targets = selected or page
    if len(targets) != 1:
        raise FastRouteError('Choose exactly one book to find graph-related books.')
    return (AssistantIntent(intent=Intent.MORE_LIKE_THIS, confidence=1),
            request.model_copy(update={'selected_work_ids': targets}))
