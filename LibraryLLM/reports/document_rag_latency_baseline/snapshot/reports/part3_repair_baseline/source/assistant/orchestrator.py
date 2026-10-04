import asyncio
from datetime import datetime, timedelta, timezone
import logging
import os
import re
from time import monotonic
from uuid import uuid4

from assistant.qwen import QwenUnavailable
from assistant.schemas import (Action, AssistantAction, AssistantError, AssistantResponse,
                               Book, Clarification, Comparison, Intent, PendingAction,
                               RecommendationMode)
from assistant.tools import ToolFailure
from assistant.profiling import measured, timed
from assistant.routing import FastRouteError, fast_route, looks_like_general_concept, needs_prose

LOG = logging.getLogger('luminar.assistant')
RECOMMEND = {Intent.RECOMMEND_BOOKS, Intent.RECOMMEND_FROM_BOOK, Intent.RECOMMEND_FROM_SELECTION,
             Intent.RECOMMEND_AVAILABLE_SIMILAR}
MUTATING = {Intent.BORROW_BOOK, Intent.RETURN_BOOK, Intent.RESERVE_BOOK}
ENTITY = MUTATING | {Intent.COMPARE_BOOKS, Intent.CHECK_AVAILABILITY, Intent.BOOK_DETAILS,
                     Intent.BOOK_CONTENT_QUESTION}
READING_LIST_WRITE = {Intent.ADD_TO_READING_LIST, Intent.REMOVE_FROM_READING_LIST,
                      Intent.CLEAR_READING_LIST}
# Default initial page size; show-more continues from offset.
DEFAULT_PAGE_SIZE = 10


def enabled(name, default=False):
    return os.getenv(name, 'true' if default else 'false').lower() in ('1', 'true', 'yes')


def text(value):
    return '; '.join(value) if isinstance(value, list) else str(value or '')


def merge_ranks(rankings, excluded):
    """Equal-weight reciprocal rank fusion, k=60; ties use canonical work_id."""
    scores = {}
    for ranking in rankings:
        for rank, wid in enumerate(dict.fromkeys(ranking), 1):
            if wid not in excluded:
                scores[wid] = scores.get(wid, 0) + 1 / (60 + rank)
    return sorted(scores, key=lambda wid: (-scores[wid], wid))


def explicit_ordinals(message):
    """Literal reference guard when Qwen omits an explicitly named result number."""
    words = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4}
    matches = re.finditer(
        r'\b(first|second|third|fourth|\d+(?:st|nd|rd|th))\s+(?:one|book|result|recommendation)\b'
        r'|\b(?:book|result|recommendation)\s+#?(\d+)\b', message.casefold())
    result = []
    for match in matches:
        value = match.group(1) or match.group(2)
        number = words[value] if value in words else int(re.match(r'\d+', value).group())
        if number not in result:
            result.append(number)
    return result


class NeedsClarification(Exception):
    def __init__(self, reason, choices=()):
        self.reason, self.choices = reason, list(choices)


