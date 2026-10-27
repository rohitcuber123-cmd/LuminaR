import { LuminarSelect } from '../components/LuminarSelect'
import { LibraryBookTitleLink } from '../components/LibraryBookTitleLink'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { PageHeading, StatePanel } from '../components/WorkspaceUI'
import { Modal } from '../components/StaffUI'
import { institutionApi } from '../lib/institutions'
import { commandKey, lendingBase, lendingCommand } from '../lib/libraryLending'
import { money, minorAmount, type ReservationRow, type FeeRow, type FeePolicy, type QueuePage, type FeePage } from '../lib/libraryReservationsFees'
import { useAuthStore } from '../store/useAuthStore'
import { activeLibrary, useInstitutionStore } from '../store/useInstitutionStore'
import './Institutions.css'
import './LibraryInventory.css'

const errorText = (error: unknown) => error instanceof Error ? error.message : 'Unable to complete library action.'
const when = (stamp?: string) => stamp ? new Date(stamp).toLocaleString() : '—'

export function LibraryReservationsFeesPage({ staff = false, fees = false }: { staff?: boolean; fees?: boolean }) {
  const library = useInstitutionStore(activeLibrary), token = useAuthStore(s => s.token)
  if (!library?.membership || library.membership.status !== 'ACTIVE') return <div className="institutions"><h1>My Library</h1><p>Select a library with active membership.</p><Link to="/libraries">Explore Libraries</Link></div>
  if (staff && !['ADMIN', 'LIBRARIAN'].includes(library.membership.role)) return <div className="institutions"><h1>Circulation</h1><p>Active staff membership is required for this library.</p></div>
  if (!staff && library.membership.role !== 'GENERAL_USER') return <StatePanel title="Patron membership required">Use the Staff Workspace to review reservations and fees.</StatePanel>
  return <LibraryAccount key={`${library.library_id}:${token}:${staff}:${fees}`} libraryId={library.library_id} name={library.name} admin={library.membership.role === 'ADMIN'} staff={staff} fees={fees} />
}

