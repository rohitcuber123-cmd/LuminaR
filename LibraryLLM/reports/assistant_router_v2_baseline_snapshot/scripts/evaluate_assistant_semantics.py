"""Opt-in real-Qwen evaluation inside the one existing RAG service process.

Synthetic catalogue fixtures for the language corpus, real catalogue/API tools
for the required sports-economics chain. No model loading, mutation execution,
credentials or private account records are written to reports.
"""
import asyncio
import importlib.util
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
A, B, C, D = 'OL_SPORT_A', 'OL_SPORT_B', 'OL_FOUNDATION', 'OL_DUNE'


def corpus():
    cases = []
    def group(category, intent, utterances, ids=(A, B), context='selected', criterion=False, fields=None):
        for message in utterances:
            cases.append(dict(category=category, message=message, expected_intent=intent,
                expected_ids=list(ids), context=context, criterion=criterion, fields=fields or []))
    group('factual_comparison', 'COMPARE_BOOKS', [
        'how do they stack up against each other', 'what separates the two',
        "what's the tradeoff between them", 'how would you distinguish these',
        "what does one offer that the other doesn't", 'can you contrast them',
        'are they basically the same', 'tell me where their metadata disagrees',
        'put the pair side by side', 'give me a rundown of their differences',
        "between these, I don't care about ratings, what's different", 'what differences do these books indicate'])
    group('preference', 'COMPARE_BOOKS', [
        'which one would be better', 'which is the better pick', 'which one should I go for',
        'which would make more sense for me', 'would either work', 'help me decide between them',
        'if you had to pick between the two, what matters', 'which should win a place on my reading list',
        'what should I prioritize when choosing one', 'is one of the two preferable',
        'I only have time for one of them', 'which one is worth my time'])
    group('preference_criterion', 'COMPARE_BOOKS', [
        'which would suit a beginner', 'which one would be better for learning sports economics',
        'I want to learn about soccer finance; which of these fits',
        'which one is a better match for a reader interested in league revenues',
        'for a newcomer to football business, which would you choose',
        'which of these might help with my course on sports markets',
        'I care about the economics of clubs rather than players; compare their fit',
        'which seems appropriate for someone studying professional football',
        'help me choose for a research project about sport',
        'what would I gain by choosing the first for a football economics class'], criterion=True)
    group('availability', 'CHECK_AVAILABILITY', [
        'would either of these be available', 'are both currently borrowable',
        "which one isn't unavailable", 'can I get a copy of either today',
        'does the library have these in stock', 'check whether the pair has any copies free',
        'what is the stock situation for the two', 'are they on the shelf now',
        'which of these has a copy ready', 'do I have to wait for either one'])
    group('field_comparison', 'COMPARE_BOOKS', [
        'which has the stronger rating', 'which of the two is rated more highly',
        'how do their star scores compare', 'who has the better catalogue rating',
        'which has better ratings'], fields=['average_rating'])
    group('subject_comparison', 'COMPARE_BOOKS', [
        'which has more subjects', 'which one lists more topics',
        'compare how many subject labels each one has'], fields=['subjects'])
    group('ordinal_details', 'BOOK_DETAILS', [
        'tell me more about the first', 'give me the metadata for the earlier one',
        'who wrote the first of my picks', "what about the first one's subjects",
        'show the title and author of selection number one'], ids=(A,))
    group('ordinal_details', 'BOOK_DETAILS', [
        'what about the second one', 'give me details for the latter',
        'show me the catalogue entry for the last of these',
        'not the first one, tell me about the other', 'who is the author of my second pick'], ids=(B,))
    group('ordinal_availability', 'CHECK_AVAILABILITY', [
        'is the first one available', 'has the earlier book got any copies left',
        'tell me whether selection number one is in stock'], ids=(A,))
    group('ordinal_availability', 'CHECK_AVAILABILITY', [
        'is my second pick borrowable', 'does the latter have a free copy',
        'check stock for the last one'], ids=(B,))
    group('graph', 'MORE_LIKE_THIS', [
        'what else is like the first one', 'anything connected to the earlier book',
        'show catalogue connections around my first pick',
        'can you find graph relatives of the former'], ids=(A,))
    group('graph', 'MORE_LIKE_THIS', [
        'what else resembles the latter', 'anything connected to the second one',
        'show related titles for my last pick', 'find neighbours of the second book'], ids=(B,))
    group('recommendation', 'RECOMMEND_FROM_SELECTION', [
        'I liked these two, what else might fit', 'use my picks to suggest my next read',
        'can you recommend from the pair I selected', 'take both as seeds for recommendations',
        'build recommendations around my selections'], ids=(A, B))
    group('search', 'SEARCH_BOOKS', [
        'I need something on saving money for someone just starting out',
        'help me find books about urban planning', 'I want to browse gothic fiction',
        'do you have titles covering renewable energy', 'find a book about probability',
        'look for beginner-friendly books on investing', 'show books about neural networks',
        'I am trying to learn gardening; find some titles'], ids=(), context='none')
    for intent, messages in {
        'USER_LOANS': ['what do I currently have out', 'anything overdue?', 'which of my loans is due soonest'],
        'USER_FEES': ['how much do I owe', 'is there an unpaid balance on my account', 'do I have any fines outstanding'],
        'USER_RESERVATIONS': ['did I reserve something', 'what am I waiting to pick up', 'check my holds'],
        'USER_HISTORY': ['what have I borrowed in the past', 'show my earlier borrowing activity'],
        'USER_READING_LIST': ['what have I saved to read later', 'open my saved reading list'],
    }.items(): group('account', intent, messages, ids=(), context='none')
    group('reference_ambiguity', 'CLARIFICATION', [
        'compare them', 'which is better', 'is that one in stock',
        'tell me about the other', 'which one should I go for'], ids=(), context='none')
    group('previous_comparison', 'CHECK_AVAILABILITY', [
        'and which one is available', 'can either be borrowed right now',
        'what is their availability'], context='comparison')
    group('selection_change', 'COMPARE_BOOKS', [
        'which one is the better choice', 'tell me how these differ',
        'what distinguishes my current pair'], ids=(C, D), context='changed')
    group('explicit_entity', 'BOOK_DETAILS', ['tell me about Dune', 'who wrote Dune'], ids=(D,))
    group('page', 'CHECK_AVAILABILITY', ['is this book in stock'], ids=(B,), context='page')
    return cases


