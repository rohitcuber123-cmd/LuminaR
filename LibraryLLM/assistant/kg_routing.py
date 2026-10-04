"""Graph button routing; typed graph intent is handled by the semantic router."""
from assistant.routing import fast_route as existing_fast_route, FastRouteError
from assistant.schemas import AssistantIntent, Intent


def fast_route(request):
    if request.action != 'MORE_LIKE_THIS':
        return existing_fast_route(request)
    selected = list(dict.fromkeys(request.action_work_ids or request.selected_work_ids))
    page = [request.page_context.work_id] if request.page_context.work_id else list(dict.fromkeys(request.page_context.work_ids))
    targets = selected or page
    if len(targets) != 1:
        raise FastRouteError('Choose exactly one book to find graph-related books.')
    return (AssistantIntent(intent=Intent.MORE_LIKE_THIS, confidence=1),
            request.model_copy(update={'selected_work_ids': targets}))