function LibraryAccount({ libraryId, name, admin, staff, fees }: { libraryId: string; name: string; admin: boolean; staff: boolean; fees: boolean }) {
  const base = lendingBase(libraryId)
  const [mode, setMode] = useState(''), [error, setError] = useState(''), [success, setSuccess] = useState(''), [loading, setLoading] = useState(true), [busy, setBusy] = useState(false)
  const [revision, setRevision] = useState(0), [page, setPage] = useState(0), [status, setStatus] = useState(staff && !fees ? 'WAITING' : 'all'), [search, setSearch] = useState(''), [type, setType] = useState('all'), [since, setSince] = useState(''), [until, setUntil] = useState('')
  const [queues, setQueues] = useState<QueuePage>({ results: [], total: 0 }), [charges, setCharges] = useState<FeePage>({ results: [], total: 0 }), [policy, setPolicy] = useState<FeePolicy | null>(null)
  const [action, setAction] = useState<{ type: string; key: string; reservation?: ReservationRow; fee?: FeeRow } | null>(null)
  const [reason, setReason] = useState(''), [amount, setAmount] = useState(''), [method, setMethod] = useState('CASH'), [reference, setReference] = useState(''), [direction, setDirection] = useState('CREDIT'), [grace, setGrace] = useState('0'), [stop, setStop] = useState('PHYSICAL_RECEIPT'), [enabled, setEnabled] = useState(true)
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  useEffect(() => {
    let current = true; const controller = new AbortController()
    async function load() {
      setLoading(true); setError(''); setQueues({ results: [], total: 0 }); setCharges({ results: [], total: 0 }); setPolicy(null)
      try {
        const config = await institutionApi<{ state: string }>(`${base}/reservations-fees/config`, 'GET', undefined, controller.signal)
        if (!current) return
        setMode(config.state)
        if (config.state === 'CANONICAL') {
          const query = new URLSearchParams({ offset: String(page * 20), ...(staff ? { status, search, ...(fees ? { fee_type: type } : {}), ...(since ? { since: new Date(since).toISOString() } : {}), ...(until ? { until: new Date(until).toISOString() } : {}) } : {}) })
          const data = await institutionApi<QueuePage & FeePage>(`${base}/${staff ? 'staff' : 'me'}/${fees ? 'fees' : 'reservations'}?${query}`, 'GET', undefined, controller.signal)
          if (!current) return
          if (fees) setCharges(data); else setQueues(data)
          if (fees && staff && admin) {
            const version = await institutionApi<{ current: FeePolicy }>(`${base}/settings/fee-policy`, 'GET', undefined, controller.signal)
            if (current) setPolicy(version.current)
          }
        }
      } catch (error) { if (current) setError(errorText(error)) } finally { if (current) setLoading(false) }
    }
    void load(); return () => { current = false; controller.abort() }
  }, [base, staff, fees, admin, revision, page, status, search, type, since, until])
  function open(type: string, fee?: FeeRow, reservation?: ReservationRow) {
    setAction({ type, fee, reservation, key: commandKey() }); setReason(''); setAmount(type === 'policy' ? String((policy?.rate_minor_per_day ?? 500) / 100) : ''); setMethod('CASH'); setReference(''); setDirection('CREDIT'); setError('')
    setGrace(String(policy?.grace_days ?? 0)); setStop(policy?.charge_stop_policy ?? 'PHYSICAL_RECEIPT'); setEnabled(policy?.overdue_enabled ?? true)
  }
  async function detail(row: FeeRow) {
    setBusy(true); setError('')
    try {
      const result = await institutionApi<FeeRow>(`${base}/${staff ? 'staff' : 'me'}/fees/${row.fee_id}`)
      if (alive.current) open('details', result)
    } catch (error) { if (alive.current) setError(errorText(error)) } finally { if (alive.current) setBusy(false) }
  }
  async function confirm() {
    if (!action) return
    setBusy(true); setError('')
    try {
      const path = action.type === 'activate' ? `${base}/staff/reservations-fees/activate` : action.type === 'cancel' ? `${base}/reservations/${action.reservation!.reservation_id}/cancel` : action.type === 'policy' ? `${base}/settings/fee-policy` : `${base}/staff/fees/${action.fee!.fee_id}/${action.type}`
      const fields = action.type === 'payments' ? { amount_minor: minorAmount(amount), method, reference: reference.trim() || null, note: reason.trim() || null } : action.type === 'adjust' ? { amount_minor: minorAmount(amount), direction, reason: reason.trim() } : action.type === 'waive' ? { reason: reason.trim() } : action.type === 'policy' ? { overdue_enabled: enabled, rate_minor_per_day: minorAmount(amount), grace_days: Number(grace), currency: 'INR', charge_stop_policy: stop } : {}
      await lendingCommand(path, fields, action.key)
      if (alive.current) { setAction(null); setRevision(r => r + 1); setSuccess(action.type === 'payments' ? 'Manual payment record saved. Payment is handled by the library.' : action.type === 'policy' ? 'New fee policy version created. Existing loan policies are preserved.' : 'Library record updated.') }
    } catch (error) { if (alive.current) setError(errorText(error)) } finally { if (alive.current) setBusy(false) }
  }
  const total = fees ? charges.total : queues.total
  return <div className="institutions library-inventory"><PageHeading title={fees ? 'Fees' : 'Reservations'} description={`${staff ? 'Manage' : 'Your'} ${fees ? 'library charges and payments' : 'library waiting queue'} at ${name}.`} />
    {fees ? <p>Payment is handled by the library. These records show charges, waivers and manual desk payments. Physical returns remain independent of unpaid fees.</p> : <p>Reservations wait in this library’s book queue. When a unit becomes available, the first eligible member receives a Borrow Request for librarian approval.</p>}
    {loading && <p role="status">Loading library records…</p>}{error && <p role="alert" className="institution-error">{error} <button onClick={() => setRevision(r => r + 1)}>Refresh</button></p>}{success && <p role="status">{success}</p>}
    {!loading && mode !== 'CANONICAL' && <section className="institution-card"><h3>{mode === 'LEGACY' ? 'Reservations and fees setup required' : 'Reservations and fees need recovery'}</h3><p>Library admin must reconcile legacy records and enable these features.</p>{staff && admin && mode === 'LEGACY' && <button onClick={() => open('activate')}>Enable Reservations & Fees</button>}</section>}
    {mode === 'CANONICAL' && <>{staff && <form className="ui-filter-toolbar circulation-filters" onSubmit={e => { e.preventDefault(); const form = new FormData(e.currentTarget); setSearch(String(form.get('search') || '')); setSince(String(form.get('since') || '')); setUntil(String(form.get('until') || '')); setPage(0) }}><label>Search<input name="search" maxLength={150} placeholder={fees ? 'Member, book, accession, loan or fee ID' : 'Book or accession'} /></label><label>Status<LuminarSelect value={status} onChange={e => { setStatus(e.target.value); setPage(0) }}>{(fees ? ['all', 'OPEN', 'PARTIALLY_PAID', 'PAID', 'WAIVED', 'CANCELLED'] : ['all', 'WAITING', 'CONVERTED', 'FULFILLED', 'CANCELLED', 'EXPIRED']).map(s => <option key={s}>{s}</option>)}</LuminarSelect></label>{fees && <><label>Fee type<LuminarSelect value={type} onChange={e => { setType(e.target.value); setPage(0) }}>{['all', 'OVERDUE', 'DAMAGE', 'LOST', 'MANUAL_ADJUSTMENT'].map(s => <option key={s}>{s}</option>)}</LuminarSelect></label><label>From<input name="since" type="datetime-local" /></label><label>Until<input name="until" type="datetime-local" /></label></>}<button className="ui-button">Filter</button></form>}
      {fees && policy && <section className="institution-card"><h3>Fee policy · Version {policy.version}</h3><p>{policy.overdue_enabled ? money(policy.rate_minor_per_day) + ' per overdue UTC calendar day' : 'Overdue charging disabled'} · {policy.grace_days} grace days · {policy.charge_stop_policy.replaceAll('_', ' ')}</p><button disabled={busy} onClick={() => open('policy')}>Create Policy Version</button></section>}
      {!fees && <div className="inventory-books">{queues.results.map(row => <article className="inventory-book" key={row.reservation_id}><div><span className="inventory-accession">{row.accession_number}</span><h3><LibraryBookTitleLink libraryId={libraryId} bookId={row.library_book_id} staff={staff} title={row.title} /></h3><span className="institution-badge">{row.status === 'CONVERTED' ? 'Ready for Borrow Approval' : row.status}</span></div><dl><div><dt>Library</dt><dd>{name}</dd></div><div><dt>Queue position</dt><dd>{row.queue_position ? `${row.queue_position} of ${row.queue_length}` : '—'}</dd></div><div><dt>Requested</dt><dd>{when(row.requested_at)}</dd></div>{staff && <><div><dt>Member</dt><dd>{row.borrower?.name}<br />{row.borrower?.email}</dd></div><div><dt>Availability</dt><dd>{row.availability?.requestable} requestable</dd></div></>}</dl>{row.reason && <p>{row.reason}</p>}{!staff && row.status === 'WAITING' && <button disabled={busy || loading} onClick={() => open('cancel', undefined, row)}>Cancel Reservation</button>}{row.lending_request_id && <p>Borrow request: {row.lending_request_id} <Link to={staff ? '/library-circulation' : '/library-loans'}>View Borrow Request</Link></p>}</article>)}</div>}
      {fees && <><div className="inventory-books">{charges.results.map(row => <article className="inventory-book" key={row.fee_id}><div><span className="inventory-accession">{row.accession_number}</span><h3><LibraryBookTitleLink libraryId={libraryId} bookId={row.library_book_id} staff={staff} title={row.title} /></h3><span className="institution-badge">{row.status.replaceAll('_', ' ')}</span></div><dl><div><dt>Charge</dt><dd>{money(row.current_amount_minor, row.currency)}</dd></div><div><dt>Recorded paid</dt><dd>{money(row.paid_amount_minor, row.currency)}</dd></div><div><dt>Balance</dt><dd>{money(row.balance_minor, row.currency)}</dd></div><div><dt>Fee type</dt><dd>{row.fee_type}</dd></div>{staff && <div><dt>Member</dt><dd>{row.borrower?.name}<br />{row.borrower?.email}</dd></div>}</dl><p>Policy version {row.policy_snapshot.version} · Created {when(row.created_at)}</p><div className="institution-actions"><button disabled={busy || loading} onClick={() => void detail(row)}>View Fee Details</button>{staff && !['WAIVED', 'CANCELLED'].includes(row.status) && <>{row.balance_minor > 0 && <button disabled={busy || loading} onClick={() => open('payments', row)}>Record Payment</button>}{admin && <><button disabled={busy || loading} onClick={() => open('adjust', row)}>Adjust Fee</button>{row.balance_minor > 0 && <button disabled={busy || loading} onClick={() => open('waive', row)}>Waive Fee</button>}</>}</>}</div></article>)}</div>{charges.estimates?.map(row => <section className="institution-card" key={row.loan_id}><h3><LibraryBookTitleLink libraryId={libraryId} bookId={row.library_book_id} staff={staff} title={row.title} /></h3><p>ESTIMATED accrued overdue charge: {money(row.amount_minor, row.currency)}. Final charge is calculated when staff confirms physical receipt.</p></section>)}</>}
      {!loading && !total && <p>No {fees ? 'final fees' : 'reservations'} in this view.</p>}<div className="ui-pagination"><button className="ui-button ui-secondary" disabled={loading || !page} onClick={() => { setPage(p => p - 1); requestAnimationFrame(() => { const el = document.querySelector<HTMLElement>('.institutions'); if (el) { const top = el.getBoundingClientRect().top + window.scrollY - 64 - 8; const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches; window.scrollTo({ top: Math.max(0, top), behavior: reduced ? 'instant' : 'smooth' }) } }) }}>Previous</button><span>Page {page + 1}</span><button className="ui-button ui-secondary" disabled={loading || (page + 1) * 20 >= total} onClick={() => { setPage(p => p + 1); requestAnimationFrame(() => { const el = document.querySelector<HTMLElement>('.institutions'); if (el) { const top = el.getBoundingClientRect().top + window.scrollY - 64 - 8; const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches; window.scrollTo({ top: Math.max(0, top), behavior: reduced ? 'instant' : 'smooth' }) } }) }}>Next</button></div>
    </>}
    {action && <Modal title={action.type === 'payments' ? 'Record Manual Payment' : action.type === 'policy' ? 'Create Fee Policy Version' : action.type === 'details' ? 'Fee Details' : action.type === 'waive' ? 'Waive Fee' : action.type === 'adjust' ? 'Adjust Fee' : action.type === 'activate' ? 'Enable Reservations & Fees' : 'Cancel Reservation'} busy={busy} onClose={() => setAction(null)}><div className="institutions"><p>{name} · {action.fee?.title || action.reservation?.title}</p>
      {action.type === 'details' && action.fee && <><p>Fee ID: {action.fee.fee_id}<br />Loan ID: {action.fee.loan_id}</p><p>Original charge: {money(action.fee.original_amount_minor)} · Current balance: {money(action.fee.balance_minor)}</p><p>Policy version {action.fee.policy_snapshot.version} · {action.fee.policy_snapshot.charge_stop_policy.replaceAll('_', ' ')}</p><p>Due: {when(action.fee.calculation.due_at)}<br />Return requested: {when(action.fee.calculation.return_requested_at)}<br />Valid return request: {when(action.fee.calculation.valid_return_requested_at)}<br />Physically received: {when(action.fee.calculation.physical_received_at)}<br />Charge stopped: {when(action.fee.calculation.charge_stop_at)}</p><h3>Immutable history</h3>{action.fee.ledger?.map(entry => <section key={entry.entry_id}><p>{entry.entry_type.replaceAll('_', ' ')} · {money(entry.amount_minor)} · {when(entry.created_at)}<br />{entry.reason}{entry.receipt_id && <><br />Library receipt: {entry.receipt_id}</>}</p></section>)}</>}
      {action.type === 'cancel' && <p>Leave this book’s waiting queue? A converted reservation must be cancelled through its Borrow Request.</p>}
      {action.type === 'activate' && <p>Enable canonical queues and fees after legacy migration and reconciliation. Initial overdue policy is ₹5 per UTC calendar day, charged until physical receipt.</p>}
      {action.type === 'payments' && <><p>This records a payment handled by the library. No online payment is processed.</p><label>Payment method<LuminarSelect value={method} onChange={e => setMethod(e.target.value)}>{['CASH', 'EXTERNAL', 'OTHER'].map(s => <option key={s}>{s}</option>)}</LuminarSelect></label><label>Desk reference (optional)<input maxLength={100} value={reference} onChange={e => setReference(e.target.value)} /></label></>}
      {['payments', 'adjust', 'policy'].includes(action.type) && <label>{action.type === 'policy' ? 'Daily rate (INR)' : 'Amount (INR)'}<input inputMode="decimal" value={amount} onChange={e => setAmount(e.target.value)} /></label>}
      {action.type === 'adjust' && <label>Adjustment<LuminarSelect value={direction} onChange={e => setDirection(e.target.value)}><option value="CREDIT">Credit / reduce charge</option><option value="CHARGE">Add charge</option></LuminarSelect></label>}
      {['payments', 'waive', 'adjust'].includes(action.type) && <label>{action.type === 'payments' ? 'Note (optional)' : 'Reason (required)'}<textarea maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></label>}
      {action.type === 'waive' && <p>Waive the remaining {money(action.fee!.balance_minor)} balance. Charge and payment history remain available.</p>}
      {action.type === 'policy' && <><p>Applies to future loans. Existing loans and charges keep their recorded policy version. Day boundaries use UTC.</p><label><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />Overdue charging enabled</label><label>Grace days<input type="number" min={0} max={365} value={grace} onChange={e => setGrace(e.target.value)} /></label><label>Charge stops at<LuminarSelect value={stop} onChange={e => setStop(e.target.value)}><option value="PHYSICAL_RECEIPT">Physical receipt</option><option value="FIRST_VALID_RETURN_REQUEST">Return request later confirmed valid</option></LuminarSelect></label></>}
      {error && <p role="alert">{error}</p>}{action.type !== 'details' && <button disabled={busy || ['waive', 'adjust'].includes(action.type) && !reason.trim() || ['payments', 'adjust', 'policy'].includes(action.type) && !amount.trim()} onClick={() => void confirm()}>{busy ? 'Saving…' : 'Confirm'}</button>}
    </div></Modal>}
  </div>
}

