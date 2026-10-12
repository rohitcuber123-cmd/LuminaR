"""Explicit tenant reservation proposals; model routing remains frozen."""
from datetime import datetime, timedelta, timezone
from time import monotonic
from uuid import uuid4
from assistant.schemas import PendingAction, Intent, Action, AssistantAction
from assistant.tools import ToolFailure


async def propose(request, state, tools, response, *, enabled=False, cancel=False, work_id=None):
    context = request.lending_context; library_id = str(context.library_id)
    book_id = str(context.library_book_id) if context.library_book_id else None
    reservation_id = str(context.reservation_id) if context.reservation_id else None
    if cancel:
        rows = await tools.reservations.library_reservations(library_id)
        matches = [r for r in rows if r['reservation_id'] == reservation_id and r['status'] == 'WAITING']
        if len(matches) != 1:
            raise ToolFailure('core', 'NO_WAITING_RESERVATION', 'Choose your waiting reservation in My Library.')
        book_id = matches[0]['library_book_id']
    elif not book_id and work_id:
        book_id = (await tools.loans.library_resolve(library_id, work_id))['library_book_id']
    if not book_id:
        raise ToolFailure('core', 'LOCAL_RECORD_REQUIRED', 'Choose the exact book in your library inventory.')
    book = await tools.loans.library_book(library_id, book_id)
    if book.get('library_id') != library_id or book.get('library_book_id') != book_id:
        raise ToolFailure('core', 'TENANT_MISMATCH')
    # Authoritative eligibility is rechecked at confirmed execution by Core.
    status = await tools.reservations.library_status(library_id, book_id)
    if status.get('state') != 'CANONICAL':
        raise ToolFailure('core', 'CANONICAL_QUEUE_REQUIRED', 'Library staff must enable canonical reservations first.')
    pending = PendingAction(action_id=uuid4().hex, type=Intent.RESERVE_BOOK, work_id=book.get('global_work_id') or book_id,
        library_id=library_id, library_book_id=book_id, reservation_id=reservation_id if cancel else None,
        idempotency_key=uuid4(), expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(), enabled=enabled)
    state.pending = pending; state.pending_deadline = monotonic() + 300
    response.intent = Intent.RESERVE_BOOK; response.pending_action = pending
    response.message = f'Confirm {"cancelling your waiting reservation" if cancel else "joining the waiting queue"} for {book["title"]} ({book["accession_number"]}) in this library?'
    response.actions = [Action(type=AssistantAction.CONFIRM_ACTION, action_id=pending.action_id), Action(type=AssistantAction.CANCEL_ACTION, action_id=pending.action_id)]
