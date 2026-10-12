import { useEffect, useRef, useState } from 'react'
import { Bell, X } from 'lucide-react'
import { coreRequest, BORROW_STATE_CHANGED } from '../lib/api'
import { useAuthStore } from '../store/useAuthStore'
import { noticeDelta, type Notice } from '../lib/notifications'

interface Inbox { notifications: Notice[]; count: number; unread_count: number }

export function NotificationCenter() {
  const user = useAuthStore(s => s.user)
  const token = useAuthStore(s => s.token)
  const scope = `${user?.user_id ?? user?.id ?? ''}:${token ?? ''}`
  const [open, setOpen] = useState(false)
  const [inbox, setInbox] = useState<Inbox>({ notifications: [], count: 0, unread_count: 0 })
  const [offset, setOffset] = useState(0)
  const [toast, setToast] = useState<{ title: string; message: string } | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const refresh = useRef<() => Promise<void>>(async () => {})
  const session = useRef({ scope: '', seen: new Set<string>(), initialized: false })
  const panel = useRef<HTMLDivElement>(null)
  const bell = useRef<HTMLButtonElement>(null)
  const enabled = Boolean(user && token)

  useEffect(() => {
    if (!enabled) return
    let active = true, inFlight = false, pending = false
    if (session.current.scope !== scope) {
      session.current = { scope, seen: new Set<string>(), initialized: false }
      setInbox({ notifications: [], count: 0, unread_count: 0 }); setToast(null); setError(''); setOpen(false); setOffset(0)
    }
    const controller = new AbortController()
    const load = async () => {
      if (!active) return
      if (inFlight) { pending = true; return }
      inFlight = true
      try {
        const latest = await coreRequest<Inbox>('/notifications?limit=20', { signal: controller.signal })
        if (!active) return
        const fresh = noticeDelta(session.current.seen, latest.notifications, session.current.initialized)
        session.current.initialized = true
        let page = latest
        if (offset) page = await coreRequest<Inbox>(`/notifications?limit=20&offset=${offset}`, { signal: controller.signal })
        if (active) {
          setInbox(page); setError('')
          if (fresh.length) setToast(fresh.length === 1 ? fresh[0] : { title: 'New notifications', message: `You have ${fresh.length} new library notifications.` })
        }
      } catch { if (active) setError('Unable to load notifications. Try again.'); }
      finally { inFlight = false; if (pending && active) { pending = false; void load() } }
    }
    refresh.current = load
    void load()
    const focused = () => { if (document.visibilityState !== 'hidden') void load() }
    const timer = setInterval(focused, 45000)
    window.addEventListener('focus', focused); document.addEventListener('visibilitychange', focused)
    window.addEventListener(BORROW_STATE_CHANGED, focused)
    return () => { active = false; controller.abort(); clearInterval(timer); window.removeEventListener('focus', focused); document.removeEventListener('visibilitychange', focused); window.removeEventListener(BORROW_STATE_CHANGED, focused) }
  }, [scope, enabled, offset])

  useEffect(() => { if (!toast) return; const timer = setTimeout(() => setToast(null), 8000); return () => clearTimeout(timer) }, [toast])
  useEffect(() => {
    if (!open) return
    panel.current?.focus()
    const close = (e: KeyboardEvent) => { if (e.key === 'Escape') { setOpen(false); bell.current?.focus() } }
    document.addEventListener('keydown', close)
    return () => document.removeEventListener('keydown', close)
  }, [open])
  async function mark(id?: string) {
    const owner = scope
    setBusy(true)
    try {
      await coreRequest(id ? `/notifications/${encodeURIComponent(id)}/read` : '/notifications/read-all', { method: id ? 'PATCH' : 'POST' })
      if (`${useAuthStore.getState().user?.user_id ?? useAuthStore.getState().user?.id ?? ''}:${useAuthStore.getState().token ?? ''}` === owner) await refresh.current()
    } catch { setError('Unable to update read status. Try again.') }
    finally { setBusy(false) }
  }
  if (!enabled) return null
  return <div className="notification-root">
    <button ref={bell} type="button" className="notification-bell" aria-label={`Notifications${inbox.unread_count ? `, ${inbox.unread_count} unread` : ''}`} aria-expanded={open} aria-controls="notification-center" onClick={() => { setOpen(v => !v); void refresh.current() }}><Bell size={19} />{inbox.unread_count > 0 && <span className="notification-count">{inbox.unread_count > 99 ? '99+' : inbox.unread_count}</span>}</button>
    {open && <div id="notification-center" ref={panel} tabIndex={-1} role="region" aria-label="Notification Center" className="notification-panel">
      <div className="notification-head"><h2>Notifications</h2><button aria-label="Close notifications" onClick={() => { setOpen(false); bell.current?.focus() }}><X size={18} /></button></div>
      <button className="notification-read" disabled={busy || !inbox.unread_count} onClick={() => void mark()}>Mark all as read</button>
      {error && <p role="alert">{error} <button onClick={() => void refresh.current()}>Retry</button></p>}
      {!inbox.notifications.length && !error && <p className="notification-empty">No notifications yet.</p>}
      <ul>{inbox.notifications.map(n => <li key={n.notification_id} className={n.resolved_at ? 'notification-resolved' : n.read_at ? '' : 'notification-unread'}><h3>{n.title}</h3><p>{n.message}</p>{n.resolved_at && <p className="notification-resolution">Resolved — {(n.resolution_reason || 'loan updated').replaceAll('_', ' ').toLowerCase()}</p>}<time dateTime={n.created_at}>{new Date(n.created_at).toLocaleString()}</time>{!n.read_at && !n.resolved_at && <button disabled={busy} className="notification-read" onClick={() => void mark(n.notification_id)}>Mark as read</button>}</li>)}</ul>
      <div className="notification-pages"><button disabled={!offset} onClick={() => setOffset(v => Math.max(0, v - 20))}>Previous</button><span>{inbox.count ? `${offset + 1}–${Math.min(offset + 20, inbox.count)} of ${inbox.count}` : '0 notifications'}</span><button disabled={offset + 20 >= inbox.count} onClick={() => setOffset(v => v + 20)}>Next</button></div>
    </div>}
    {toast && <div className="notification-toast" role="status"><div><strong>{toast.title}</strong><p>{toast.message}</p></div><button aria-label="Close notification toast" onClick={() => setToast(null)}><X size={18} /></button></div>}
  </div>
}