export function ReservationControl({ libraryId, bookId, unavailable, changed }: { libraryId: string; bookId: string; unavailable: boolean; changed: () => void }) {
  const base = lendingBase(libraryId), [state, setState] = useState<{ state: string; reservation?: ReservationRow | null; pending_request_id?: string; active_loan?: boolean } | null>(null)
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [action, setAction] = useState<{ type: string; key: string } | null>(null), [revision, setRevision] = useState(0)
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  useEffect(() => { let current = true; const controller = new AbortController(); void institutionApi<typeof state>(`${base}/inventory/${bookId}/reservation-status`, 'GET', undefined, controller.signal).then(data => { if (current) setState(data) }).catch(error => { if (current) setError(errorText(error)) }); return () => { current = false; controller.abort() } }, [base, bookId, revision, unavailable])
  async function confirm() {
    if (!action) return
    setBusy(true); setError('')
    try {
      await lendingCommand(action.type === 'cancel' ? `${base}/reservations/${state!.reservation!.reservation_id}/cancel` : `${base}/reservations`, action.type === 'cancel' ? {} : { library_book_id: bookId }, action.key)
      if (alive.current) { setAction(null); setRevision(r => r + 1); changed() }
    } catch (error) { if (alive.current) setError(errorText(error)) } finally { if (alive.current) setBusy(false) }
  }
  if (state?.state !== 'CANONICAL') return error ? <p role="alert">{error}</p> : null
  const row = state.reservation
  return <div>{row?.status === 'WAITING' ? <><p>Reserved · Position: {row.queue_position} of {row.queue_length}</p><button className="secondary" disabled={busy} onClick={() => setAction({ type: 'cancel', key: commandKey() })}>Cancel Reservation</button></> : row?.status === 'CONVERTED' || state.pending_request_id ? <p>Ready for Borrow Approval · <Link to="/library-loans">View Borrow Request</Link></p> : unavailable && !state.active_loan && <button disabled={busy} onClick={() => setAction({ type: 'reserve', key: commandKey() })}>Join Waitlist</button>}{error && <p role="alert">{error}</p>}{action && <Modal title={action.type === 'cancel' ? 'Cancel Reservation' : 'Join Waitlist'} busy={busy} onClose={() => setAction(null)}><p>{action.type === 'cancel' ? 'Leave this library book’s waiting queue?' : 'Join this library’s queue? An available unit will become a Borrow Request that staff must approve.'}</p>{error && <p role="alert">{error}</p>}<button disabled={busy} onClick={() => void confirm()}>Confirm</button></Modal>}</div>
}
