import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { MessageCircle, Search, Send, Sparkles, X, BookOpen } from 'lucide-react'
import { useAssistantStore } from '../store/useAssistantStore'
import { useAuthStore } from '../store/useAuthStore'
import { recommendLabel, recommendAction } from '../lib/assistant'
import type { AssistantAction, AssistantBook, AssistantPageContext } from '../lib/assistantTypes'
import { AssistantTurn } from './assistant/AssistantTurn'

export function SelectedBooksTray({ onSend, busy }: { onSend: (message: string, options?: Parameters<ReturnType<typeof useAssistantStore.getState>['send']>[2]) => void; busy: boolean }) {
  const { selected, unselect, clearSelection, selectionNotice } = useAssistantStore()
  if (!selected.length && !selectionNotice) return null
  return <section aria-label="Selected books" className="mb-3 border border-line bg-panel p-2.5">
    <div className="flex items-center justify-between"><h3 className="font-display text-xs">Selected books · {selected.length}/4</h3>
      {!!selected.length && <button className="assistant-button" onClick={clearSelection}>Clear</button>}</div>
    <ul className="mt-2 flex max-h-24 flex-wrap gap-1.5 overflow-y-auto">{selected.map(book => <li key={book.work_id} className="flex min-w-0 max-w-full items-center gap-1 border border-line bg-paper pl-2 text-xs">
      <span className="max-w-44 truncate" title={book.title || book.work_id}>{book.title || book.work_id}</span>
      <button className="assistant-icon-button" aria-label={`Remove ${book.title || book.work_id} from selection`} onClick={() => unselect(book.work_id)}><X size={12} /></button>
    </li>)}</ul>
    <div className="mt-2 flex flex-wrap gap-2">
      {selected.length >= 2 && <button disabled={busy} className="assistant-button" onClick={() => onSend('Compare these books', { action: 'COMPARE' })}>Compare with AI</button>}
      {!!selected.length && <button disabled={busy} className="assistant-button" onClick={() => onSend('Recommend', { action: recommendAction(selected.length) })}>{recommendLabel(selected.length)}</button>}
    </div>
    {selectionNotice && <p role="status" className="mt-2 text-xs text-brand">{selectionNotice}</p>}
  </section>
}