def write(name, data):
    (ROOT / 'reports' / name).write_text(json.dumps(data, indent=2, default=str), encoding='utf8')


def baseline_modules():
    package = ModuleType('frozen_semantic'); package.__path__ = []
    sys.modules[package.__name__] = package
    modules = {}
    for name in ('schemas', 'state', 'contextual', 'qwen', 'routing', 'kg_routing', 'tools', 'orchestrator'):
        path = ROOT / 'reports/assistant_semantic_router_baseline/assistant' / (name + '.py')
        source = path.read_text(encoding='utf8').replace('from assistant.', 'from frozen_semantic.')
        source = source.replace('from frozen_semantic.profiling', 'from assistant.profiling')
        module = ModuleType('frozen_semantic.' + name); module.__file__ = str(path)
        sys.modules[module.__name__] = module
        exec(compile(source, str(path), 'exec'), module.__dict__)
        modules[name] = module
    return SimpleNamespace(**modules)


class FixtureTools:
    def __init__(self, schemas, tool_module):
        self.schemas = schemas
        self.records = {A: schemas.Book(work_id=A, title='Economics of Football', authors='Fixture Author A',
            subjects='Soccer | Economics', average_rating=4.5, rating_count=20, available_copies=2, total_copies=2),
            B: schemas.Book(work_id=B, title='The Economics of the National Football League', authors='Fixture Author B',
            subjects='Football | Sports business | Economics', average_rating=3.8, rating_count=10, available_copies=0, total_copies=1),
            C: schemas.Book(work_id=C, title='Foundation', authors='Isaac Asimov', available_copies=1),
            D: schemas.Book(work_id=D, title='Dune', authors='Frank Herbert', available_copies=1)}
        self.title_calls = []; self.search_calls = []
        self.catalogue = SimpleNamespace(books=self.books, resolve=self.resolve)
        self.search = SimpleNamespace(search=self.search_books)
        self.recommendation = SimpleNamespace(recommend=self.recommend)
        self.availability = tool_module.AssistantAvailabilityTool()
        self.kg = SimpleNamespace(more_like_this=self.graph)
        self.loans = SimpleNamespace(loans=self.loans_query)
        self.fees = SimpleNamespace(fees=self.fees_query)
        self.reservations = SimpleNamespace(reservations=self.reservations_query)
        self.reading_list = SimpleNamespace(get=self.list_query)
        self.rag = SimpleNamespace(ask=self.rag_query)

    async def books(self, ids): return [self.records[wid].model_copy() for wid in dict.fromkeys(ids)]
    async def resolve(self, title, author):
        self.title_calls.append(title)
        return [b.model_copy() for b in self.records.values() if (not title or b.title.casefold() == title.casefold())
            and (not author or author.casefold() in str(b.authors).casefold())]
    async def search_books(self, query, count): self.search_calls.append(query); return [C, D]
    async def recommend(self, count, seed=None): return [C, D]
    async def graph(self, seed, count): return {'recommendations': [self.records[C].model_dump()]}
    async def loans_query(self, history=False): return {'count': 0, 'issues': []}
    async def fees_query(self): return {'total_unpaid': 0}
    async def reservations_query(self): return {'reservations': []}
    async def list_query(self): return {'items': []}
    async def rag_query(self, *args, **kwargs): return {'answer': 'Authorized fixture response'}


