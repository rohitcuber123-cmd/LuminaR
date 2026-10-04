import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/core'
import { Feedback, Modal, Pager, Panel, Table, date } from '../components/StaffUI'
import { LoanRenewalControl } from '../components/LoanRenewalControl'
import type { RenewalPolicy } from '../lib/loanRenewal'
import { OperationTypeFilter } from '../components/OperationTypeFilter'

export interface Account { user_id: number; email: string; name: string; role?: string }
interface Operation { operation_id: string; operation_type: string; target_user_id: number | null; target_user: Account | null; actor_user_id: number | null; actor: Account | null; performed_by?: { kind: 'ACCOUNT' | 'SYSTEM' | 'LEGACY_READER'; account: Account | null; user_id: number | null }; book: { work_id: string; title: string }; occurred_at: string; due_at?: string; old_due_date?: string; new_due_date?: string; renewal?: RenewalPolicy; status?: string; source_ref: { issue_id?: number } }
interface Activity { user: Account; loans: { records: { title: string; due_date: string }[]; count: number }; reservations: { records: { title: string; status: string }[]; count: number }; fines: { records: { title: string; amount: number; status: string }[]; count: number }; notifications: { records: { notification_id: string; title: string; message: string }[]; count: number } }

export function UserPicker({ selected, onChange, label = 'Search user email...', disabled = false, onLoadingChange }: {
  selected: Account[]; onChange: (users: Account[]) => void; label?: string; disabled?: boolean; onLoadingChange?: (loading: boolean) => void
}) {
  const [query, setQuery] = useState(''), [users, setUsers] = useState<Account[]>([]), [error, setError] = useState('')
  const [selecting, setSelecting] = useState(false), [expanded, setExpanded] = useState(false)
  const selectionRequest = useRef<AbortController | null>(null)
  useEffect(() => () => selectionRequest.current?.abort(), [])
  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(() => { void api<{ users: Account[] }>(`/admin/users?q=${encodeURIComponent(query)}&limit=20`, { signal: controller.signal }).then(r => { setUsers(r.users); setError('') }).catch(() => { if (!controller.signal.aborted) setError('Unable to search users.') }) }, 250)
    return () => { clearTimeout(timer); controller.abort() }
  }, [query])
  async function selectAll() {
    if (selectionRequest.current || disabled) return
    const controller = new AbortController(); selectionRequest.current = controller
    setSelecting(true); onLoadingChange?.(true); setError('')
    try {
      const all = new Map<number, Account>()
      for (let offset = 0; ; offset += 50) {
        const result = await api<{ users: Account[]; count: number }>(`/admin/users?limit=50&offset=${offset}`, { signal: controller.signal })
        if (!Number.isInteger(result.count) || result.count < 0) throw new Error('Incomplete recipient directory.')
        for (const user of result.users) all.set(user.user_id, user)
        if (offset + result.users.length >= result.count || result.users.length < 50) break
      }
      if (!controller.signal.aborted) { onChange([...all.values()]); setExpanded(false) }
    } catch { if (!controller.signal.aborted) setError('Unable to select all users. Your current selection is unchanged. Try again.') }
    finally {
      selectionRequest.current = null
      if (!controller.signal.aborted) { setSelecting(false); onLoadingChange?.(false) }
    }
  }
  const locked = disabled || selecting
  return <div className="admin-user-picker">
    <div className="admin-recipient-heading"><div><h3>Recipients <span>{selected.length} selected</span></h3><p>Choose accounts or select all active, verified users.</p></div><div className="admin-recipient-actions"><button type="button" className="admin-select-all" disabled={locked} onClick={() => void selectAll()}>{selecting ? 'Selecting users…' : 'Select all users'}</button><button type="button" disabled={locked || !selected.length} onClick={() => onChange([])}>Clear</button></div></div>
    <label>{label}<input aria-label={label} placeholder="Search by email" value={query} disabled={locked} onChange={e => setQuery(e.target.value)} /></label>
    {error && <p className="admin-picker-error" role="alert">{error}</p>}
    {!!selected.length && <div className="admin-selected">{(expanded ? selected : selected.slice(0, 5)).map(u => <button type="button" key={u.user_id} disabled={locked} onClick={() => onChange(selected.filter(s => s.user_id !== u.user_id))} aria-label={`Remove ${u.email}`}>{u.email} <span aria-hidden="true">×</span></button>)}{selected.length > 5 && <button type="button" className="admin-selection-expand" onClick={() => setExpanded(v => !v)}>{expanded ? 'Show fewer' : `+${selected.length - 5} more`}</button>}</div>}
    {(!users.length || query.trim() || !users.every(u => selected.some(s => s.user_id === u.user_id))) && <ul aria-label="Matching users">{users.map(u => {
      const picked = selected.some(s => s.user_id === u.user_id)
      return <li key={u.user_id}><button type="button" disabled={locked} aria-pressed={picked} onClick={() => onChange(picked ? selected.filter(s => s.user_id !== u.user_id) : [...selected, u])}><span className="admin-recipient-check" aria-hidden="true">{picked ? '✓' : '+'}</span><span>{u.email}<small>{u.name}</small></span></button></li>
    })}</ul>}
  </div>
}

