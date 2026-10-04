import { create } from 'zustand'
import { ApiError, getToken, BORROW_STATE_CHANGED } from '../lib/api.ts'
import { assistantChat, uniqueIds, validWorkId, recentIds, MAX_SELECTION_MESSAGE, sanitizePageContext } from '../lib/assistant.ts'
import type { AssistantBook, AssistantChatMessage, AssistantPageContext, AssistantRequest } from '../lib/assistantTypes.ts'

type SelectedBook = Pick<AssistantBook, 'work_id' | 'title' | 'authors'>
interface SavedSession { owner: string | null; selected: SelectedBook[]; conversationId: string | null }
const STORAGE = 'luminar_assistant_session'
const currentOwner = (): string | null => {
  try { return getToken() ? JSON.parse(localStorage.getItem('luminar_user') || 'null')?.email ?? null : null } catch { return null }
}
function restore(): SavedSession {
  const empty = { owner: currentOwner(), selected: [], conversationId: null }
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE) || 'null')
    if (!saved || saved.owner !== empty.owner) return empty
    return { owner: empty.owner, conversationId: typeof saved.conversationId === 'string' && saved.conversationId.length <= 64 ? saved.conversationId : null,
      selected: Array.isArray(saved.selected) ? saved.selected.filter((book: SelectedBook) => typeof book?.work_id === 'string' && validWorkId(book.work_id)).filter((book: SelectedBook, i: number, all: SelectedBook[]) => all.findIndex(b => b.work_id === book.work_id) === i).slice(0, 4).map(minimalBook) : [] }
  } catch { return empty }
}
function minimalBook(book: SelectedBook): SelectedBook {
  return { work_id: book.work_id, title: typeof book.title === 'string' ? book.title : null, authors: typeof book.authors === 'string' || Array.isArray(book.authors) ? book.authors : null }
}
const initial = restore()
let sequence = 0
let controller: AbortController | null = null
let revision = 0
export type SendOptions = Pick<AssistantRequest, 'action' | 'pending_action_id'> & { selected_work_ids?: string[]; result_offset?: number }
interface AssistantState extends SavedSession {
  open: boolean; messages: AssistantChatMessage[]; recent: string[]; busy: boolean; startedAt: number | null; selectionNotice: string
  pagePath: string; pageContext: AssistantPageContext
  setOpen: (open: boolean) => void
  select: (book: SelectedBook) => boolean; unselect: (id: string) => void; clearSelection: () => void
  syncOwner: (owner: string | null) => void; resetConversation: () => void
  setPageContext: (path: string, context: AssistantPageContext) => void
  send: (message: string, context: AssistantPageContext, options?: SendOptions) => Promise<void>
}
function persist(state: SavedSession) {
  try { sessionStorage.setItem(STORAGE, JSON.stringify({ owner: state.owner, selected: state.selected.map(minimalBook), conversationId: state.conversationId })) } catch { /* Storage may be unavailable; memory still works. */ }
}
export const useAssistantStore = create<AssistantState>((set, get) => ({
  ...initial, open: false, messages: [], recent: [], busy: false, startedAt: null, selectionNotice: '', pagePath: '', pageContext: {},
  setOpen: open => set({ open }),
  select: book => {
    if (!validWorkId(book.work_id)) return false
    if (get().selected.some(b => b.work_id === book.work_id)) return true
    if (get().selected.length >= 4) { set({ selectionNotice: MAX_SELECTION_MESSAGE }); return false }
    set({ selected: [...get().selected, minimalBook(book)], selectionNotice: '' }); persist(get()); return true
  },
  unselect: id => { set({ selected: get().selected.filter(b => b.work_id !== id), selectionNotice: '' }); persist(get()) },
  clearSelection: () => { set({ selected: [], selectionNotice: '' }); persist(get()) },
  syncOwner: owner => {
    if (get().owner === owner) return
    revision++; controller?.abort(); controller = null
    set({ owner, selected: [], conversationId: null, messages: [], recent: [], busy: false, startedAt: null, selectionNotice: '', pageContext: {}, pagePath: '' }); persist(get())
  },
  resetConversation: () => {
    if (get().busy) return
    set({ conversationId: null, messages: [], recent: [] }); persist(get())
  },
  setPageContext: (path, context) => set({ pagePath: path, pageContext: sanitizePageContext(context) }),
  send: async (message, context, options = {}) => {
    message = message.trim()
    if (!message || message.length > 4000 || get().busy || !getToken()) return
    const snapshot = get()
    const request: AssistantRequest = {
      message, conversation_id: snapshot.conversationId, selected_work_ids: uniqueIds(options.selected_work_ids ?? snapshot.selected.map(b => b.work_id), 4),
      recent_work_ids: [...snapshot.recent], page_context: sanitizePageContext(context), action: options.action ?? null, pending_action_id: options.pending_action_id ?? null,
      ...(options.result_offset ? { result_offset: options.result_offset } : {}),
    }
    const version = revision, token = getToken(), startedAt = Date.now()
    controller = new AbortController()
    set({ busy: true, startedAt, messages: [...snapshot.messages, { id: ++sequence, kind: 'USER_TEXT', text: message }] })
    try {
      const response = await assistantChat(request, controller.signal)
      if (version !== revision || token !== getToken()) return
      set({ conversationId: response.conversation_id, recent: response.reading_list !== null
        ? recentIds(response.reading_list, [])
        : recentIds(response.books.length ? response.books : response.comparison?.books ?? [], get().recent),
        messages: [...get().messages, { id: ++sequence, kind: 'ASSISTANT_RESPONSE', response, latencyMs: Date.now() - startedAt }] })
      persist(get())
      if (options.action === 'CONFIRM_ACTION' && response.account && !response.errors.length) window.dispatchEvent(new Event(BORROW_STATE_CHANGED))
    } catch (error) {
      if (version !== revision || token !== getToken()) return
      const expired = error instanceof ApiError && error.status === 404 && Boolean(request.conversation_id)
      if (expired) { set({ conversationId: null, recent: [] }); persist(get()) }
      set({ messages: [...get().messages, { id: ++sequence, kind: expired ? 'SYSTEM_NOTICE' : 'ERROR',
        text: expired ? 'This assistant session expired. Starting a new conversation. Please send your request again.' : error instanceof Error ? error.message : 'The assistant could not complete this request.' }] })
    } finally {
      if (version === revision) { controller = null; set({ busy: false, startedAt: null }) }
    }
  },
}))
