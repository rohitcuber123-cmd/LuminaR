import assert from 'node:assert/strict'
import { test, beforeEach, afterEach } from 'node:test'
import { JSDOM } from 'jsdom'
import React from 'react'

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost:5173' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, sessionStorage: dom.window.sessionStorage, HTMLElement: dom.window.HTMLElement, Event: dom.window.Event, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
localStorage.setItem('luminar_token', 'test-session')
localStorage.setItem('luminar_user', JSON.stringify({ email: 'reader@test.invalid', role: 'GENERAL_USER' }))
const { render, screen, fireEvent, cleanup, act, waitFor } = await import('@testing-library/react')
const { default: userEvent } = await import('@testing-library/user-event')
const { MemoryRouter } = await import('react-router-dom')
const { AIChatWidget } = await import('../src/components/AIChatWidget.tsx')
const { BookSelectButton } = await import('../src/components/BookSelectButton.tsx')
const { AssistantTurn } = await import('../src/components/assistant/AssistantTurn.tsx')
const { useAssistantStore: store } = await import('../src/store/useAssistantStore.ts')
const { useAuthStore } = await import('../src/store/useAuthStore.ts')
const { useAssistantPageContext } = await import('../src/hooks/useAssistantPageContext.ts')
const { assistantChat, recentIds, MAX_SELECTION_MESSAGE } = await import('../src/lib/assistant.ts')
import type { AssistantResponse, AssistantRequest, AssistantBook } from '../src/lib/assistantTypes.ts'
const book = (id = 'OL1W'): AssistantBook => ({ work_id: id, title: `Book ${id}`, authors: 'An Author', subjects: ['Science'], average_rating: 4.2, available_copies: 2, total_copies: 3, shelf_location: 'A1', description: null })
const response = (patch: Partial<AssistantResponse> = {}): AssistantResponse => ({ conversation_id: 'conv-1', intent: 'GENERAL_LIBRARY_HELP', message: 'Verified answer.', books: [], comparison: null, recommendation_mode: null, seed_work_ids: [], availability: [], actions: [], clarification: null, pending_action: null, account: null, reading_list: null, rag: null, errors: [], has_more: false, result_offset: 0, explanation_available: false, ...patch })
const pending = { action_id: 'pending-1', type: 'RESERVE_BOOK' as const, work_id: 'OL1W', requires_confirmation: true, expires_at: new Date(Date.now() + 300000).toISOString(), enabled: false }
let calls: Array<{ url: string; body: AssistantRequest; headers: Headers }> = []
let next = response()
let fetcher: typeof fetch
beforeEach(() => {
  localStorage.setItem('luminar_token', 'test-session')
  localStorage.setItem('luminar_user', JSON.stringify({ email: 'reader@test.invalid', role: 'GENERAL_USER' }))
  act(() => {
    store.setState({ owner: 'reader@test.invalid', selected: [], conversationId: null, messages: [], recent: [], open: false, busy: false, startedAt: null, selectionNotice: '', pageContext: {}, pagePath: '' })
    useAuthStore.setState({ isAuthenticated: true, token: 'test-session', user: { email: 'reader@test.invalid', role: 'GENERAL_USER' } })
  })
  calls = []; next = response()
  fetcher = globalThis.fetch
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), body: JSON.parse(String(options.body)), headers: new Headers(options.headers) })
    return new Response(JSON.stringify(next), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }
})
afterEach(() => { cleanup(); globalThis.fetch = fetcher })
function mount(path = '/') { return render(<MemoryRouter initialEntries={[path]}><AIChatWidget /></MemoryRouter>) }
function open() { fireEvent.click(screen.getByRole('button', { name: 'Open LuminaR AI' })) }
async function submit(text: string) { fireEvent.change(screen.getByLabelText('Message LuminaR AI'), { target: { value: text } }); fireEvent.click(screen.getByRole('button', { name: 'Send message' })); await waitFor(() => assert.equal(store.getState().busy, false)) }
async function select(count: number) { await act(async () => { for (let i = 1; i <= count; i++) store.getState().select(book(`OL${i}W`)) }) }
function turn(data: AssistantResponse, onAction = () => {}, onChoice = () => {}) { return render(<MemoryRouter><AssistantTurn response={data} busy={false} pendingActive={true} now={Date.now()} onAction={onAction} onChoice={onChoice} /></MemoryRouter>) }