export function NotificationComposer({ initial = [], onClose, onSent }: { initial?: Account[]; onClose: () => void; onSent: () => void }) {
  const [users, setUsers] = useState(initial), [title, setTitle] = useState(''), [message, setMessage] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState('')
  const [selecting, setSelecting] = useState(false), [started, setStarted] = useState(false), [delivered, setDelivered] = useState(0)
  const sending = useRef(false)
  const plan = useRef<{ ids: number[]; title: string; message: string; requestId: string; completed: number } | null>(null)
  async function send() {
    if (sending.current || selecting || !users.length || !title.trim() || !message.trim()) return
    sending.current = true; setBusy(true); setStarted(true); setError('')
    plan.current ??= { ids: users.map(u => u.user_id), title, message, requestId: crypto.randomUUID(), completed: 0 }
    const current = plan.current
    try {
      while (current.completed < current.ids.length) {
        const ids = current.ids.slice(current.completed, current.completed + 50)
        await api('/admin/notifications', { method: 'POST', body: JSON.stringify({ recipient_user_ids: ids, title: current.title, message: current.message, request_id: current.requestId }) })
        current.completed += ids.length; setDelivered(current.completed)
      }
      onSent(); onClose()
    } catch (e) {
      setError(`${current.completed} of ${current.ids.length} recipients confirmed. ${e instanceof Error ? e.message : 'Unable to send.'} Retry to finish this message, or close to compose a different one.`)
    } finally { sending.current = false; setBusy(false) }
  }
  return <Modal title="Send Notification" className="admin-notification-dialog" onClose={onClose} busy={busy || selecting}><form className="staff-form admin-notification-form" onSubmit={e => { e.preventDefault(); void send() }}>
    <div className="admin-notification-body">
    <UserPicker selected={users} onChange={setUsers} label="Recipient email" disabled={busy || started} onLoadingChange={setSelecting} />
    <div className="admin-compose-fields"><label>Title<input aria-label="Notification title" placeholder="A short, clear subject" required maxLength={120} value={title} onChange={e => setTitle(e.target.value)} disabled={busy || started} /></label>
    <label>Message<textarea aria-label="Notification message" placeholder="Write your message to readers…" required maxLength={1000} rows={4} value={message} onChange={e => setMessage(e.target.value)} disabled={busy || started} /></label><p className="admin-message-hint">Appears in each recipient’s notification inbox.<span>{message.length}/1000</span></p></div>
    {error && <p className="admin-picker-error" role="alert">{error}</p>}
    </div>
    <footer className="admin-notification-footer"><span role="status">{busy ? `Sending: ${delivered} of ${users.length}` : `${users.length} ${users.length === 1 ? 'recipient' : 'recipients'}`}</span><button type="button" disabled={busy || selecting} onClick={onClose}>Cancel</button><button className="staff-primary" disabled={busy || selecting || !users.length || !title.trim() || !message.trim()}>{busy ? 'Sending…' : started ? 'Retry remaining' : 'Send'}</button></footer>
  </form></Modal>
}