def establish(orchestrator, case, schemas):
    state = orchestrator.store.get(None, 'semantic-evaluation')
    selection = [A, B] if case['context'] in ('selected', 'changed') else []
    if case['context'] in ('comparison', 'changed'):
        state.last_comparison_work_ids = [A, B]; state.last_intent = schemas.Intent.COMPARE_BOOKS
        state.last_referenced_work_ids = [A, B]; state.active_result_work_ids = [A, B]
        state.recent_result_work_ids = [A, B]; state.last_result_type = 'comparison'
        state.semantic_turns = [dict(intent='COMPARE_BOOKS', referenced_work_ids=[A, B], result_type='comparison', goal='FACTUAL_COMPARE')]
    if case['context'] == 'changed': selection = [C, D]
    return schemas.AssistantRequest(message=case['message'], conversation_id=state.conversation_id,
        selected_work_ids=selection, page_context={'work_id': B} if case['context'] == 'page' else {})


async def measured_case(orchestrator, tools, request):
    from assistant.profiling import current
    profile = {'stages_ms': {}, 'qwen_calls': []}
    token = current.set(profile); started = perf_counter()
    before_title, before_search = len(tools.title_calls), len(tools.search_calls)
    try:
        response = await orchestrator.chat(request, 'semantic-evaluation', tools)
        profile['total_ms'] = (perf_counter() - started) * 1000
        return response, profile, tools.title_calls[before_title:], tools.search_calls[before_search:]
    finally: current.reset(token)