class AssistantOrchestrator:
    def __init__(self, qwen, store):
        self.qwen, self.store = qwen, store

    async def chat(self, request, owner, tools):
        state = self.store.get(request.conversation_id, owner)
        async with state.lock:
            state.touched = monotonic()
            response = AssistantResponse(conversation_id=state.conversation_id)
            try:
                if request.action in {'CONFIRM_ACTION', 'CANCEL_ACTION'} or request.pending_action_id:
                    await self.confirm(request, state, tools, response)
                    return response

                # ── Phase 7/8 – Explicit explain actions (lazy, Qwen-backed) ──────────────
                if request.action == 'EXPLAIN_RECOMMENDATION':
                    await self._explain_recommendation(request, state, tools, response)
                    return response
                if request.action == 'EXPLAIN_COMPARISON':
                    await self._explain_comparison(request, state, tools, response)
                    return response

                with timed('intent_routing'):
                    fast = fast_route(request)
                routing_request = request
                if fast:
                    parsed, routing_request = fast
                else:
                    # ── Phase 16: stale-context fix ──────────────────────────────────────
                    # If the last turn was SEARCH_BOOKS and the current message looks like
                    # a pure definitional question, force GENERAL_LIBRARY_HELP before
                    # sending to Qwen. Only safe to do when there are no selected books or
                    # page context that would make it a genuine follow-up.
                    if (state.last_intent == Intent.SEARCH_BOOKS
                            and not request.selected_work_ids
                            and not request.page_context.work_id
                            and looks_like_general_concept(request.message)):
                        from assistant.schemas import AssistantIntent
                        parsed = AssistantIntent(intent=Intent.GENERAL_LIBRARY_HELP, confidence=1.0)
                    else:
                        parsed = await self.qwen.parse(request.message, {
                            'selected_work_ids': request.selected_work_ids,
                            'recent_work_ids': state.recent_result_work_ids or request.recent_work_ids,
                            'last_comparison_work_ids': state.last_comparison_work_ids,
                            'last_recommendation_work_ids': state.last_recommendation_work_ids,
                            'page_context': request.page_context.model_dump(),
                            'last_intent': state.last_intent,
                        })
                # Generic recommendations require no preferences or entity
                # clarification. This guarantees the mandated zero/one/many modes.
                generic_recommend = re.fullmatch(
                    r'(?:please\s+)?(?:recommend(?:\s+(?:me\s+)?(?:something|books?|a book|something to read))?'
                    r'|what should i read(?: next)?|give me (?:some )?recommendations)[.!?]*',
                    request.message.strip().casefold())
                if generic_recommend and not request.action:
                    parsed = parsed.model_copy(update={'intent': Intent.RECOMMEND_BOOKS,
                        'clarification_needed': False, 'reference': 'none', 'ordinal_references': [],
                        'mentioned_titles': [], 'mentioned_authors': [], 'resolved_work_ids': [],
                        'unsupported_filters': [], 'filters': type(parsed.filters)()})
                ordinals = explicit_ordinals(request.message)
                if ordinals and not request.action:
                    parsed = parsed.model_copy(update={'ordinal_references': ordinals})
                # A literal availability question overrides stale comparison
                # context. Mixed comparison questions retain Qwen's extraction.
                availability_question = re.fullmatch(
                    r'(?:is|are)\s+.+\s+available(?:\s+(?:now|today))?[?.!]*',
                    request.message.strip().casefold())
                if availability_question and not request.action and not re.search(
                    r'\b(shorter|longer|compare|beginner|similar|recommend)\b', request.message.casefold()):
                    parsed = parsed.model_copy(update={'intent': Intent.CHECK_AVAILABILITY,
                                                       'clarification_needed': False, 'unsupported_filters': []})
                # ── Phase 16 routing fix: SEARCH hijacking conceptual questions ────────
                # If Qwen returned SEARCH_BOOKS for a pure conceptual question that
                # shows no search signals, demote to GENERAL_LIBRARY_HELP.
                if (parsed.intent == Intent.SEARCH_BOOKS
                        and not request.action
                        and not request.selected_work_ids
                        and not request.page_context.work_id
                        and looks_like_general_concept(request.message)):
                    parsed = parsed.model_copy(update={'intent': Intent.GENERAL_LIBRARY_HELP})

                LOG.info('intent_extracted conversation_id=%s intent=%s confidence=%.2f reference=%s clarification=%s',
                         state.conversation_id, parsed.intent.value, parsed.confidence,
                         parsed.reference, parsed.clarification_needed)
                response.intent = parsed.intent
                state.selected_work_ids = list(dict.fromkeys(request.selected_work_ids))
                # Any new ordinary turn invalidates a previous action proposal.
                state.pending = None
                state.pending_issue_id = None
                # Concrete entity intents must reach authoritative resolution:
                if parsed.intent in {Intent.UNKNOWN, Intent.CLARIFICATION} or (
                    parsed.clarification_needed and parsed.intent not in ENTITY | RECOMMEND):
                    raise NeedsClarification('Please specify what you want to find or which book you mean.')
                if parsed.unsupported_filters:
                    raise NeedsClarification('These catalogue filters are unavailable: '
                                             + ', '.join(parsed.unsupported_filters) + '.')
                with timed('tool_execution'):
                    await self.route(routing_request, parsed, state, tools, response)
                if not response.rag and needs_prose(request, response.intent, parsed):
                    try:
                        response.message = await self.qwen.respond(request.message, response)
                    except QwenUnavailable as exc:
                        response.errors.append(AssistantError(code='QWEN_UNAVAILABLE', service='qwen', message=str(exc)))
                        response.message = response.message or 'Verified results are available below; the explanation could not be generated.'
                # Operational facts and confirmation wording are rendered from
                # verified fields; generated prose cannot replace these values.
                self.ground_operational_message(response)
                ids = [b.work_id for b in response.books]
                if ids:
                    state.recent_result_work_ids = ids[:20]
                if parsed.intent == Intent.SEARCH_BOOKS:
                    state.last_search_work_ids = ids
                if response.intent in RECOMMEND:
                    state.last_recommendation_work_ids = ids
                if response.intent == Intent.COMPARE_BOOKS:
                    state.last_comparison_work_ids = ids
                state.last_intent = response.intent
            except (NeedsClarification, FastRouteError) as exc:
                response.intent = Intent.CLARIFICATION
                response.clarification = Clarification(reason=exc.reason, choices=exc.choices)
                response.message = exc.reason
                response.actions = [Action(type=AssistantAction.SELECT_BOOK, work_id=b.work_id) for b in exc.choices]
            except ToolFailure as exc:
                response.errors.append(exc.error)
                response.message = exc.error.message
            except QwenUnavailable as exc:
                response.errors.append(AssistantError(code='QWEN_UNAVAILABLE', service='qwen', message=str(exc)))
                response.message = str(exc)
            except Exception:
                # No raw exception/user content in logs or responses; schema remains stable.
                LOG.error('assistant_unexpected_error conversation_id=%s', state.conversation_id)
                response.errors.append(AssistantError(code='ASSISTANT_ERROR', service='assistant',
                                                       message='Assistant request could not be completed.'))
                response.message = response.errors[-1].message
            finally:
                LOG.info('assistant conversation_id=%s intent=%s selected_count=%d resolved_ids=%s result_count=%d',
                         state.conversation_id, response.intent.value, len(request.selected_work_ids),
                         state.last_referenced_work_ids, len(response.books))
            return response

    # ── Phase 7: Lazy recommendation explanation ───────────────────────────────
    async def _explain_recommendation(self, request, state, tools, response):
        """Qwen-backed explanation of a previous recommendation result.
        Only invoked on explicit user request; never blocks initial results.
        """
        response.intent = Intent.RECOMMEND_BOOKS
        seed_ids = (list(dict.fromkeys(request.selected_work_ids)) or
                    state.last_recommendation_work_ids or [])
        rec_ids = (state.last_recommendation_work_ids or
                   state.recent_result_work_ids or [])
        books = []
        if rec_ids:
            try:
                books = await tools.catalogue.books(rec_ids[:6])
            except ToolFailure:
                pass
        seed_books = []
        if seed_ids:
            try:
                seed_books = await tools.catalogue.books(seed_ids[:2])
            except ToolFailure:
                pass
        # Provide seed metadata and recommendation metadata to Qwen.
        # Only factual fields (title, authors, subjects) are included.
        explanation_context = {
            'seeds': [{'title': b.title, 'authors': text(b.authors), 'subjects': text(b.subjects)}
                      for b in seed_books],
            'recommendations': [{'title': b.title, 'authors': text(b.authors),
                                  'subjects': text(b.subjects)} for b in books],
        }
        response.books = books
        response.availability = [tools.availability.availability(b) for b in books]
        try:
            prompt = ('Explain in 2-3 sentences why the following books were recommended '
                      'based on the seed books. Use only the subjects and authors shown. '
                      'Do not invent information.\n' +
                      str(explanation_context))
            response.message = await self.qwen.generate(prompt)
        except QwenUnavailable as exc:
            response.errors.append(AssistantError(code='QWEN_UNAVAILABLE', service='qwen', message=str(exc)))
            response.message = 'Could not generate an explanation right now.'

    # ── Phase 8: Lazy comparison explanation ──────────────────────────────────
    async def _explain_comparison(self, request, state, tools, response):
        """Qwen-backed narrative synthesis of a previous comparison result.
        Only invoked on explicit user request; never blocks initial comparison.
        """
        response.intent = Intent.COMPARE_BOOKS
        ids = (state.last_comparison_work_ids or
               list(dict.fromkeys(request.selected_work_ids)) or [])
        if not ids:
            raise NeedsClarification('No recent comparison to explain. Compare books first.')
        books = await tools.catalogue.books(ids[:4])
        response.comparison = Comparison(books=books, requested_fields=[], missing_fields=[])
        response.availability = [tools.availability.availability(b) for b in books]
        comparison_data = [
            {'title': b.title, 'authors': text(b.authors),
             'subjects': text(b.subjects), 'description': (b.description or '')[:400]}
            for b in books
        ]
        try:
            prompt = ('Briefly summarize in 2-4 sentences the key differences and similarities '
                      'between these books. Only use the provided metadata.\n' +
                      str(comparison_data))
            response.message = await self.qwen.generate(prompt)
        except QwenUnavailable as exc:
            response.errors.append(AssistantError(code='QWEN_UNAVAILABLE', service='qwen', message=str(exc)))
            response.message = 'Could not generate a comparison narrative right now.'

    @staticmethod
    def ground_operational_message(response):
        if response.pending_action:
            action = {Intent.BORROW_BOOK: 'borrowing', Intent.RESERVE_BOOK: 'reserving',
                      Intent.RETURN_BOOK: 'returning'}[response.pending_action.type]
            title = response.books[0].title or response.pending_action.work_id
            response.message = f'Confirm {action} {title}?'
            if not response.pending_action.enabled:
                response.message += ' Library actions are currently disabled.'
        elif response.intent == Intent.CHECK_AVAILABILITY:
            statements = []
            for book, availability in zip(response.books, response.availability):
                status = ('availability unknown' if availability.available is None
                          else 'available' if availability.available else 'unavailable')
                counts = (f' ({availability.available_copies} available copies'
                          + (f', {availability.total_copies} total' if availability.total_copies is not None else '')
                          + ')' if availability.available_copies is not None else '')
                statements.append(f'{book.title or book.work_id}: {status}{counts}.')
            response.message = ' '.join(statements)
        elif response.intent == Intent.USER_FEES and response.account is not None:
            total = response.account.get('total_unpaid')
            response.message = ('Your unpaid fees total ' + str(total) + '. See the fee records below.'
                                if total is not None else 'See your verified fee records below.')
        elif response.intent in {Intent.USER_LOANS, Intent.USER_HISTORY, Intent.USER_RESERVATIONS}:
            response.message = 'Your verified account records are shown below.'
        elif response.intent == Intent.USER_READING_LIST:
            count = len(response.reading_list or [])
            response.message = (f'Your reading list has {count} book{"s" if count != 1 else ""}.'
                                if count else 'Your reading list is empty.')
        elif response.intent == Intent.ADD_TO_READING_LIST:
            added = len(response.books)
            response.message = (f'Added {added} book{"s" if added != 1 else ""} to your reading list.'
                                if added else 'Books added to your reading list.')
        elif response.intent == Intent.REMOVE_FROM_READING_LIST:
            response.message = 'Removed from your reading list.'
        elif response.intent == Intent.CLEAR_READING_LIST:
            response.message = 'Your reading list has been cleared.'
        elif response.comparison and response.comparison.missing_fields:
            response.message = ('The catalogue does not record these comparison fields: '
                                + ', '.join(response.comparison.missing_fields)
                                + '. Verified metadata and availability are shown below.')
        elif response.intent in RECOMMEND | {Intent.SEARCH_BOOKS} and not response.books:
            response.message = 'The service returned no matching books for this request.'
        elif not response.message and response.intent == Intent.SEARCH_BOOKS:
            response.message = f'I found {len(response.books)} matching books.'
        elif not response.message and response.intent in RECOMMEND:
            response.message = ('Here are recommendations based on your selected books.'
                if len(response.seed_work_ids) > 1 else 'Here are books related to your selected book.'
                if response.seed_work_ids else 'Here are your recommendations.')
        elif not response.message and response.comparison:
            response.message = 'Compare verified catalogue metadata and availability below.'
        elif not response.message and response.intent == Intent.BOOK_DETAILS:
            response.message = 'Verified book details are shown below.'

    @measured('entity_resolution')
    async def resolve(self, request, parsed, state, tools, optional=False):
        selected = list(dict.fromkeys(request.selected_work_ids))
        # Qwen may reference only IDs actually supplied by the user/context.
        explicit = re.findall(r'\b[A-Za-z0-9_-]+\b', request.message)
        literal_ids = [wid for wid in parsed.resolved_work_ids if wid in explicit]
        context = (state.recent_result_work_ids or request.recent_work_ids
                   or state.last_comparison_work_ids or state.last_recommendation_work_ids)
        page = ([request.page_context.work_id] if request.page_context.work_id else request.page_context.work_ids)
        pool = selected or literal_ids
        if selected and parsed.mentioned_titles and not parsed.ordinal_references:
            # Explicit names disambiguate within selection before catalogue
            # lookup. They must not silently target a different selected book.
            selected_books = await tools.catalogue.books(selected)
            title_matches = [[b.work_id for b in selected_books
                              if text(b.title).casefold() == title.casefold()]
                             for title in parsed.mentioned_titles]
            if all(len(matches) == 1 for matches in title_matches):
                pool = [matches[0] for matches in title_matches]
            else:
                context = selected
                pool = []
        if parsed.ordinal_references:
            pool = pool or context or page
            if any(n < 1 or n > len(pool) for n in parsed.ordinal_references):
                raise NeedsClarification('That result number is not in the current book list.')
            pool = [pool[n-1] for n in parsed.ordinal_references]
        elif not pool and (parsed.mentioned_titles or parsed.mentioned_authors):
            resolved = []
            titles = parsed.mentioned_titles or [None]
            for index, title in enumerate(titles):
                author = (parsed.mentioned_authors[index] if len(parsed.mentioned_authors) == len(titles)
                          else parsed.mentioned_authors[0] if len(parsed.mentioned_authors) == 1 else None)
                # Author/title references to a previous list resolve within that list first.
                known = await tools.catalogue.books(list(context)[:20]) if context else []
                matches = [b for b in known if (not title or text(b.title).casefold() == title.casefold())
                           and (not author or author.casefold() in text(b.authors).casefold())]
                if not matches:
                    matches = await tools.catalogue.resolve(title, author)
                if not matches and title:
                    ids = await tools.search.search(' '.join(filter(None, (title, author))), 6)
                    matches = await tools.catalogue.books(ids)
                    exact = [b for b in matches if text(b.title).casefold() == title.casefold()
                             and (not author or author.casefold() in text(b.authors).casefold())]
                    if exact:
                        matches = exact
                    else:
                        raise NeedsClarification('Choose the book you mean.', matches)
                if len(matches) != 1:
                    raise NeedsClarification('Choose the book you mean.', matches)
                resolved.append(matches[0].work_id)
            pool = resolved
        elif not pool and parsed.reference != 'none':
            pool = (state.last_recommendation_work_ids if parsed.reference == 'previous_recommendation'
                    else context) or page
        elif not pool and not optional:
            pool = context or page
        if parsed.mentioned_authors and pool and not parsed.mentioned_titles:
            books = await tools.catalogue.books(pool)
            pool = [b.work_id for b in books if any(a.casefold() in text(b.authors).casefold()
                                                   for a in parsed.mentioned_authors)]
        if not pool and optional and parsed.reference == 'none' and not (parsed.mentioned_titles or parsed.mentioned_authors):
            return []
        if not pool:
            raise NeedsClarification('Select a book or give its title or catalogue work_id.')
        books = await tools.catalogue.books(pool)
        # A singular deictic reference cannot pick arbitrarily among several books.
        if parsed.reference == 'this' and not parsed.ordinal_references and len(books) != 1:
            raise NeedsClarification('Which book do you mean?', books)
        state.last_referenced_work_ids = [b.work_id for b in books]
        return books

    async def filtered(self, books, filters, seeds):
        def keep(book):
            if filters.available_only and (book.available_copies is None or book.available_copies <= 0):
                return False
            if filters.author and filters.author.casefold() not in text(book.authors).casefold():
                return False
            if filters.subject and filters.subject.casefold() not in text(book.subjects).casefold():
                return False
            if filters.exclude_seed_authors and any(set(self.authors(book)) & set(self.authors(seed)) for seed in seeds):
                return False
            return True
        results = [b for b in books if keep(b)]
        if filters.sort_preference == 'title':
            results.sort(key=lambda b: text(b.title).casefold())
        elif filters.sort_preference == 'rating':
            results.sort(key=lambda b: -(b.average_rating if b.average_rating is not None else -1))
        return results

    @staticmethod
    def authors(book):
        # Match the existing recommender's pipe-separated catalogue author
        # convention. A comma can be part of a surname-first author name.
        values = book.authors if isinstance(book.authors, list) else (book.authors or '').split('|')
        return [a.strip().casefold() for a in values if a.strip()]

    async def route(self, request, parsed, state, tools, response):
        intent = parsed.intent
        # ── Show-more pagination (Phase 10) ──────────────────────────────────
        # offset is extracted from the validated request schema.
        page_size = parsed.requested_result_count
        offset = getattr(request, 'result_offset', 0)

        if intent == Intent.SEARCH_BOOKS:
            ids = await tools.search.search(parsed.query or request.message, 50 + offset)
            all_books = await self.filtered(await tools.catalogue.books(ids), parsed.filters, [])
            sliced = all_books[offset:offset + page_size]
            response.books = sliced
            response.has_more = len(all_books) > offset + page_size
            response.result_offset = offset

        elif intent in RECOMMEND:
            # RECOMMEND_AVAILABLE_SIMILAR: seed recommendation filtered to available only.
            if intent == Intent.RECOMMEND_AVAILABLE_SIMILAR:
                targets = list(dict.fromkeys(request.selected_work_ids))
                if not targets:
                    raise NeedsClarification('Select a book to find available alternatives.')
                seeds = await tools.catalogue.books(targets[:1])
                response.seed_work_ids = [b.work_id for b in seeds]
                response.intent = Intent.RECOMMEND_AVAILABLE_SIMILAR
                response.recommendation_mode = RecommendationMode.SINGLE_SELECTED_BOOK
                rankings = await asyncio.gather(*(tools.recommendation.recommend(50, b.work_id) for b in seeds))
                ids = merge_ranks(rankings, set(response.seed_work_ids))
                from assistant.schemas import Filters
                all_books = await self.filtered(
                    await tools.catalogue.books(ids),
                    Filters(available_only=True),
                    seeds)
                all_books = all_books[:page_size + offset]
                sliced = all_books[offset:offset + page_size]
                response.books = sliced
                response.has_more = len(all_books) > offset + page_size
                response.result_offset = offset
            else:
                # Selection means ALL selected seeds, irrespective of a generated
                # ordinal/title/author interpretation in this recommendation turn.
                seed_intent = parsed.model_copy(update={'ordinal_references': [], 'reference': 'none',
                                                        'mentioned_titles': [], 'mentioned_authors': []}) if request.selected_work_ids else parsed
                seeds = await self.resolve(request, seed_intent, state, tools, optional=True)
                response.seed_work_ids = [b.work_id for b in seeds]
                if request.selected_work_ids:
                    response.recommendation_mode = (RecommendationMode.SINGLE_SELECTED_BOOK if len(seeds) == 1
                                                    else RecommendationMode.MULTI_SELECTED_BOOKS)
                    response.intent = Intent.RECOMMEND_FROM_BOOK if len(seeds) == 1 else Intent.RECOMMEND_FROM_SELECTION
                elif seeds:
                    response.recommendation_mode = RecommendationMode.EXPLICIT_BOOK_SEED
                    response.intent = Intent.RECOMMEND_FROM_BOOK
                else:
                    response.recommendation_mode = RecommendationMode.PERSONALIZED_EXISTING_FORMULA
                    response.intent = Intent.RECOMMEND_BOOKS
                if seeds:
                    rankings = await asyncio.gather(*(tools.recommendation.recommend(50, b.work_id) for b in seeds))
                    ids = merge_ranks(rankings, set(response.seed_work_ids))
                else:
                    # Preserve the default formula's TopN/diversity behavior exactly.
                    has_filters = parsed.filters.model_dump() != type(parsed.filters)().model_dump()
                    ids = await tools.recommendation.recommend(50 if has_filters else page_size + offset)
                all_books = await self.filtered(await tools.catalogue.books(ids), parsed.filters, seeds)
                sliced = all_books[offset:offset + page_size]
                response.books = sliced
                response.has_more = len(all_books) > offset + page_size
                response.result_offset = offset
                # Explanation is available when there are seeds and books (Phase 7)
                if response.seed_work_ids and response.books:
                    response.explanation_available = True

        elif intent in ENTITY:
            books = await self.resolve(request, parsed, state, tools)
            if intent == Intent.COMPARE_BOOKS:
                if not 2 <= len(books) <= 4:
                    raise NeedsClarification('Select two to four books to compare.', books)
                known = {'title', 'authors', 'author', 'subjects', 'description', 'rating', 'average_rating',
                         'availability', 'available_copies', 'total_copies', 'shelf_location'}
                missing = [f for f in parsed.comparison_fields if f not in known]
                response.comparison = Comparison(books=books, requested_fields=parsed.comparison_fields,
                                                   missing_fields=missing)
                # Explanation is available after comparison (Phase 8)
                response.explanation_available = True
            elif intent in MUTATING:
                if len(books) != 1:
                    raise NeedsClarification('Choose one book for this action.', books)
                issue_id = None
                if intent == Intent.RETURN_BOOK:
                    loans = await tools.loans.loans()
                    matches = [r for r in loans['issues'] if r.get('work_id') == books[0].work_id]
                    if len(matches) != 1:
                        raise NeedsClarification('A unique active loan for this book could not be found.')
                    issue_id = matches[0]['issue_id']
                pending = PendingAction(action_id=uuid4().hex, type=intent, work_id=books[0].work_id,
                                        expires_at=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),
                                        enabled=enabled('ASSISTANT_MUTATING_ACTIONS_ENABLED'))
                state.pending, state.pending_issue_id = pending, issue_id
                state.pending_deadline = monotonic() + 300
                response.pending_action = pending
                response.message = f'Confirm {intent.value.lower().replace("_book", "")} for {books[0].title}?'
                response.actions = [Action(type=AssistantAction.CONFIRM_ACTION, action_id=pending.action_id),
                                    Action(type=AssistantAction.CANCEL_ACTION, action_id=pending.action_id)]
            elif intent == Intent.BOOK_CONTENT_QUESTION:
                if len(books) != 1:
                    raise NeedsClarification('Select one book for a content question.', books)
                response.rag = await tools.rag.ask(request.message, work_id=books[0].work_id)
                response.message = response.rag.get('answer', '')
            response.books = books

        elif intent == Intent.DOCUMENT_QUESTION:
            if not request.page_context.document_id:
                raise NeedsClarification('Provide the uploaded document_id in page_context.')
            response.rag = await tools.rag.ask(request.message, document_id=request.page_context.document_id)
            response.message = response.rag.get('answer', '')

        elif intent in {Intent.USER_LOANS, Intent.USER_HISTORY}:
            response.account = await tools.loans.loans(history=intent == Intent.USER_HISTORY)

        elif intent == Intent.USER_RESERVATIONS:
            response.account = await tools.reservations.reservations()

        elif intent == Intent.USER_FEES:
            response.account = await tools.fees.fees()

        # ── Phase 3: Reading list intents ────────────────────────────────────
        elif intent == Intent.USER_READING_LIST:
            raw = await tools.reading_list.get()
            items = raw.get('items', [])
            # Convert to Book objects using only authoritative catalogue fields.
            rl_books = []
            for item in items:
                wid = item.get('work_id')
                if wid:
                    rl_books.append(Book(
                        work_id=wid,
                        title=item.get('title') or None,
                        authors=item.get('authors') or None,
                        available_copies=item.get('available_copies'),
                        total_copies=item.get('total_copies'),
                    ))
            response.reading_list = rl_books
            response.intent = Intent.USER_READING_LIST

        elif intent == Intent.ADD_TO_READING_LIST:
            targets = list(dict.fromkeys(request.selected_work_ids))
            if not targets:
                raise NeedsClarification('Select at least one book to add to your reading list.')
            # Validate all work_ids through catalogue before persisting.
            books = await tools.catalogue.books(targets)
            await asyncio.gather(*(tools.reading_list.add(b.work_id) for b in books))
            response.books = books
            response.intent = Intent.ADD_TO_READING_LIST

        elif intent == Intent.REMOVE_FROM_READING_LIST:
            targets = list(dict.fromkeys(request.selected_work_ids))
            if not targets:
                raise NeedsClarification('Select a book to remove from your reading list.')
            books = await tools.catalogue.books(targets)
            await asyncio.gather(*(tools.reading_list.remove(b.work_id) for b in books))
            response.books = books
            response.intent = Intent.REMOVE_FROM_READING_LIST

        elif intent == Intent.CLEAR_READING_LIST:
            raw = await tools.reading_list.get()
            work_ids = [item['work_id'] for item in raw.get('items', []) if item.get('work_id')]
            if work_ids:
                await tools.reading_list.clear(work_ids)
            response.intent = Intent.CLEAR_READING_LIST

        elif intent != Intent.GENERAL_LIBRARY_HELP:
            raise NeedsClarification('Please describe the library task you want help with.')

        # Attach availability for all books in standard result sets.
        response.availability = [tools.availability.availability(b) for b in response.books]
        if not response.pending_action and intent not in READING_LIST_WRITE | {
                Intent.USER_READING_LIST, Intent.CLEAR_READING_LIST}:
            # Standard book card actions — Phase 11: include ADD_TO_READING_LIST.
            response.actions = [
                Action(type=action, work_id=b.work_id) for b in response.books
                for action in (AssistantAction.VIEW_BOOK, AssistantAction.SELECT_BOOK,
                               AssistantAction.RECOMMEND_SIMILAR, AssistantAction.CHECK_AVAILABILITY,
                               AssistantAction.ADD_TO_READING_LIST)
            ]
            # Phase 5: If any book is unavailable, offer RECOMMEND_AVAILABLE_SIMILAR.
            for b in response.books:
                avail = tools.availability.availability(b)
                if avail.available is False:
                    response.actions.append(
                        Action(type=AssistantAction.RECOMMEND_AVAILABLE_SIMILAR, work_id=b.work_id)
                    )
            # Show-more action if there are more results.
            if response.has_more:
                response.actions.append(Action(type=AssistantAction.SHOW_MORE))

    async def confirm(self, request, state, tools, response):
        pending = state.pending
        if request.action not in {'CONFIRM_ACTION', 'CANCEL_ACTION'} or not request.pending_action_id:
            raise NeedsClarification('Confirmation requires both action and pending_action_id.')
        if not pending or pending.action_id != request.pending_action_id or monotonic() > state.pending_deadline:
            raise NeedsClarification('This action is invalid, expired or already consumed. Request it again.')
        response.intent = pending.type
        if request.action == 'CANCEL_ACTION':
            state.pending = None
            response.message = 'Action cancelled.'
            return
        if not enabled('ASSISTANT_MUTATING_ACTIONS_ENABLED'):
            response.pending_action = pending
            response.message = 'Library actions are currently disabled. No action was performed.'
            response.errors.append(AssistantError(code='MUTATIONS_DISABLED', service='assistant', message=response.message))
            return
        # Consume before sending: a timeout may have committed at Core. Never auto-retry.
        state.pending = None
        if pending.type == Intent.BORROW_BOOK:
            result = await tools.loans.borrow(pending.work_id)
        elif pending.type == Intent.RESERVE_BOOK:
            result = await tools.reservations.reserve(pending.work_id)
        elif pending.type == Intent.RETURN_BOOK and state.pending_issue_id is not None:
            result = await tools.loans.return_book(state.pending_issue_id)
        else:
            raise NeedsClarification('The pending action cannot be executed.')
        state.pending_issue_id = None
        response.account = result
        response.message = result.get('message', 'Library action completed.')