export function AdminNotifications() {
  const [compose, setCompose] = useState(false), [page, setPage] = useState(0), [revision, setRevision] = useState(0), [success, setSuccess] = useState(''), [error, setError] = useState('')
  const [sent, setSent] = useState<{ notifications: { notification_id: string; title: string; message: string; recipient: Account | null; sender: Account | null; created_at: string; delivery_status: string }[]; count: number }>({ notifications: [], count: 0 })
  useEffect(() => { const controller = new AbortController(); void api<typeof sent>(`/admin/notifications/sent?limit=20&offset=${page * 20}`, { signal: controller.signal }).then(r => { setSent(r); setError('') }).catch(e => { if (!controller.signal.aborted) setError(e.message) }); return () => controller.abort() }, [page, revision])
  return <div className="admin-notification-history"><Panel title="Sent Notifications" tools={<button className="staff-primary" onClick={() => setCompose(true)}>Send Notification</button>}>
    <p className="admin-notification-description">Send updates to readers and keep track of messages delivered to their inboxes.</p>
    {(success || error) && <div className="admin-notification-feedback"><Feedback value={{ error: Boolean(error), text: error || success }} /></div>}
    <Table headers={['Recipient', 'Notice', 'Sent by', 'Date', 'Delivery']} count={sent.notifications.length} empty="No notifications sent yet.">{sent.notifications.map(n => <tr key={n.notification_id}><td data-label="Recipient" className="admin-notification-account">{n.recipient?.email || 'Unknown user'}{n.recipient?.name && <small>{n.recipient.name}</small>}</td><td data-label="Notice" className="admin-notification-content"><strong>{n.title}</strong><small>{n.message}</small></td><td data-label="Sent by" className="admin-notification-account">{n.sender?.email || 'Unknown actor'}</td><td data-label="Date">{date(n.created_at)}</td><td data-label="Delivery"><span className="admin-delivery-badge">{n.delivery_status === 'STORED' ? 'In inbox' : n.delivery_status}</span></td></tr>)}</Table><Pager page={page} count={sent.count} onChange={setPage} />
    {compose && <NotificationComposer onClose={() => { setCompose(false); setRevision(v => v + 1) }} onSent={() => setSuccess('Notification sent successfully.')} />}
  </Panel></div>
}

function OperationActor({ operation: r }: { operation: Operation }) {
  if (r.actor_user_id != null) return <>{r.actor?.email || r.performed_by?.account?.email || `Account #${r.actor_user_id}`}{' '}<small>{r.actor_user_id === r.target_user_id ? 'User action' : 'Staff-assisted action'}</small></>
  if (r.performed_by?.kind === 'SYSTEM' || ['FINE_CREATED', 'RESERVATION_READY'].includes(r.operation_type)) return <>System{' '}<small>Automatic circulation update</small></>
  return <>{r.performed_by?.account?.email || r.target_user?.email || 'Actor not recorded'}{' '}<small>Reader · actor not recorded</small></>
}

