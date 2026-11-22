"""A model circulation label does not turn a question into consent."""
import pytest
from backend.database.mongodb import db
from assistant.schemas import AssistantIntentDecision, Intent, ReferenceScope
from tests.institution_v2q_ai.test_integration import fixture, chat


class BorrowParser:
    async def parse(self, message, context):
        return AssistantIntentDecision(intent=Intent.BORROW_BOOK, confidence=1,
            reference_scope=ReferenceScope.CURRENT_PAGE_BOOK, reference_position='ALL')
    async def respond(self, *args):
        return 'Controlled explanation.'


@pytest.mark.parametrize('message', ['Can I borrow this?', 'Is this available to borrow?',
    'Which one can I borrow physically?', "Don't borrow it, just tell me whether it is available."])
def test_information_never_proposes_loan(client, fixture, message):
    api, libs, books, _ = fixture
    api.app.state.assistant.qwen = BorrowParser()
    response = chat(fixture, libs[0], message=message, page_context={'work_id': books[0]}).json()
    assert response['intent'] == 'CHECK_AVAILABILITY', response
    assert response['pending_action'] is None and response['availability']
    assert response['books'][0]['work_id'] == books[0]


def test_explicit_borrow_keeps_confirmation(client, fixture):
    api, libs, books, _ = fixture
    api.app.state.assistant.qwen = BorrowParser()
    response = chat(fixture, libs[0], message='Borrow this for me.', page_context={'work_id': books[0]}).json()
    assert response['pending_action'] is not None, response


def test_digital_question_retains_authoritative_unknown(client, fixture):
    api, libs, books, _ = fixture
    api.app.state.assistant.qwen = BorrowParser()
    response = chat(fixture, libs[0], message='Can I read it digitally instead?', page_context={'work_id': books[0]}).json()
    assert response['pending_action'] is None
    assert response['digital_availability'][0]['status'] == 'UNKNOWN'


@pytest.mark.parametrize('scope', [ReferenceScope.CURRENT_PAGE_BOOK, ReferenceScope.RECENT_RESULTS])
def test_local_page_followup_uses_verified_lending_record(fixture, scope):
    class FollowupParser(BorrowParser):
        async def parse(self, message, context):
            decision = await super().parse(message, context)
            if message.startswith('Borrow'):
                return decision.model_copy(update={'reference_scope': scope})
            return decision

    api, libs, books, calls = fixture
    api.app.state.assistant.qwen = FollowupParser()
    context = {'page_context': {'work_id': books[0]}, 'lending_context': {'library_id': libs[0]}}
    info = chat(fixture, libs[0], message='Can I borrow this book?', **context).json()
    assert info['pending_action'] is None and info['availability']
    proposal = chat(fixture, libs[0], message='Borrow this book for me.',
                    conversation_id=info['conversation_id'], recent_work_ids=[books[0]], **context).json()
    pending = proposal['pending_action']
    assert pending and pending['library_book_id'] == books[0], proposal
    assert f'/libraries/{libs[0]}/lending/resolve' not in calls
    assert chat(fixture, libs[1], conversation_id=info['conversation_id'], action='CONFIRM_ACTION',
                pending_action_id=pending['action_id']).status_code == 404
    cancelled = chat(fixture, libs[0], conversation_id=info['conversation_id'], action='CANCEL_ACTION',
                     pending_action_id=pending['action_id'])
    assert cancelled.status_code == 200 and not cancelled.json()['errors']
    assert db.institution_lending_requests.count_documents({}) == 0
    assert db.institution_loans.count_documents({}) == 0


def test_resolved_page_cannot_propose_for_conflicting_record(fixture):
    api, libs, books, _ = fixture
    api.app.state.assistant.qwen = BorrowParser()
    response = chat(fixture, libs[0], message='Borrow this book for me.', page_context={'work_id': books[0]},
                    lending_context={'library_id': libs[0], 'library_book_id': books[1]}).json()
    assert response['pending_action'] is None and response['clarification']


def test_keep_duration_question_cannot_propose_borrowing(fixture):
    api, libs, books, _ = fixture
    api.app.state.assistant.qwen = BorrowParser()
    response = chat(fixture, libs[0], message='How long can I keep this book?',
                    page_context={'work_id': books[0]}, lending_context={'library_id': libs[0]}).json()
    assert response['pending_action'] is None
    assert 'cannot verify' in response['message']