test('repair reading-list selection uses the shared tray and clears stale references on empty list', async () => {
  next = response({ intent: 'USER_READING_LIST', reading_list: [book('OL2W')] })
  mount(); open(); await submit('Show my reading list')
  fireEvent.click(screen.getByRole('button', { name: 'Select Book OL2W' }))
  assert.deepEqual(store.getState().selected.map(b => b.work_id), ['OL2W'])
  assert.deepEqual(store.getState().recent, ['OL2W'])
  next = response({ intent: 'USER_READING_LIST', reading_list: [] })
  await submit('Show my reading list')
  assert.deepEqual(store.getState().recent, [])
})

test('repair Show More sends dedicated action, original text and next offset without current tray', async () => {
  next = response({ intent: 'SEARCH_BOOKS', books: [book()], has_more: true, result_offset: 10 })
  mount(); open(); await submit('Find books about AI'); await select(2)
  next = response({ intent: 'SEARCH_BOOKS', books: [book('OL3W')], result_offset: 11 })
  fireEvent.click(screen.getByRole('button', { name: 'Show more results' }))
  await waitFor(() => assert.equal(store.getState().busy, false))
  assert.equal(calls[1].body.action, 'SHOW_MORE')
  assert.equal(calls[1].body.message, 'Find books about AI')
  assert.equal(calls[1].body.result_offset, 11)
  assert.deepEqual(calls[1].body.selected_work_ids, [])
  assert.equal((screen.getByRole('button', { name: 'Show more results' }) as HTMLButtonElement).disabled, true)
})

test('repair lazy explanation buttons send typed actions and no replacement tray seeds', async () => {
  next = response({ intent: 'RECOMMEND_FROM_BOOK', books: [book()], recommendation_mode: 'SINGLE_SELECTED_BOOK', seed_work_ids: ['OL2W'], explanation_available: true })
  mount(); open(); await submit('Recommend'); await select(3)
  fireEvent.click(screen.getByRole('button', { name: 'Why these recommendations?' }))
  await waitFor(() => assert.equal(store.getState().busy, false))
  assert.equal(calls[1].body.action, 'EXPLAIN_RECOMMENDATION')
  assert.deepEqual(calls[1].body.selected_work_ids, [])
  next = response({ intent: 'COMPARE_BOOKS', comparison: { books: [book(), book('OL2W')], requested_fields: ['authors'], missing_fields: [] }, explanation_available: true })
  await submit('Compare')
  fireEvent.click(screen.getByRole('button', { name: 'Explain comparison' }))
  await waitFor(() => assert.equal(store.getState().busy, false))
  assert.equal(calls.at(-1)?.body.action, 'EXPLAIN_COMPARISON')
  assert.deepEqual(calls.at(-1)?.body.selected_work_ids, [])
})