export function AdminOperations() {
  const [email, setEmail] = useState(''), [book, setBook] = useState(''), [kind, setKind] = useState(''), [group, setGroup] = useState(false), [page, setPage] = useState(0)
  const [user, setUser] = useState<Account | null>(null), [detail, setDetail] = useState<Activity | null>(null), [notify, setNotify] = useState<Account[] | null>(null), [revision, setRevision] = useState(0)
  const [data, setData] = useState<{ operations: Operation[]; count: number; operation_types: string[] }>({ operations: [], count: 0, operation_types: [] }), [loading, setLoading] = useState(true), [error, setError] = useState(''), [success, setSuccess] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    const params = new URLSearchParams({ limit: '20', offset: String(page * 20), email, operation_type: kind })
    if (user) params.set('user_id', String(user.user_id))
    if (/^OL\d+W$/i.test(book.trim())) params.set('work_id', book.trim().toUpperCase()); else params.set('title', book)
    const timer = setTimeout(() => { setLoading(true); void api<typeof data>(`/admin/operations?${params}`, { signal: controller.signal }).then(r => { setData(r); setError('') }).catch(e => { if (!controller.signal.aborted) setError(e.message) }).finally(() => { if (!controller.signal.aborted) setLoading(false) }) }, 200)
    return () => { clearTimeout(timer); controller.abort() }
  }, [email, book, kind, page, user, revision])
  async function inspect(u: Account) { setUser(u); setPage(0); try { setDetail(await api<Activity>(`/admin/users/${u.user_id}/activity`)) } catch (e) { setError(e instanceof Error ? e.message : 'Unable to load activity.') } }
  const groups = group ? [...new Set(data.operations.map(r => r.target_user_id))].map(id => ({ id, rows: data.operations.filter(r => r.target_user_id === id) })) : [{ id: null, rows: data.operations }]
  const rows = (items: Operation[]) => items.map(r => <tr key={r.operation_id}>
    <td data-label="User">{r.target_user ? <button className="admin-account-link" onClick={() => void inspect(r.target_user!)}>{r.target_user.email}</button> : 'Unknown user'}<small>{r.target_user_id ? `Account #${r.target_user_id}` : 'Legacy operation'}</small></td>
    <td data-label="Book" className="admin-wrap">{r.book.work_id ? <Link to={`/book/${encodeURIComponent(r.book.work_id)}`}>{r.book.title || r.book.work_id}</Link> : r.book.title || '—'}</td><td data-label="Operation"><span className={`admin-operation-badge ${r.operation_type === 'BOOK_RENEWED' ? 'is-renewed' : ''}`}>{r.operation_type.replaceAll('_', ' ')}</span>{r.old_due_date && r.new_due_date && <small className="admin-renewal-dates"><span>{date(r.old_due_date)}</span><span>→ {date(r.new_due_date)}</span></small>}</td><td data-label="Date">{date(r.occurred_at)}</td><td data-label="Performed by" className="admin-operation-actor"><OperationActor operation={r} /></td>
    <td data-label="Actions"><div className="admin-operation-actions">{r.target_user && <button onClick={() => setNotify([r.target_user!])}>Notify User</button>}{r.operation_type === 'BOOK_ISSUED' && r.status === 'ISSUED' && r.source_ref.issue_id && <button onClick={() => { if (!window.confirm(`Process return of ${r.book.title} for ${r.target_user?.email || 'this account'}?`)) return; void api(`/admin/operations/return/${r.source_ref.issue_id}`, { method: 'POST' }).then(() => { setRevision(v => v + 1); setSuccess('Return processed.') }).catch(e => setError(e.message)) }}>Process return</button>}{r.operation_type === 'BOOK_ISSUED' && r.status === 'ISSUED' && r.source_ref.issue_id && r.due_at && <LoanRenewalControl compact assisted loan={{ issue_id: r.source_ref.issue_id, due_date: r.due_at, renewal: r.renewal }} onRenewed={() => { setRevision(v => v + 1); setSuccess('Loan renewed.'); setError('') }} />}</div></td>
  </tr>)
  return <div className="admin-operations"><Panel title={user ? `Activity for ${user.email}` : 'Library operations'} tools={<>
    <button aria-pressed={group} onClick={() => setGroup(v => !v)}>Group by user</button>{user && <button onClick={() => { setUser(null); setDetail(null); setPage(0) }}>Clear selected account</button>}
  </>}>
    <div className="admin-operation-controls"><label>User email<input aria-label="Search user email..." placeholder="Search user email..." value={email} onChange={e => { setEmail(e.target.value); setUser(null); setPage(0) }} /></label>
    <label>Book<input aria-label="Search book title or work ID" placeholder="Book title or work ID" value={book} onChange={e => { setBook(e.target.value); setPage(0) }} /></label>
    <div><span className="admin-filter-label">Operation type</span><OperationTypeFilter value={kind} types={data.operation_types} onChange={value => { setKind(value); setPage(0) }} /></div></div>
    {(success || error) && <div className="admin-operation-feedback"><Feedback value={{ error: Boolean(error), text: error || success }} />{error && <button onClick={() => setRevision(v => v + 1)}>Retry</button>}</div>}
    {loading ? <p role="status">Loading operations…</p> : groups.map(g => <div key={String(g.id)}>{group && <h3>{g.rows[0]?.target_user?.email || 'Unknown user'}</h3>}<Table headers={['User', 'Book', 'Operation', 'Date', 'Performed by', 'Actions']} count={g.rows.length} empty="No operations match these filters.">{rows(g.rows)}</Table></div>)}
    {group && <p className="staff-note">Grouped within this page. Filters and pagination apply on the server.</p>}<Pager page={page} count={data.count} onChange={setPage} />
    {detail && <Modal title={`Activity for ${detail.user.email}`} onClose={() => setDetail(null)}><p>{detail.user.name} · {detail.user.role}</p><h3>Current Loans ({detail.loans.count})</h3>{detail.loans.records.map((l, i) => <p key={i}>{l.title} · Due {date(l.due_date)}</p>)}<h3>Reservations ({detail.reservations.count})</h3>{detail.reservations.records.map((l, i) => <p key={i}>{l.title} · {l.status}</p>)}<h3>Fees ({detail.fines.count})</h3>{detail.fines.records.map((l, i) => <p key={i}>{l.title} · ₹{l.amount} · {l.status}</p>)}<h3>Notification History ({detail.notifications.count})</h3>{detail.notifications.records.map(n => <p key={n.notification_id}>{n.title}: {n.message}</p>)}<p className="staff-note">Each summary shows up to 20 records. Recent operation history is filtered to this account behind this panel.</p></Modal>}
    {notify && <NotificationComposer initial={notify} onClose={() => setNotify(null)} onSent={() => setSuccess('Notification sent successfully.')} />}
  </Panel></div>
}