export function AIChatWidget() {
  const state = useAssistantStore()
  const authenticated = useAuthStore(s => s.isAuthenticated)
  const { pathname, search } = useLocation()
  const navigate = useNavigate()
  const [input, setInput] = useState('')
  const [now, setNow] = useState(() => Date.now())
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const launcherRef = useRef<HTMLButtonElement>(null)
  const historyRef = useRef<HTMLDivElement>(null)
  const pathKey = pathname + search
  const bookMatch = pathname.match(/^\/book\/([A-Za-z0-9_-]+)(?:\/read)?$/)
  const context: AssistantPageContext = state.pagePath === pathKey ? state.pageContext : bookMatch ? { work_id: bookMatch[1] } : {}
  useEffect(() => { if (state.open) inputRef.current?.focus() }, [state.open])
  useEffect(() => {
    if (!state.open) return
    const pane = historyRef.current
    if (pane) pane.scrollTo?.({ top: pane.scrollHeight, behavior: 'smooth' })
  }, [state.open, state.messages.length, state.busy])
  useEffect(() => {
    if (!state.open) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [state.open])
  const close = () => { state.setOpen(false); window.setTimeout(() => launcherRef.current?.focus(), 0) }
  const send = (message: string, options?: Parameters<typeof state.send>[2]) => { if (!state.busy && authenticated) { setInput(''); void state.send(message, context, options) } }
  const onAction = (action: AssistantAction, book?: AssistantBook) => {
    const id = action.work_id || book?.work_id
    switch (action.type) {
      case 'VIEW_BOOK': if (id) navigate(`/book/${encodeURIComponent(id)}`); break
      case 'SELECT_BOOK': if (book) state.select(book); break
      case 'UNSELECT_BOOK': if (id) state.unselect(id); break
      case 'COMPARE':
        if (book && !state.select(book)) break
        if (useAssistantStore.getState().selected.length >= 2) send('Compare these books', { action: 'COMPARE' })
        else inputRef.current?.focus()
        break
      case 'RECOMMEND_SIMILAR': if (id) send('Recommend', { action: 'RECOMMEND_SIMILAR', selected_work_ids: [id] }); break
      case 'RECOMMEND_FROM_SELECTION': send('Recommend', { action: 'RECOMMEND_FROM_SELECTION' }); break
      case 'RECOMMEND_AVAILABLE_SIMILAR': if (id) send('Show available alternatives', { action: 'RECOMMEND_AVAILABLE_SIMILAR', selected_work_ids: [id] }); break
      case 'CHECK_AVAILABILITY': if (id) send('Is this book available?', { action: 'CHECK_AVAILABILITY', selected_work_ids: [id] }); break
      case 'RECOMMEND': send('Recommend', { action: 'RECOMMEND' }); break
      case 'AVAILABLE_NOW': send('Show me books available now.', { action: 'AVAILABLE_NOW' }); break
      case 'ADD_TO_READING_LIST':
        if (id) send('Add this to my reading list', { action: 'ADD_TO_READING_LIST', selected_work_ids: [id] }); break
      case 'REMOVE_FROM_READING_LIST':
        if (id) send('Remove from reading list', { action: 'REMOVE_FROM_READING_LIST', selected_work_ids: [id] }); break
      case 'SHOW_MORE': {
        const lastMsg = state.messages.at(-1)
        if (lastMsg?.kind === 'ASSISTANT_RESPONSE') {
          const prev = lastMsg.response
          send('Show more', { action: prev.intent as Parameters<typeof send>[2] extends { action?: infer A } ? A : never,
            result_offset: (prev.result_offset ?? 0) + (prev.books?.length ?? 10) } as Parameters<typeof send>[2])
        }
        break
      }
      case 'BORROW': case 'RESERVE': case 'RETURN':
        if (id) send(`${action.type.toLowerCase()} this book`, { selected_work_ids: [id] })
        break
      case 'CONFIRM_ACTION': case 'CANCEL_ACTION':
        send(action.type === 'CONFIRM_ACTION' ? 'Confirm' : 'Cancel', { action: action.type, pending_action_id: action.action_id })
        break
    }
  }

  const lastMessage = state.messages.at(-1)
  return <>
    {state.open && <div role="dialog" aria-modal="false" aria-labelledby="luminar-ai-title" className="assistant-drawer" onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); close() } }}>
      <div className="h-[3px] shrink-0 bg-brand" />
      <header className="flex shrink-0 items-center justify-between border-b border-line px-5 py-4">
        <div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center bg-brand text-paper"><Sparkles size={18} /></div>
          <div><h2 id="luminar-ai-title" className="font-display text-sm">Lumina<span className="text-brand">R</span> AI</h2><p className="mt-1 text-xs text-ink-soft">Library intelligence</p></div></div>
        <div className="flex items-center gap-1"><button className="assistant-button" disabled={state.busy} onClick={state.resetConversation}>New chat</button><button className="assistant-icon-button" aria-label="Close LuminaR AI" onClick={close}><X size={18} /></button></div>
      </header>
      <div ref={historyRef} role="log" aria-label="Assistant conversation" aria-live="polite" aria-relevant="additions" className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain p-4">
        {!state.messages.length && <div><p className="text-sm leading-relaxed">Welcome to LuminaR. Discover books, compare your selections, check availability, or ask about your library account.</p>
          <p className="mt-2 text-xs text-ink-soft">Select up to four books anywhere in the catalogue to use them as context.</p></div>}
        {state.messages.map((message, index) => <div key={message.id} data-assistant-intent={message.kind === 'ASSISTANT_RESPONSE' ? message.response.intent : undefined} data-recommendation-mode={message.kind === 'ASSISTANT_RESPONSE' ? message.response.recommendation_mode ?? undefined : undefined} data-response-latency-ms={message.kind === 'ASSISTANT_RESPONSE' ? message.latencyMs : undefined} className={message.kind === 'USER_TEXT' ? 'ml-8 border border-line bg-panel p-3 text-sm' : 'border-l-2 border-brand/30 pl-3'}>
          {message.kind === 'ASSISTANT_RESPONSE' ? <AssistantTurn response={message.response} busy={state.busy} pendingActive={lastMessage?.id === message.id} now={now} onAction={onAction} onChoice={book => {
            // Retry the original task with the user's explicit canonical choice.
            let original = ''
            for (let i = index - 1; i >= 0; i--) { const previous = state.messages[i]; if (previous.kind === 'USER_TEXT') { original = previous.text; break } }
            send(original || 'Tell me about this book', { selected_work_ids: [book.work_id] })
          }} /> : <p role={message.kind === 'ERROR' ? 'alert' : undefined} className="whitespace-pre-wrap text-sm leading-relaxed">{message.text}</p>}
        </div>)}
        {state.busy && <div role="status" aria-live="polite" className="border-l-2 border-brand pl-3 text-sm"><span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-brand" />Working on that…
          <p className="mt-2 text-xs text-ink-soft">{state.startedAt && now - state.startedAt >= 15000 ? 'This can take a little while on the local AI model.' : 'You can keep browsing while LuminaR responds.'}</p></div>}
      </div>
      <div className="shrink-0 border-t border-line bg-paper p-3">
        <div className="mb-3 flex flex-wrap gap-2" aria-label="Quick actions">
          <button className="assistant-button inline-flex items-center gap-1" onClick={() => { setInput('Find books about '); inputRef.current?.focus() }}><Search size={12} />Find a book</button>
          <button disabled={state.busy || !authenticated} className="assistant-button inline-flex items-center gap-1" onClick={() => send('Recommend', { action: recommendAction(state.selected.length) })}><Sparkles size={12} />{recommendLabel(state.selected.length)}</button>
          <button disabled={state.busy || !authenticated} className="assistant-button inline-flex items-center gap-1" onClick={() => send('Show me books available now.', { action: 'AVAILABLE_NOW' })}><BookOpen size={12} />Available now</button>
          <button disabled={state.busy || !authenticated} className="assistant-button inline-flex items-center gap-1" onClick={() => send('Show my reading list', { action: 'USER_READING_LIST' })}><BookOpen size={12} />My reading list</button>
        </div>
        <SelectedBooksTray busy={state.busy || !authenticated} onSend={send} />
        {!!Object.keys(context).length && <p className="mb-2 truncate text-xs text-ink-soft">Context: {context.document_id ? 'selected document' : context.work_id ? 'current book' : 'current results'}</p>}
        {!authenticated ? <p className="text-sm"><Link className="text-brand underline" to="/login">Sign in</Link> to chat with LuminaR.</p> : <form onSubmit={event => { event.preventDefault(); send(input) }} className="border border-line bg-panel focus-within:border-brand">
          <label className="sr-only" htmlFor="luminar-assistant-input">Message LuminaR AI</label>
          <textarea id="luminar-assistant-input" ref={inputRef} rows={2} maxLength={4000} value={input} onChange={event => setInput(event.target.value)} placeholder="Ask LuminaR anything…" className="max-h-28 min-h-16 w-full resize-y bg-transparent px-3 py-2 text-sm text-ink outline-none" onKeyDown={event => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); send(input) }
          }} />
          <div className="flex items-center justify-between border-t border-line px-2 py-1.5"><span className="px-1 text-xs text-ink-soft">{input.length}/4000 · Shift+Enter for a new line</span>
            <button type="submit" disabled={state.busy || !input.trim()} aria-label="Send message" className="assistant-icon-button bg-brand text-paper disabled:opacity-40"><Send size={15} /></button></div>
        </form>}
      </div>
    </div>}
    {!state.open && <button ref={launcherRef} onClick={() => state.setOpen(true)} aria-label="Open LuminaR AI" aria-haspopup="dialog" className="fixed bottom-7 right-7 z-[100] flex items-center gap-3 bg-brand px-4 py-3 text-paper shadow-[0_14px_35px_rgba(189,63,27,0.28)] transition hover:-translate-y-1 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand">
      <MessageCircle size={22} /><div className="hidden text-left sm:block"><p className="font-display text-xs">Ask LuminaR</p><p className="mt-1 text-[0.6rem] opacity-70">{state.busy ? 'Working on your request…' : 'AI Library Assistant'}</p></div>
      {!!state.selected.length && <span className="border border-paper/40 px-1.5 text-xs">{state.selected.length} selected</span>}
    </button>}
  </>
}