test('test_assistant_drawer_opens', () => { mount(); open(); assert.ok(screen.getByRole('dialog', { name: 'LuminaR AI' })) })
test('test_message_submission', async () => { mount(); open(); await submit('Find AI books'); assert.equal(calls.length, 1); assert.equal(calls[0].body.message, 'Find AI books'); assert.ok(screen.getByText('Verified answer.')) })
test('test_bearer_auth_uses_existing_client', async () => { await assistantChat({ message: 'Hi', selected_work_ids: [], recent_work_ids: [], page_context: {} }); assert.equal(calls[0].url, '/rag-api/assistant/chat'); assert.equal(calls[0].headers.get('Authorization'), 'Bearer test-session'); assert.equal('user_id' in calls[0].body, false) })
test('test_conversation_id_retained', async () => { mount(); open(); await submit('Hi'); await submit('More'); assert.equal(calls[1].body.conversation_id, 'conv-1') })
test('test_selected_work_ids_sent', async () => { await select(2); mount(); open(); await submit('recommend something'); assert.deepEqual(calls[0].body.selected_work_ids, ['OL1W', 'OL2W']) })
test('test_recent_work_ids_bounded_to_20', () => { const books = Array.from({ length: 30 }, (_, i) => book(`OL${i}W`)); assert.equal(recentIds(books, ['OL1W']).length, 20); assert.equal(new Set(recentIds(books, [])).size, 20) })
test('test_select_book', () => { render(<BookSelectButton book={book()} />); fireEvent.click(screen.getByRole('button', { name: 'Select Book OL1W' })); assert.equal(store.getState().selected[0].work_id, 'OL1W'); assert.equal(screen.getByRole('button').getAttribute('aria-pressed'), 'true') })
test('test_unselect_book', async () => { await select(1); render(<BookSelectButton book={book()} />); fireEvent.click(screen.getByRole('button')); assert.equal(store.getState().selected.length, 0) })
test('test_clear_selection', async () => { await select(2); mount(); open(); fireEvent.click(screen.getByRole('button', { name: 'Clear', exact: true })); assert.equal(store.getState().selected.length, 0) })
test('test_max_four_selected', async () => { await select(4); assert.equal(store.getState().selected.length, 4); assert.equal(store.getState().select(book('OL1W')), true); assert.equal(store.getState().selected.length, 4) })
test('test_fifth_selection_rejected', async () => { await select(4); mount(); open(); await act(async () => { assert.equal(store.getState().select(book('OL5W')), false) }); assert.ok(screen.getByText(MAX_SELECTION_MESSAGE)); assert.equal(store.getState().selected.length, 4) })
test('test_selected_tray_rendering', async () => { await select(2); mount(); open(); assert.ok(screen.getByRole('region', { name: 'Selected books' })); assert.ok(screen.getByRole('button', { name: 'Remove Book OL1W from selection' })) })
test('test_zero_selected_recommend_button', () => { mount(); open(); assert.ok(screen.getByRole('button', { name: 'Recommend', exact: true })); assert.equal(screen.queryByRole('button', { name: 'Compare with AI' }), null) })
test('test_one_selected_recommend_similar_button', async () => { await select(1); mount(); open(); assert.equal(screen.getAllByRole('button', { name: 'Recommend Similar' }).length, 2) })
test('test_two_selected_compare_button', async () => { await select(2); mount(); open(); assert.ok(screen.getByRole('button', { name: 'Compare with AI' })) })
test('test_multiple_selected_recommend_from_these_button', async () => { await select(4); mount(); open(); assert.equal(screen.getAllByRole('button', { name: 'Recommend From These' }).length, 2) })
test('test_compare_requires_two', async () => { await select(1); mount(); open(); assert.equal(screen.queryByRole('button', { name: 'Compare with AI' }), null) })
test('test_compare_sends_selected_work_ids', async () => { await select(2); mount(); open(); fireEvent.click(screen.getByRole('button', { name: 'Compare with AI' })); await waitFor(() => assert.equal(store.getState().busy, false)); assert.deepEqual(calls[0].body.selected_work_ids, ['OL1W', 'OL2W']); assert.match(calls[0].body.message, /Compare/) })
test('compare tray sends structured action', async () => { await select(2); mount(); open(); fireEvent.click(screen.getByRole('button', { name: 'Compare with AI' })); await waitFor(() => assert.equal(store.getState().busy, false)); assert.equal(calls[0].body.action, 'COMPARE') })
test('recommend buttons send selection-specific structured actions', async () => {
  for (const [count, expected] of [[0, 'RECOMMEND'], [1, 'RECOMMEND_SIMILAR'], [3, 'RECOMMEND_FROM_SELECTION']] as const) {
    await act(async () => { store.getState().clearSelection(); store.getState().setOpen(false) }); await select(count); const view = mount(); open()
    fireEvent.click(screen.getAllByRole('button', { name: count === 0 ? 'Recommend' : count === 1 ? 'Recommend Similar' : 'Recommend From These', exact: true })[0])
    await waitFor(() => assert.equal(store.getState().busy, false)); assert.equal(calls.at(-1)?.body.action, expected); view.unmount()
  }
})
test('available now sends structured action', async () => { mount(); open(); fireEvent.click(screen.getByRole('button', { name: 'Available now' })); await waitFor(() => assert.equal(store.getState().busy, false)); assert.equal(calls[0].body.action, 'AVAILABLE_NOW') })
test('typed text has no explicit action', async () => { mount(); open(); await submit('Compare these two'); assert.equal(calls[0].body.action, null) })
test('card availability action binds clicked canonical ID', async () => {
  next = response({ books: [book()], actions: [{ type: 'CHECK_AVAILABILITY', work_id: 'OL1W' }] }); mount(); open(); await submit('Find books')
  fireEvent.click(screen.getByRole('button', { name: 'Check Availability' })); await waitFor(() => assert.equal(store.getState().busy, false))
  assert.equal(calls.at(-1)?.body.action, 'CHECK_AVAILABILITY'); assert.deepEqual(calls.at(-1)?.body.selected_work_ids, ['OL1W'])
})
test('test_recommend_sends_selected_work_ids', async () => { await select(3); mount(); open(); fireEvent.click(screen.getAllByRole('button', { name: 'Recommend From These' })[0]); await waitFor(() => assert.equal(store.getState().busy, false)); assert.deepEqual(calls[0].body.selected_work_ids, ['OL1W', 'OL2W', 'OL3W']) })
test('test_book_results_render', () => { turn(response({ intent: 'SEARCH_BOOKS', books: [book()], actions: [{ type: 'VIEW_BOOK', work_id: 'OL1W' }, { type: 'SELECT_BOOK', work_id: 'OL1W' }] })); assert.ok(screen.getByRole('article', { name: 'Book OL1W' })); assert.equal(screen.getByRole('link', { name: 'View book' }).getAttribute('href'), '/book/OL1W') })
test('test_recommendation_mode_render', () => { const modes = ['PERSONALIZED_EXISTING_FORMULA', 'SINGLE_SELECTED_BOOK', 'MULTI_SELECTED_BOOKS', 'EXPLICIT_BOOK_SEED'] as const; for (const mode of modes) { const view = turn(response({ recommendation_mode: mode, books: [book()] })); assert.ok(screen.getByRole('heading', { level: 3 })); view.unmount() } })
test('test_availability_render', () => { turn(response({ books: [book()], availability: [{ work_id: 'OL1W', available: false, available_copies: 0, total_copies: 3 }] })); assert.ok(screen.getByText('Unavailable')); assert.equal(screen.queryByText('Available · 2 copies'), null) })
test('test_dynamic_comparison_render', () => { turn(response({ comparison: { books: [book(), book('OL2W')], requested_fields: [], missing_fields: [] } })); assert.ok(screen.getByRole('table')); assert.ok(screen.getByRole('rowheader', { name: 'Shelf location' })); assert.equal(screen.queryByRole('rowheader', { name: 'Page count' }), null) })
test('test_missing_comparison_fields', () => { turn(response({ comparison: { books: [book(), book('OL2W')], requested_fields: ['page_count'], missing_fields: ['page_count'] } })); assert.ok(screen.getByText(/Not recorded: Page count/)) })
test('test_clarification_render', () => { turn(response({ intent: 'CLARIFICATION', clarification: { reason: 'Which edition?', choices: [book(), book('OL2W')] } })); assert.ok(screen.getByText('Which edition?')); assert.equal(screen.getAllByRole('button', { name: /Continue with/ }).length, 2) })
test('test_clarification_choice_select', async () => { next = response({ intent: 'CLARIFICATION', clarification: { reason: 'Which?', choices: [book(), book('OL2W')] } }); mount(); open(); await submit('Is Book available?'); next = response(); fireEvent.click(screen.getByRole('button', { name: /Continue with Book OL2W,/ })); await waitFor(() => assert.equal(store.getState().busy, false)); assert.deepEqual(calls[1].body.selected_work_ids, ['OL2W']); assert.equal(calls[1].body.conversation_id, 'conv-1') })
test('test_quick_find_book', () => { mount(); open(); fireEvent.click(screen.getByRole('button', { name: 'Find a book' })); assert.equal((screen.getByLabelText('Message LuminaR AI') as HTMLTextAreaElement).value, 'Find books about '); assert.equal(document.activeElement, screen.getByLabelText('Message LuminaR AI')); assert.equal(calls.length, 0) })
test('test_quick_recommend', async () => { mount(); open(); fireEvent.click(screen.getByRole('button', { name: 'Recommend', exact: true })); await waitFor(() => assert.equal(store.getState().busy, false)); assert.deepEqual(calls[0].body.selected_work_ids, []) })
test('test_quick_available_now', async () => { mount(); open(); fireEvent.click(screen.getByRole('button', { name: 'Available now' })); await waitFor(() => assert.equal(store.getState().busy, false)); assert.equal(calls[0].body.message, 'Show me books available now.') })
test('test_account_result_render', () => { turn(response({ intent: 'USER_FEES', account: { total_unpaid: 5, fines: [{ amount: 5, status: 'UNPAID', work_id: 'OL1W', title: 'Book OL1W', user_id: 99 }] } })); assert.ok(screen.getByText('Unpaid fees:', { exact: false })); assert.ok(screen.getByText('UNPAID')); assert.equal(screen.queryByText('99'), null) })
test('test_rag_result_render', () => { turn(response({ intent: 'DOCUMENT_QUESTION', rag: { answer: 'Source answer.', sources: [{ filename: 'guide.pdf', page: 3 }] } })); assert.ok(screen.getByText('Source answer.')); fireEvent.click(screen.getByText('Sources (1)')); assert.ok(screen.getByText('guide.pdf · Page 3')) })
test('test_pending_action_render', () => { turn(response({ pending_action: pending, books: [book()] })); assert.ok(screen.getByRole('button', { name: 'Confirm reservation' })); assert.ok(screen.getByText('Library actions are currently disabled.')) })
test('test_confirm_action_request', async () => { next = response({ pending_action: pending, books: [book()] }); mount(); open(); await submit('Reserve this book'); next = response({ errors: [{ code: 'MUTATIONS_DISABLED', service: 'assistant', message: 'Disabled' }] }); fireEvent.click(screen.getByRole('button', { name: 'Confirm reservation' })); await waitFor(() => assert.equal(store.getState().busy, false)); assert.equal(calls[1].body.action, 'CONFIRM_ACTION'); assert.equal(calls[1].body.pending_action_id, 'pending-1'); assert.equal(calls[1].url, '/rag-api/assistant/chat') })
test('test_cancel_action_request', async () => { next = response({ pending_action: pending }); mount(); open(); await submit('Reserve this book'); next = response(); fireEvent.click(screen.getByRole('button', { name: 'Cancel', exact: true })); await waitFor(() => assert.equal(store.getState().busy, false)); assert.equal(calls[1].body.action, 'CANCEL_ACTION'); assert.equal(calls[1].body.pending_action_id, 'pending-1') })
test('test_mutations_disabled_render', () => { turn(response({ errors: [{ code: 'MUTATIONS_DISABLED', service: 'assistant', message: 'Disabled' }] })); assert.ok(screen.getByText('Library actions are currently disabled. No action was performed.')) })
test('test_errors_array_render', () => { turn(response({ errors: [{ code: 'TOOL_UNAVAILABLE', service: 'search', message: 'Search unavailable.' }] })); assert.ok(screen.getByText('Search unavailable.')) })
test('test_nonfatal_error_does_not_hide_books', () => { turn(response({ books: [book()], errors: [{ code: 'QWEN_UNAVAILABLE', service: 'qwen', message: 'Explanation unavailable.' }] })); assert.ok(screen.getByRole('article', { name: 'Book OL1W' })); assert.ok(screen.getByText('Explanation unavailable.')) })
test('test_long_request_loading_state', () => { mount(); open(); act(() => store.setState({ busy: true, startedAt: Date.now() - 20000 })); assert.ok(screen.getByText(/Working on that/)); assert.ok(screen.getByText('This can take a little while on the local AI model.')) })
test('test_duplicate_send_disabled', async () => { let finish: (r: Response) => void = () => {}; globalThis.fetch = async (url, options) => { calls.push({ url: String(url), body: JSON.parse(String(options?.body)), headers: new Headers(options?.headers) }); return new Promise(resolve => { finish = resolve }) }; mount(); open(); fireEvent.change(screen.getByLabelText('Message LuminaR AI'), { target: { value: 'Hi' } }); fireEvent.click(screen.getByRole('button', { name: 'Send message' })); assert.equal((screen.getByRole('button', { name: 'Send message' }) as HTMLButtonElement).disabled, true); await act(async () => store.getState().send('Hi', {})); assert.equal(calls.length, 1); await act(async () => finish(new Response(JSON.stringify(response())))); await waitFor(() => assert.equal(store.getState().busy, false)) })
test('test_page_context_book_id', async () => { mount('/book/OL1W'); open(); await submit('Is this available?'); assert.deepEqual(calls[0].body.page_context, { work_id: 'OL1W' }) })
test('test_page_context_work_ids', async () => { act(() => store.getState().setPageContext('/search?q=AI', { work_ids: ['OL1W', 'OL2W'] })); mount('/search?q=AI'); open(); await submit('Compare the first two'); assert.deepEqual(calls[0].body.page_context.work_ids, ['OL1W', 'OL2W']) })
test('test_page_context_document_id', async () => { function Document() { useAssistantPageContext({ document_id: 'doc-123' }); return <AIChatWidget /> }; render(<MemoryRouter initialEntries={['/llm']}><Document /></MemoryRouter>); open(); await submit('What does this PDF say?'); assert.deepEqual(calls[0].body.page_context, { document_id: 'doc-123' }); assert.equal(calls.length, 1) })
test('test_expired_conversation_handling', async () => { act(() => store.setState({ conversationId: 'expired' })); globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Conversation not found or expired.' }), { status: 404 }); mount(); open(); await submit('Hi'); assert.equal(store.getState().conversationId, null); assert.ok(screen.getByText(/This assistant session expired/)) })
test('test_keyboard_accessibility_for_selection', async () => { render(<BookSelectButton book={book()} />); const user = userEvent.setup({ document }); await user.tab(); assert.equal(document.activeElement, screen.getByRole('button')); await user.keyboard('{Enter}'); assert.equal(store.getState().selected.length, 1) })
test('session closes and reopens without losing conversation or selection', async () => { await select(1); mount(); open(); await submit('Hi'); fireEvent.click(screen.getByRole('button', { name: 'Close LuminaR AI' })); open(); assert.ok(screen.getByText('Verified answer.')); assert.equal(store.getState().conversationId, 'conv-1'); assert.equal(store.getState().selected.length, 1); const saved = JSON.parse(sessionStorage.getItem('luminar_assistant_session') || '{}'); assert.equal('messages' in saved, false); assert.equal('token' in saved, false) })
test('account change clears private turns and pending confirmations', async () => { next = response({ account: { total_unpaid: 20 }, pending_action: pending }); mount(); open(); await submit('Fees'); await act(async () => store.getState().syncOwner('different@test.invalid')); assert.equal(store.getState().messages.length, 0); assert.equal(store.getState().conversationId, null) })
test('recommend similar uses one-request selection without overwriting tray', async () => { await select(2); next = response({ books: [book('OL3W')], actions: [{ type: 'RECOMMEND_SIMILAR', work_id: 'OL3W' }] }); mount(); open(); await submit('Search'); next = response(); fireEvent.click(screen.getAllByRole('button', { name: 'Recommend Similar' })[0]); await waitFor(() => assert.equal(store.getState().busy, false)); assert.deepEqual(calls[1].body.selected_work_ids, ['OL3W']); assert.deepEqual(store.getState().selected.map(b => b.work_id), ['OL1W', 'OL2W']) })
test('unknown availability and zero rating are rendered without inventions', () => { turn(response({ books: [{ ...book(), available_copies: null, total_copies: null, average_rating: 0 }], availability: [{ work_id: 'OL1W', available: null, available_copies: null, total_copies: null }] })); assert.ok(screen.getByText('Availability unknown')); assert.equal(screen.queryByText('★ 0.0'), null) })
test('old pending actions are unusable after another turn', async () => { next = response({ pending_action: pending }); mount(); open(); await submit('Reserve'); next = response(); await submit('Hi'); assert.equal((screen.getByRole('button', { name: 'Confirm reservation' }) as HTMLButtonElement).disabled, true) })
test('authenticated API 401 follows existing session expiry behavior', async () => { let expired = false; const listener = () => { expired = true }; window.addEventListener('luminar-session-expired', listener); globalThis.fetch = async () => new Response('{}', { status: 401 }); await assert.rejects(assistantChat({ message: 'Hi', selected_work_ids: [], recent_work_ids: [], page_context: {} }), /session has expired/); assert.equal(expired, true); assert.equal(localStorage.getItem('luminar_token'), null); window.removeEventListener('luminar-session-expired', listener) })
test('generic recommendation empty state has no fabricated books', () => { turn(response({ intent: 'RECOMMEND_BOOKS', recommendation_mode: 'PERSONALIZED_EXISTING_FORMULA' })); assert.ok(screen.getByText('No personalized recommendations are available yet.')); assert.equal(screen.queryByRole('article'), null) })
test('request context is a snapshot when selection changes during generation', async () => { await select(1); let finish: (r: Response) => void = () => {}; globalThis.fetch = async (url, options) => { calls.push({ url: String(url), body: JSON.parse(String(options?.body)), headers: new Headers(options?.headers) }); return new Promise(resolve => { finish = resolve }) }; const sending = store.getState().send('Recommend', {}); await act(async () => store.getState().select(book('OL2W'))); assert.deepEqual(calls[0].body.selected_work_ids, ['OL1W']); await act(async () => finish(new Response(JSON.stringify(response())))); await sending })
test('assistant dialog passes axe semantic accessibility checks', async () => {
  await select(2); mount(); open()
  const { default: axe } = await import('axe-core')
  const result = await axe.run(screen.getByRole('dialog'), { rules: { 'color-contrast': { enabled: false } } })
  assert.deepEqual(result.violations.map(item => item.id), [])
})
test('structured comparison and confirmation pass axe semantic checks', async () => {
  turn(response({ books: [book(), book('OL2W')], comparison: { books: [book(), book('OL2W')], requested_fields: [], missing_fields: ['page_count'] }, pending_action: pending }))
  const { default: axe } = await import('axe-core')
  const result = await axe.run(document.body, { rules: { 'color-contrast': { enabled: false }, 'region': { enabled: false } } })
  assert.deepEqual(result.violations.map(item => item.id), [])
})
test('recent structured result IDs retain order in later request payloads', async () => {
  next = response({ books: Array.from({ length: 20 }, (_, i) => book(`OL${i}W`)) })
  mount(); open(); await submit('Search')
  next = response({ books: [book('OL25W'), book('OL1W')] })
  await submit('More'); next = response(); await submit('Availability')
  assert.equal(calls[2].body.recent_work_ids.length, 20)
  assert.deepEqual(calls[2].body.recent_work_ids.slice(0, 3), ['OL25W', 'OL1W', 'OL0W'])
})
test('late response from a previous identity never restores private account data', async () => {
  let finish: (r: Response) => void = () => {}
  globalThis.fetch = async () => new Promise(resolve => { finish = resolve })
  const sending = store.getState().send('Fees', {})
  store.getState().syncOwner('another@test.invalid')
  finish(new Response(JSON.stringify(response({ account: { total_unpaid: 100 } }))))
  await sending
  assert.equal(store.getState().messages.length, 0)
  assert.equal(store.getState().conversationId, null)
  assert.equal(store.getState().busy, false)
})

// ─── Phase 3/4: Reading list UI ────────────────────────────────────────────

test('reading list empty state renders correctly', () => {
  turn(response({ intent: 'USER_READING_LIST', reading_list: [], message: 'Your reading list is empty.' }))
  assert.ok(screen.getByText('Your reading list is empty.'))
})

test('reading list items render with remove button', () => {
  const item: AssistantBook = { work_id: 'OL1W', title: 'Dracula', authors: 'Bram Stoker', available_copies: 0, total_copies: 2 }
  turn(response({ intent: 'USER_READING_LIST', reading_list: [item], message: 'Your reading list has 1 book.' }))
  assert.ok(screen.getByRole('article'), 'reading list article')
  assert.ok(screen.getByRole('button', { name: 'Remove Dracula from reading list' }))
})

test('add to reading list success renders confirmation', () => {
  turn(response({ intent: 'ADD_TO_READING_LIST', books: [book()], message: 'Added 1 book to your reading list.' }))
  assert.ok(screen.getByText('Book OL1W added to your reading list.'))
})

test('remove from reading list success renders confirmation', () => {
  turn(response({ intent: 'REMOVE_FROM_READING_LIST', books: [book()], message: 'Removed from your reading list.' }))
  assert.ok(screen.getByText('Book OL1W removed from your reading list.'))
})

test('reading list quick action button sends USER_READING_LIST action', async () => {
  mount(); open()
  fireEvent.click(screen.getByRole('button', { name: 'My reading list' }))
  await waitFor(() => assert.equal(store.getState().busy, false))
  assert.equal(calls[0].body.action, 'USER_READING_LIST')
})

test('add to reading list icon button sends ADD_TO_READING_LIST', async () => {
  next = response({
    intent: 'SEARCH_BOOKS', books: [book()],
    actions: [{ type: 'ADD_TO_READING_LIST', work_id: 'OL1W' }],
  })
  mount(); open(); await submit('Find books')
  next = response()
  fireEvent.click(screen.getByRole('button', { name: 'Add Book OL1W to reading list' }))
  await waitFor(() => assert.equal(store.getState().busy, false))
  assert.equal(calls.at(-1)?.body.action, 'ADD_TO_READING_LIST')
  assert.deepEqual(calls.at(-1)?.body.selected_work_ids, ['OL1W'])
})

// ─── Phase 5/6: Available alternatives ─────────────────────────────────────

test('unavailable book shows find available similar button', () => {
  turn(response({
    intent: 'SEARCH_BOOKS', books: [book()],
    availability: [{ work_id: 'OL1W', available: false, available_copies: 0, total_copies: 2 }],
    actions: [{ type: 'RECOMMEND_AVAILABLE_SIMILAR', work_id: 'OL1W' }],
  }))
  assert.ok(screen.getByRole('button', { name: 'Find Available Similar' }))
})

test('unavailable book panel does not appear for available book', () => {
  turn(response({
    intent: 'SEARCH_BOOKS', books: [book()],
    availability: [{ work_id: 'OL1W', available: true, available_copies: 2, total_copies: 3 }],
    actions: [],
  }))
  assert.equal(screen.queryByText('This book is currently unavailable.'), null)
})

test('find available similar action sends RECOMMEND_AVAILABLE_SIMILAR', async () => {
  next = response({
    intent: 'SEARCH_BOOKS', books: [book()],
    availability: [{ work_id: 'OL1W', available: false, available_copies: 0, total_copies: 2 }],
    actions: [{ type: 'RECOMMEND_AVAILABLE_SIMILAR', work_id: 'OL1W' }],
  })
  mount(); open(); await submit('Find books')
  next = response()
  fireEvent.click(screen.getByRole('button', { name: 'Find Available Similar' }))
  await waitFor(() => assert.equal(store.getState().busy, false))
  assert.equal(calls.at(-1)?.body.action, 'RECOMMEND_AVAILABLE_SIMILAR')
  assert.deepEqual(calls.at(-1)?.body.selected_work_ids, ['OL1W'])
})

// ─── Phase 7/8: Explain buttons ────────────────────────────────────────────

test('why these recommendations button appears when explanation_available', () => {
  turn(response({
    intent: 'RECOMMEND_BOOKS', recommendation_mode: 'SINGLE_SELECTED_BOOK',
    seed_work_ids: ['OL1W'], books: [book('OL2W')], explanation_available: true,
  }))
  assert.ok(screen.getByRole('button', { name: 'Why these recommendations?' }))
})

test('explain button does not appear without explanation_available', () => {
  turn(response({
    intent: 'RECOMMEND_BOOKS', recommendation_mode: 'PERSONALIZED_EXISTING_FORMULA',
    books: [book()], explanation_available: false,
  }))
  assert.equal(screen.queryByRole('button', { name: 'Why these recommendations?' }), null)
})

test('explain comparison button appears when explanation_available on comparison', () => {
  turn(response({
    intent: 'COMPARE_BOOKS',
    comparison: { books: [book(), book('OL2W')], requested_fields: [], missing_fields: [] },
    explanation_available: true,
  }))
  assert.ok(screen.getByRole('button', { name: 'Explain comparison' }))
})

// ─── Phase 10: Show more ───────────────────────────────────────────────────

test('show more button appears when has_more is true', () => {
  turn(response({ intent: 'SEARCH_BOOKS', books: [book()], has_more: true }))
  assert.ok(screen.getByRole('button', { name: 'Show more results' }))
})

test('show more button does not appear when has_more is false', () => {
  turn(response({ intent: 'SEARCH_BOOKS', books: [book()], has_more: false }))
  assert.equal(screen.queryByRole('button', { name: 'Show more results' }), null)
})

test('show more click from widget sends result_offset', async () => {
  // First response has more results
  next = response({ intent: 'SEARCH_BOOKS', books: [book()], has_more: true, result_offset: 0 })
  mount(); open(); await submit('Find books')
  next = response()
  // Simulate the show-more action by sending with a positive offset
  const msg = store.getState().messages.at(-1)
  assert.ok(msg?.kind === 'ASSISTANT_RESPONSE', 'Expected assistant response message')
  const prev = msg.response
  const offset = (prev.result_offset ?? 0) + (prev.books?.length ?? 1)
  await act(async () => { await store.getState().send('Show more', {}, { result_offset: offset }) })
  await waitFor(() => assert.equal(store.getState().busy, false))
  const lastCall = calls.at(-1)
  assert.equal(typeof lastCall?.body.result_offset, 'number')
  assert.ok((lastCall?.body.result_offset ?? 0) > 0)
})


// ─── Phase 22: Accessibility (reading list section) ─────────────────────────

test('reading list section passes axe checks', async () => {
  const item: AssistantBook = { work_id: 'OL1W', title: 'Dracula', authors: 'Bram Stoker', available_copies: 0, total_copies: 2 }
  turn(response({ intent: 'USER_READING_LIST', reading_list: [item], message: 'Your reading list has 1 book.' }))
  const { default: axe } = await import('axe-core')
  const result = await axe.run(document.body, { rules: { 'color-contrast': { enabled: false }, 'region': { enabled: false } } })
  assert.deepEqual(result.violations.map(v => v.id), [])
})