async def evaluate(app, engine):
    import assistant.schemas as schemas
    import assistant.tools as tool_module
    from assistant.orchestrator import AssistantOrchestrator
    from assistant.state import ConversationStore
    from assistant.qwen import QwenGateway
    cases = corpus(); before = []; after = []
    pilot = '--pilot' in sys.argv
    if pilot:
        cases = [cases[index] for index in [0,5,12,24,34,40,45,52,54,57,60,73,81,100,len(cases)-1]]
    case_report = 'assistant_semantic_router_pilot.json' if pilot else 'assistant_semantic_router_cases.json'
    skip_baseline = '--skip-baseline' in sys.argv
    if skip_baseline:
        before = json.loads((ROOT/'reports/assistant_semantic_router_latency.json').read_text())['before']
    old = baseline_modules()
    baseline = old.orchestrator.AssistantOrchestrator(old.qwen.QwenGateway(engine.llm, engine.inference_lock), old.state.ConversationStore())
    benchmark_indices = sorted({round(i * (len(cases)-1) / 19) for i in range(20)})
    for index in ([] if skip_baseline else benchmark_indices):
        case = cases[index]; tools = FixtureTools(old.schemas, old.tools)
        response, profile, title, search = await measured_case(baseline, tools, establish(baseline, case, old.schemas))
        before.append(dict(index=index, message=case['message'], profile=profile, intent=response.intent,
            title_calls=title, search_calls=search, errors=[e.code for e in response.errors]))
        write('assistant_semantic_router_latency.json', {'before': before, 'after': []})
        print('SEMANTIC before', index, response.intent, round(profile['total_ms']), flush=True)
    baseline.qwen.close()
    class ObservedQwen:
        decision = None
        async def parse(self, message, context):
            self.decision = await app.state.assistant.qwen.parse(message, context)
            return self.decision
        async def respond(self, message, response):
            return await app.state.assistant.qwen.respond(message, response)
    observed = ObservedQwen()
    await live_chain(app)
    if '--live-only' in sys.argv: return
    orchestrator = AssistantOrchestrator(observed, ConversationStore())
    for index, case in enumerate(cases):
        tools = FixtureTools(schemas, tool_module)
        request = establish(orchestrator, case, schemas)
        response, profile, title, search = await measured_case(orchestrator, tools, request)
        state = orchestrator.store.entries[request.conversation_id]
        ids = response.seed_work_ids if response.intent in {'MORE_LIKE_THIS', 'RECOMMEND_FROM_SELECTION', 'RECOMMEND_FROM_BOOK'} else state.last_referenced_work_ids
        if case['expected_intent'] == 'CLARIFICATION': ids = []
        good = (response.intent.value == case['expected_intent'] and ids == case['expected_ids'] and not response.errors)
        if case['category'] == 'factual_comparison': good = good and not response.clarification
        if case['fields']: good = good and bool(response.comparison and set(case['fields']) <= set(response.comparison.requested_fields))
        if case['category'] == 'preference': good = good and bool(response.clarification and response.clarification.type == 'CRITERIA_AMBIGUITY')
        if case['criterion']: good = good and bool(observed.decision and observed.decision.criterion and not response.clarification)
        if case['category'] not in {'explicit_entity', 'search'}: good = good and not title and not search
        after.append({**case, 'index': index, 'actual_intent': response.intent, 'resolved_ids': ids,
            'message_result': response.message, 'clarification': response.clarification.model_dump() if response.clarification else None,
            'semantic_decision': observed.decision.model_dump(mode='json') if observed.decision else None,
            'comparison_fields': response.comparison.requested_fields if response.comparison else [],
            'profile': profile, 'title_calls': title, 'search_calls': search, 'errors': [e.code for e in response.errors], 'pass': good})
        write(case_report, {'method': 'real resident Qwen + authoritative synthetic API fixtures',
            'cases': after, 'total': len(after), 'passed': sum(r['pass'] for r in after), 'complete': len(after) == len(cases)})
        if index in benchmark_indices and not pilot:
            write('assistant_semantic_router_latency.json', {'before': before,
                'after': [r for r in after if r['index'] in benchmark_indices]})
        print('SEMANTIC after', index, response.intent.value, good, round(profile['total_ms']), flush=True)
    print('SEMANTIC evaluation complete', sum(r['pass'] for r in after), '/', len(after), flush=True)


