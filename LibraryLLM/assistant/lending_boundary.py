"""Explicit library request adapter; never changes semantic routing or retrieval."""
from datetime import datetime, timedelta, timezone
from time import monotonic
from uuid import uuid4
from assistant.schemas import PendingAction, Intent, Action, AssistantAction
from assistant.tools import ToolFailure


async def propose(request, state, tools, response, intent, *, work_id=None, enabled=False):
    context = request.lending_context
    library_id = str(context.library_id); book_id = str(context.library_book_id) if context.library_book_id else None
    loan_id = str(context.loan_id) if context.loan_id else None
    if not book_id and work_id:
        book_id = (await tools.loans.library_resolve(library_id, work_id))['library_book_id']
    if intent == Intent.RETURN_BOOK:
        loans = await tools.loans.library_loans(library_id)
        matches = [l for l in loans if l['status'] == 'ACTIVE' and (l['loan_id'] == loan_id if loan_id else l['library_book_id'] == book_id)]
        if len(matches) != 1 or matches[0].get('pending_return_request_id'):
            raise ToolFailure('core', 'NO_UNIQUE_LOAN', 'Choose your active loan in My Library; an existing pending return cannot be requested again.')
        loan_id = matches[0]['loan_id']; book_id = matches[0]['library_book_id']
    if not book_id:
        raise ToolFailure('core', 'LOCAL_RECORD_REQUIRED', 'Choose the exact book in your library inventory.')
    book = await tools.loans.library_book(library_id, book_id)
    if book.get('library_id') != library_id or book.get('library_book_id') != book_id:
        raise ToolFailure('core', 'TENANT_MISMATCH')
    pending = PendingAction(action_id=uuid4().hex, type=intent, work_id=book.get('global_work_id') or book_id,
        library_id=library_id, library_book_id=book_id, loan_id=loan_id, idempotency_key=uuid4(),
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(), enabled=enabled)
    state.pending = pending; state.pending_deadline = monotonic() + 300
    response.intent = intent; response.pending_action = pending
    response.message = f'Confirm a {"book" if intent == Intent.BORROW_BOOK else "return"} request for {book["title"]} ({book["accession_number"]})? Library staff must approve the physical transition.'
    response.actions = [Action(type=AssistantAction.CONFIRM_ACTION, action_id=pending.action_id), Action(type=AssistantAction.CANCEL_ACTION, action_id=pending.action_id)]
