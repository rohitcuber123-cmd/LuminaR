"""Small exact-message router and validated read-only action hints.

An action establishes an operation, never identity, authorization or catalogue
truth. Existing authoritative tools still resolve every supplied work_id.

Part 3 additions:
- Reading list fast routes (USER_READING_LIST, ADD_TO_READING_LIST,
  REMOVE_FROM_READING_LIST, CLEAR_READING_LIST).
- Available alternatives fast route (RECOMMEND_AVAILABLE_SIMILAR).
- Explain fast routes (EXPLAIN_RECOMMENDATION, EXPLAIN_COMPARISON).
- Phase 16: stale-context general-help fix: conceptual questions that look
  like GENERAL_LIBRARY_HELP should not be overridden by stale prior SEARCH
  intent.
"""
import re

from assistant.schemas import AssistantIntent, Filters, Intent
from assistant.contextual import normalize, selected_command, reference_kind


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

    phrase = normalize(request.message)
    contextual = selected_command(request.message)
    if contextual:
        operation, fields = contextual
        kind = reference_kind(request.message)
        if kind == 'two' and selected and len(selected) != 2:
            raise FastRouteError(f'You have {len(selected)} books selected. Which two do you mean?')
        if kind == 'singular' and len(selected) > 1:
            raise FastRouteError('You have multiple books selected. Choose the one you mean.')
        targets = selected or page
        if kind == 'two' and targets and len(targets) != 2:
            raise FastRouteError(f'The current context contains {len(targets)} books. Which two do you mean?')
        if operation == 'compare':
            if len(targets) == 1:
                raise FastRouteError('Select at least one more book to compare.')
            if len(targets) > 4:
                raise FastRouteError('Select two to four books to compare.')
            if not targets:
                # Retained canonical results may satisfy a plural reference.
                return AssistantIntent(intent=Intent.COMPARE_BOOKS, confidence=1, reference='these', comparison_fields=fields), request
        elif not targets:
            return AssistantIntent(intent={'recommend': Intent.RECOMMEND_BOOKS, 'availability': Intent.CHECK_AVAILABILITY, 'details': Intent.BOOK_DETAILS}[operation], confidence=1, reference='this' if kind == 'singular' else 'these'), request
        if operation == 'details' and len(targets) != 1:
            raise FastRouteError('Choose one book for catalogue details.')
        parsed = AssistantIntent(intent={'compare': Intent.COMPARE_BOOKS, 'recommend': Intent.RECOMMEND_BOOKS,
            'availability': Intent.CHECK_AVAILABILITY, 'details': Intent.BOOK_DETAILS}[operation], confidence=1,
            reference='this' if kind == 'singular' else 'these', comparison_fields=fields)
        return parsed, request.model_copy(update={'selected_work_ids': targets})
    # Exact closed set: qualifiers, quantities and mixed requests fall through.
    if phrase in {'recommend', 'recommend something', 'recommend me something'}:
        return AssistantIntent(intent=Intent.RECOMMEND_BOOKS, confidence=1), request
    accounts = {'show my loans': Intent.USER_LOANS,
        'what books do i have borrowed': Intent.USER_LOANS,
        'what books do i have': Intent.USER_LOANS,
        'which one is due first': Intent.USER_LOANS,
        'which book is due first': Intent.USER_LOANS,
        'sort my loans by due date': Intent.USER_LOANS,
        'do i have fines': Intent.USER_FEES, 'show my fines': Intent.USER_FEES,
        'show my fees': Intent.USER_FEES,
        'what do i owe': Intent.USER_FEES, 'do i owe anything': Intent.USER_FEES,
        'show my reservations': Intent.USER_RESERVATIONS,
        'what are my reservations': Intent.USER_RESERVATIONS,
        'my reservations': Intent.USER_RESERVATIONS,
        'my loans': Intent.USER_LOANS,
        'show my history': Intent.USER_HISTORY,
        'my borrowing history': Intent.USER_HISTORY,
        'show my borrowing history': Intent.USER_HISTORY,
        # Reading list phrases
        'show my reading list': Intent.USER_READING_LIST,
        'my reading list': Intent.USER_READING_LIST,
        'what is on my reading list': Intent.USER_READING_LIST,
        "what's on my reading list": Intent.USER_READING_LIST,
        'clear my reading list': Intent.CLEAR_READING_LIST,
        'empty my reading list': Intent.CLEAR_READING_LIST,
    }
    if phrase in accounts:
        return AssistantIntent(intent=accounts[phrase], confidence=1), request
    # An explicit current source outranks a prior search or conceptual wording.
    if request.page_context.document_id and re.search(
            r'\b(?:this|the)\s+(?:pdf|document)\b|\bdocument content\b', phrase):
        return AssistantIntent(intent=Intent.DOCUMENT_QUESTION, confidence=1), request
    if phrase in {'compare these', 'compare these two'} and 2 <= len(selected) <= 4:
        return AssistantIntent(intent=Intent.COMPARE_BOOKS, confidence=1), request
    targets = selected or page
    # These exact proposal phrases establish intent only. The entity resolver,
    # fresh Core facts, owner-scoped pending action and explicit confirmation
    # still govern execution. No direct mutation tool is called here.
    proposal = re.fullmatch(r'(borrow|reserve|return) this(?: book)?', phrase)
    if proposal and len(targets) == 1:
        intent = {'borrow': Intent.BORROW_BOOK, 'reserve': Intent.RESERVE_BOOK,
                  'return': Intent.RETURN_BOOK}[proposal.group(1)]
        return (AssistantIntent(intent=intent, confidence=1, requires_confirmation=True),
                request.model_copy(update={'selected_work_ids': targets}))
    if (len(targets) == 1
            and re.search(r'\b(?:this|the selected)\s+(?:selected\s+)?book\b', phrase)
            and re.match(r'^(?:who|what|why|how|where|when|summari[sz]e|according to)\b', phrase)
            and not re.search(r'\b(?:available|copies|borrow|reserve|return|recommend|similar|compare|fees?|loans?)\b', phrase)):
        return (AssistantIntent(intent=Intent.BOOK_CONTENT_QUESTION, confidence=1),
                request.model_copy(update={'selected_work_ids': targets}))
    if phrase in {'is this available', 'is this book available'} and len(targets) == 1:
        return (AssistantIntent(intent=Intent.CHECK_AVAILABILITY, confidence=1),
                request.model_copy(update={'selected_work_ids': targets}))
    # Available alternatives exact phrases
    avail_alt = {
        'show available alternatives', 'give me available alternatives',
        'anything like this available', 'anything like this that is available',
        'show something similar that i can borrow',
        'show something similar i can borrow now',
    }
    if phrase in avail_alt and len(targets) == 1:
        return (AssistantIntent(intent=Intent.RECOMMEND_AVAILABLE_SIMILAR, confidence=1),
                request.model_copy(update={'selected_work_ids': targets}))
    # Reading list — add
    rl_add = re.fullmatch(
        r'add (?:this|these)(?:\s+(?:book|books|one|ones|three|to))?\s*(?:to my reading list)?'
        r'|add (?:to|this to) my reading list',
        phrase)
    if rl_add and targets:
        return (AssistantIntent(intent=Intent.ADD_TO_READING_LIST, confidence=1),
                request.model_copy(update={'selected_work_ids': targets}))
    search = simple_search(request.message)
    if search:
        return search, request
    if (not selected and not request.page_context.work_id and not request.page_context.document_id
            and looks_like_general_concept(request.message)):
        return AssistantIntent(intent=Intent.GENERAL_LIBRARY_HELP, confidence=1), request
    return None