async def live_chain(app):
    import httpx
    from backend.database.mongodb import books_collection, users_collection
    from backend.services.identity_service import current_identity
    from backend.utils.jwt_utils import create_access_token
    from assistant.tools import AssistantTools
    from assistant.schemas import AssistantRequest
    books = [books_collection.find_one({'title': {'$regex': '^' + name + '$', '$options': 'i'}})
        for name in ('Economics of Football', 'The Economics of the National Football League')]
    if not all(books):
        write('assistant_semantic_router_live.json', {'status': 'blocked', 'reason': 'Required live catalogue titles missing'})
        return
    user = next((u for u in users_collection.find({'is_email_verified': True, 'role': 'GENERAL_USER'})
        if current_identity({'sub': str(u['user_id'])})), None)
    if user is None:
        write('assistant_semantic_router_live.json', {'status': 'blocked', 'reason': 'No eligible read-only identity'})
        return
    token = create_access_token(user['user_id'], user['email'], user['role'])
    ids = [b['work_id'] for b in books]; rows = []; conversation = None
    async def rag(*a, **k): raise RuntimeError('Live semantic validation never requests private RAG')
    async with httpx.AsyncClient(timeout=50) as client:
        tools = AssistantTools(client, 'Bearer ' + token, rag)
        title_calls = []; search_calls = []
        tools.title_calls, tools.search_calls = title_calls, search_calls
        original_resolve, original_search = tools.catalogue.resolve, tools.search.search
        async def resolve(title, author): title_calls.append(title); return await original_resolve(title, author)
        async def search(query, count): search_calls.append(query); return await original_search(query, count)
        tools.catalogue.resolve, tools.search.search = resolve, search
        # Independent owner-scoped conversation, same pipeline and real APIs.
        from assistant.orchestrator import AssistantOrchestrator
        from assistant.state import ConversationStore
        class LiveObservedQwen:
            decision = None
            async def parse(self, message, context):
                self.decision = await app.state.assistant.qwen.parse(message, context)
                return self.decision
            async def respond(self, message, response):
                return await app.state.assistant.qwen.respond(message, response)
        observed = LiveObservedQwen()
        orch = AssistantOrchestrator(observed, ConversationStore())
        for message in ['what differences do these books indicate', 'which one would be better',
                'for someone mainly interested in soccer economics', 'is the first one available',
                'and the other?', 'anything similar to that one']:
            request = AssistantRequest(message=message, selected_work_ids=ids, conversation_id=conversation)
            response, profile, titles, searches = await measured_case(orch, tools, request)
            conversation = response.conversation_id
            rows.append({'semantic_decision': observed.decision.model_dump(mode='json') if observed.decision else None, 'message': message, 'response': response.model_dump(mode='json'), 'profile': profile,
                'resolved_ids': orch.store.entries[conversation].last_referenced_work_ids,
                'title_calls': titles, 'search_calls': searches})
            write('assistant_semantic_router_live.json', {'method': 'real Qwen, Mongo catalogue and normal authenticated API tools; read-only',
                'selected_work_ids': ids, 'selected_titles': [b['title'] for b in books], 'turns': rows})
            print('SEMANTIC live', message, response.intent.value, flush=True)


if __name__ == '__main__':
    # Restart one RAG process with this runner. No second model or debug endpoint.
    import os
    os.environ['ASSISTANT_PROFILE_PATH'] = str(ROOT / 'reports/assistant_semantic_router_profiles.jsonl')
    import rag.api
    async def startup():
        async def task():
            try:
                await evaluate(rag.api.app, rag.api.engine)
                # Local audit runner only: rerun revised routing code against the
                # same resident engine. No additional model or public endpoint.
                trigger = ROOT / 'reports/.semantic_router_rerun'
                while True:
                    await asyncio.sleep(1)
                    if trigger.exists():
                        mode = trigger.read_text().strip()
                        trigger.unlink()
                        import importlib
                        import assistant.qwen, assistant.semantic, assistant.orchestrator
                        importlib.reload(assistant.qwen)
                        importlib.reload(assistant.semantic)
                        importlib.reload(assistant.orchestrator)
                        rag.api.app.state.assistant.qwen.__class__ = assistant.qwen.QwenGateway
                        rag.api.app.state.assistant.__class__ = assistant.orchestrator.AssistantOrchestrator
                        for flag in ['--pilot','--live-only']:
                            if flag in sys.argv: sys.argv.remove(flag)
                        if mode in {'pilot','live'}: sys.argv.append('--pilot' if mode == 'pilot' else '--live-only')
                        await evaluate(rag.api.app, rag.api.engine)
            except Exception as exc:
                write('assistant_semantic_router_eval_error.json', {'type': type(exc).__name__, 'message': str(exc)})
                import traceback; traceback.print_exc()
        rag.api.app.state.semantic_evaluation = asyncio.create_task(task())
    rag.api.app.router.add_event_handler('startup', startup)
    import uvicorn
    uvicorn.run(rag.api.app, host='127.0.0.1', port=8005, workers=1)