def simple_search(message):
    """Only explicit catalogue grammar; qualifications fall through to Qwen."""
    phrase = ' '.join(message.strip().split()).rstrip('.!?')
    phrase = re.sub(r'^show me\b', 'show', phrase, flags=re.I)
    phrase = re.sub(r'^books on\b', 'find books on', phrase, flags=re.I)
    match = re.fullmatch(
        r'(?:please\s+)?(?:find|show|search(?:\s+for)?)\s+'
        r'(?:books?\s+(?:about|on)\s+(.+?)|(.+?)\s+books?)', phrase, re.I)
    if not match:
        return None
    topic = match.group(1) or match.group(2)
    available = bool(re.search(r'\s+available (?:now|today)$', topic, re.I))
    if available:
        topic = re.sub(r'\s+available (?:now|today)$', '', topic, flags=re.I)
    author = None
    parts = re.fullmatch(r'(.+?)\s+by\s+([\w .\'-]{2,100})', topic, re.I)
    if parts:
        topic, author = parts.groups()
    # A bounded noun phrase has no comparative, personal, temporal, numerical,
    # source-reference, unsupported metadata or compound operation constraints.
    if (not re.fullmatch(r'[\w -]{2,120}', topic) or len(topic.split()) > 8
            # Short acronyms can denote different topics. Retain semantic
            # extraction for them rather than guessing an expansion.
            or re.search(r'\b[A-Z]{2,4}\b', topic)
            or re.search(r'\d', topic + (author or ''))
            or re.search(r'\b(?:and|or|but|not|without|with|like|similar|more|less|different|same|'
                         r'available|author|by|under|over|before|after|pages?|year|published|language|'
                         r'shorter|longer|beginner|accessible|easy|difficulty|math|sorted|sort|'
                         r'this|these|my|selected|pdf|document|borrow|reserve|return|compare)\b',
                         topic + ' ' + (author or ''), re.I)):
        return None
    return AssistantIntent(intent=Intent.SEARCH_BOOKS, confidence=1, query=topic,
                           filters=Filters(available_only=available, author=author))


def needs_prose(request, intent, parsed=None):
    if intent == Intent.GENERAL_LIBRARY_HELP:
        return True
    if request.action:
        if request.action in ('EXPLAIN_RECOMMENDATION', 'EXPLAIN_COMPARISON'):
            return True  # Explicit explanation is intentionally Qwen-backed.
        return False  # Current action set requests structured facts, never synthesis.
    if intent in {Intent.COMPARE_BOOKS, Intent.RECOMMEND_BOOKS,
                  Intent.RECOMMEND_FROM_BOOK, Intent.RECOMMEND_FROM_SELECTION}:
        # Keep interpretation and prose for subjective/complex requests. Only
        # standard comparison wording and generic recommendation wording skip it.
        phrase = normalize(request.message)
        if selected_command(request.message):
            return False
        if intent == Intent.COMPARE_BOOKS:
            standard = phrase in {'compare these', 'compare these two', 'compare these books',
                                  'compare the selected books'}
            standard = standard or bool(re.fullmatch(
                r'compare the first (?:two|three|four)(?: (?:books|ones|results))?', phrase))
            if parsed and len(parsed.mentioned_titles) >= 2:
                titles = ' and '.join(' '.join(t.casefold().split()) for t in parsed.mentioned_titles)
                standard = standard or phrase == 'compare ' + titles
            return not standard
        return not bool(re.fullmatch(
            r'(?:please\s+)?(?:recommend(?:\s+(?:me\s+)?(?:something|books?|a book|something to read))?'
            r'|what should i read(?: next)?|give me (?:some )?recommendations)', phrase))
    return False


# Phase 16: detect purely conceptual/definitional questions that should not be
# hijacked by stale SEARCH_BOOKS intent from a prior conversation turn.
_GENERAL_CONCEPT_PATTERN = re.compile(
    r'^what (?:is|are|does|do)\s+.{3,120}\??$'
    r'|^(?:define|explain|describe)\s+.{3,120}\??$'
    r'|^what (?:is the )?(?:difference|meaning) .{3,120}\??$',
    re.IGNORECASE
)


def looks_like_general_concept(message: str) -> bool:
    """Return True if message is a pure definitional question that should not
    be treated as a follow-up search even when prior intent was SEARCH_BOOKS.

    We are deliberately conservative: only match simple 'What is/are X?'
    patterns that contain no catalogue-specific signals.
    """
    phrase = message.strip()
    # If the message mentions selection keywords it is a follow-up, not general.
    catalogue_signals = re.search(
        r'\b(?:available|recommend|similar|compare|borrow|reserve|select|find|search|show|pdf|document|owe|fines?|fees?|loans?|reservations?|account|history|due|this|these|my|author|title|chapter)\b',
        phrase, re.IGNORECASE
    )
    if catalogue_signals:
        return False
    return bool(_GENERAL_CONCEPT_PATTERN.match(phrase))
