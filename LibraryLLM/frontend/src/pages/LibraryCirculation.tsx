import { LuminarSelect } from '../components/LuminarSelect'
import { LibraryBookTitleLink } from '../components/LibraryBookTitleLink'
import { useEffect, useRef, useState } from 'react'

import { Link, useSearchParams } from 'react-router-dom'
import { PageHeading, StatePanel } from '../components/WorkspaceUI'
import { patronPath } from '../lib/libraryWorkspace'

import { Modal } from '../components/StaffUI'

import { AssistantLibraryRequestButton } from '../components/AssistantLibraryRequestButton'

import { ReservationControl } from './LibraryReservationsFees'

import { institutionApi } from '../lib/institutions'

import { commandKey, lendingBase, lendingCommand, type LendingPage, type LendingRow } from '../lib/libraryLending'

import { useAuthStore } from '../store/useAuthStore'

import { activeLibrary, useInstitutionStore } from '../store/useInstitutionStore'

import './Institutions.css'

import './LibraryInventory.css'



const errorMessage = (reason: unknown) => reason instanceof Error ? reason.message : 'Unable to complete circulation action.'

const when = (value?: string) => value ? new Date(value).toLocaleString() : '—'



export function LibraryCirculationPage({ staff = false }: { staff?: boolean }) {

  const current = useInstitutionStore(activeLibrary), session = useAuthStore(s => s.token)
  const [params] = useSearchParams()
  const initialTab = ['return', 'loans'].includes(params.get('tab') || '') ? params.get('tab')! : 'borrow'

  if (!current?.membership || current.membership.status !== 'ACTIVE') return <div className="institutions"><h1>My Library</h1><p>Select a library with active membership.</p><Link to="/libraries">Explore Libraries</Link></div>

  if (staff && !['ADMIN', 'LIBRARIAN'].includes(current.membership.role)) return <div className="institutions"><h1>Circulation Requests</h1><p>Active staff membership is required for this library.</p></div>

  if (!staff && current.membership.role !== 'GENERAL_USER') return <StatePanel title="Patron membership required">Use this library’s Staff Workspace to manage circulation.</StatePanel>
  return <Circulation initialTab={initialTab} key={`${current.library_id}:${session}:${staff}:${initialTab}`} libraryId={current.library_id} name={current.name} admin={current.membership.role === 'ADMIN'} staff={staff} />

}



function Circulation({ libraryId, name, admin, staff, initialTab }: { libraryId: string; name: string; admin: boolean; staff: boolean; initialTab: string }) {

  const base = lendingBase(libraryId)
  const actorId = useAuthStore(s => Number(s.user?.user_id))

  const [mode, setMode] = useState(''), [tab, setTab] = useState(initialTab), [status, setStatus] = useState(initialTab === 'loans' ? 'ACTIVE' : 'PENDING'), [search, setSearch] = useState(''), [user, setUser] = useState(''), [since, setSince] = useState(''), [until, setUntil] = useState('')

  const [page, setPage] = useState(0), [revision, setRevision] = useState(0), [data, setData] = useState<LendingPage>({ results: [], total: 0 }), [loans, setLoans] = useState<LendingPage>({ results: [], total: 0 })

  const [error, setError] = useState(''), [success, setSuccess] = useState(''), [loading, setLoading] = useState(true), [busy, setBusy] = useState(false)

  const [action, setAction] = useState<{ row?: LendingRow; type: string; key: string } | null>(null), [reason, setReason] = useState('')

  const alive = useRef(true)

  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])

  useEffect(() => {

    let current = true; const controller = new AbortController()

    async function load() {

      setLoading(true); setError(''); setData({ results: [], total: 0 }); setLoans({ results: [], total: 0 })

      try {

        const config = await institutionApi<{ state: string }>(`${base}/lending/config`, 'GET', undefined, controller.signal)

        if (!current) return

        setMode(config.state)

        if (config.state === 'CANONICAL') {

          const query = new URLSearchParams({ offset: String(page * 20), status, search, ...(user ? { user_id: user } : {}), ...(since ? { since: new Date(since).toISOString() } : {}), ...(until ? { until: new Date(until).toISOString() } : {}) })

          const requests = await institutionApi<LendingPage>(staff ? tab === 'loans' ? `${base}/staff/loans?${query}` : `${base}/staff/lending/${tab}-requests?${query}` : `${base}/me/borrow-requests?offset=${page * 20}`, 'GET', undefined, controller.signal)

          if (current) setData(requests)

          if (!staff) {

            const active = await institutionApi<LendingPage>(`${base}/me/loans?offset=${page * 20}`, 'GET', undefined, controller.signal)

            if (current) setLoans(active)

          }

        }

      } catch (reason) { if (current) setError(errorMessage(reason)) } finally { if (current) setLoading(false) }

    }

    void load(); return () => { current = false; controller.abort() }

  }, [base, staff, tab, status, search, user, since, until, page, revision])

  const open = (type: string, row?: LendingRow) => { setAction({ type, row, key: commandKey() }); setReason(''); setError('') }

  async function confirm() {

    if (!action) return

    setBusy(true); setError('')

    const { row, type, key } = action

    const path = type === 'staff-renew' || type === 'staff-receive' ? `${base}/staff/loans/${row!.loan_id}/${type === 'staff-renew' ? 'renew' : 'receive'}` : type === 'activate' ? `${base}/staff/lending/activate` : type === 'cancel' ? `${base}/lending/borrow-requests/${row!.lending_request_id}/cancel` : type === 'return-request' || type === 'renew' ? `${base}/loans/${row!.loan_id}/${type}` : `${base}/staff/lending/${tab}-requests/${row!.lending_request_id}/${type}`

    try {

      const result = await lendingCommand<{ status?: string; rejection_reason?: string }>(path, ['renew', 'staff-renew'].includes(type) ? { expected_due_at: row!.due_at } : ['approve', 'reject', 'confirm'].includes(type) ? { reason: reason.trim() || null } : {}, key)

      if (alive.current) { setAction(null); setRevision(r => r + 1); setSuccess(result.rejection_reason || (type === 'return-request' ? 'Return requested. Your loan remains active until staff physically confirms receipt.' : type === 'activate' ? 'Approval circulation enabled.' : 'Circulation status updated.')) }

    } catch (reason) { if (alive.current) setError(errorMessage(reason)) } finally { if (alive.current) setBusy(false) }

  }

  function rowCard(row: LendingRow, loan = false) {

    return <article className="inventory-book" key={row.loan_id && loan ? row.loan_id : row.lending_request_id}><div><span className="inventory-accession">{row.accession_number}</span><h3><LibraryBookTitleLink libraryId={libraryId} bookId={row.library_book_id} staff={staff} title={row.title} /></h3><span className="institution-badge">{loan && row.pending_return_request_id ? 'RETURN REQUESTED · Awaiting librarian confirmation' : row.status === 'PENDING' ? staff && tab === 'return' ? 'RETURN REQUESTED · Awaiting physical receipt' : 'PENDING APPROVAL · Awaiting librarian approval' : row.status}</span></div>

      <dl><div><dt>Shelf / Location</dt><dd>{row.shelf_location || 'Not recorded'}</dd></div><div><dt>{loan ? 'Due' : 'Requested'}</dt><dd>{when(loan ? row.due_at : row.requested_at)}</dd></div>{staff && <div><dt>Copy tracking</dt><dd>{row.allocation_mode === 'COPY' ? 'Individual copy' : 'Quantity based'}{row.copy_id ? ` · ${row.copy_id}` : ''}</dd></div>}{staff && <><div><dt>Borrower</dt><dd>{row.borrower?.name}<br />{row.borrower?.email}<br />Membership: {row.borrower?.membership_status}</dd></div><div><dt>Availability</dt><dd>{row.availability?.requestable} requestable · {row.availability?.pending_holds} held · {row.availability?.active_loans} active</dd></div></>}</dl>

      {row.rejection_reason && <p>{row.rejection_reason}</p>}{loan && row.return_requested_at && <p>Return requested: {when(row.return_requested_at)}{row.returned_at ? ` · Received: ${when(row.returned_at)}` : ''}</p>}

      <div className="institution-actions">{staff && loan && row.status === 'ACTIVE' && row.user_id !== actorId && <><button disabled={busy || loading} onClick={() => open('staff-receive', row)}>Receive physical return</button><button className="secondary" disabled={busy || loading || !!row.pending_return_request_id} onClick={() => open('staff-renew', row)}>Renew for member</button></>}{staff && row.status === 'PENDING' && <><button disabled={busy || loading} onClick={() => open(tab === 'borrow' ? 'approve' : 'confirm', row)}>{tab === 'borrow' ? 'Approve & Issue' : 'Confirm Received'}</button><button className="secondary" disabled={busy || loading} onClick={() => open('reject', row)}>Reject</button></>}{!staff && !loan && row.status === 'PENDING' && <button className="secondary" disabled={busy || loading} onClick={() => open('cancel', row)}>Cancel Request</button>}{!staff && loan && row.status === 'ACTIVE' && <><button disabled={busy || loading || !!row.pending_return_request_id} onClick={() => open('return-request', row)}>Request Return</button><button className="secondary" disabled={busy || loading || !!row.pending_return_request_id} onClick={() => open('renew', row)}>Renew Loan</button><AssistantLibraryRequestButton libraryId={libraryId} bookId={row.library_book_id} loanId={row.loan_id!} disabled={!!row.pending_return_request_id} /></>}</div>

    </article>

  }

  return <div className="institutions library-inventory"><PageHeading title={staff ? 'Circulation' : 'My Library'} description={staff ? `Review requests, confirm physical returns and view loans at ${name}.` : `Your requests, current loans and borrowing history at ${name}.`} actions={!staff && <Link className="ui-button secondary" to="/account/history">Account and legacy history</Link>} />
    {loading && <StatePanel kind="loading" title="Loading circulation…" />}{error && <StatePanel kind="error" title="Unable to load circulation" action={<button onClick={() => setRevision(r => r + 1)}>Refresh</button>}>{error}</StatePanel>}{success && <p role="status">{success}</p>}

    {!loading && mode !== 'CANONICAL' && <section className="institution-card"><h2>{mode === 'LEGACY' ? 'Circulation setup required' : 'Circulation needs recovery'}</h2><p>Library staff must reconcile existing stock and loans before enabling requests.</p>{staff && admin && mode === 'LEGACY' && <button disabled={busy} onClick={() => open('activate')}>Enable Approval Circulation</button>}</section>}

    {mode === 'CANONICAL' && <>{staff && <><div className="ui-tabs" role="group" aria-label="Circulation views">{['borrow', 'return', 'loans'].map(value => <button key={value} aria-pressed={tab === value} className={tab === value ? '' : 'secondary'} onClick={() => { setTab(value); setStatus(value === 'loans' ? 'ACTIVE' : 'PENDING'); setPage(0) }}>{value === 'loans' ? 'Loans' : value === 'borrow' ? 'Borrow Requests' : 'Return Requests'}{value === 'borrow' && data.pending_counts ? ` (${data.pending_counts.BORROW ?? 0})` : value === 'return' && data.pending_counts ? ` (${data.pending_counts.RETURN ?? 0})` : ''}</button>)}</div><form className="ui-filter-toolbar circulation-filters" onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget); setSearch(String(f.get('search') || '')); setUser(String(f.get('user') || '')); setSince(String(f.get('since') || '')); setUntil(String(f.get('until') || '')); setPage(0) }}><label>Title / Accession<input name="search" maxLength={150} /></label><label>Borrower ID<input name="user" type="number" min={1} /></label><label>From<input name="since" type="datetime-local" /></label><label>Until<input name="until" type="datetime-local" /></label><label>Status<LuminarSelect value={status} onChange={e => { setStatus(e.target.value); setPage(0) }}>{(tab === 'loans' ? ['ACTIVE', 'RETURNED', 'all'] : ['PENDING', 'all', 'APPROVED', 'REJECTED', 'CANCELLED', 'EXPIRED', 'COMPLETED']).map(s => <option key={s}>{s}</option>)}</LuminarSelect></label><button>Filter</button></form></>}

      {!staff && <h2>Borrow Requests</h2>}<div className="inventory-books">{data.results.map(r => rowCard(r, staff && tab === 'loans'))}</div>{!loading && !error && !data.results.length && <StatePanel title={staff && tab === 'loans' ? 'No loans in this view' : 'No requests in this view'}>New activity will appear here when a patron requests a book or return.</StatePanel>}

      {!staff && <><h2>Current Loans</h2><p>Requested returns remain your responsibility until staff confirms physical receipt.</p><div className="inventory-books">{loans.results.filter(r => r.status === 'ACTIVE').map(r => rowCard(r, true))}</div>{!loading && !error && !loans.results.some(r => r.status === 'ACTIVE') && <p>No current loans in this view.</p>}<h2>Loan History</h2><div className="inventory-books">{loans.results.filter(r => r.status === 'RETURNED').map(r => rowCard(r, true))}</div>{!loading && !error && !loans.results.some(r => r.status === 'RETURNED') && <p>Your completed loans will appear here.</p>}</>}

      <div className="ui-pagination"><button className="ui-button ui-secondary" disabled={loading || !page} onClick={() => { setPage(p => p - 1); requestAnimationFrame(() => { const el = document.querySelector<HTMLElement>('.institutions'); if (el) { const top = el.getBoundingClientRect().top + window.scrollY - 64 - 8; const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches; window.scrollTo({ top: Math.max(0, top), behavior: reduced ? 'instant' : 'smooth' }) } }) }}>Previous</button><span>Page {page + 1}</span><button className="ui-button ui-secondary" disabled={loading || (page + 1) * 20 >= Math.max(data.total, loans.total)} onClick={() => { setPage(p => p + 1); requestAnimationFrame(() => { const el = document.querySelector<HTMLElement>('.institutions'); if (el) { const top = el.getBoundingClientRect().top + window.scrollY - 64 - 8; const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches; window.scrollTo({ top: Math.max(0, top), behavior: reduced ? 'instant' : 'smooth' }) } }) }}>Next</button></div>

    </>}

    {action && <Modal title={action.type === 'approve' ? 'Approve & Issue' : action.type === 'confirm' ? 'Confirm Received' : action.type === 'activate' ? 'Enable Approval Circulation' : action.type === 'staff-receive' ? 'Receive physical return' : action.type === 'staff-renew' ? 'Renew loan for member' : action.type.replaceAll('-', ' ')} busy={busy} onClose={() => setAction(null)}><div className="institutions">{action.row ? <><p>{action.row.title} · {action.row.accession_number}</p><p>Shelf / Location: {action.row.shelf_location || 'Not recorded'}</p>{action.row.borrower && <p>Borrower: {action.row.borrower.name} · {action.row.borrower.email}</p>}{action.type === 'approve' && <p>Confirm that you are handing this book to the borrower. The loan starts on confirmation. Proposed due date: {when(action.row.proposed_due_at)}.</p>}{action.type === 'staff-renew' && <p>Renew this member’s loan if it meets the library’s renewal policy.</p>}{(action.type === 'confirm' || action.type === 'staff-receive') && <p>Confirm that you have physically received and verified this book. This completes the return and releases its allocation.</p>}{action.type === 'return-request' && <p>This requests a physical return review. Your loan stays active until staff receives the book.</p>}</> : <p>Enable staff approval for this library after stock reconciliation. Active legacy loans require the migration tool.</p>}{action.type === 'reject' && <label>Reason (optional)<textarea maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></label>}{error && <p role="alert">{error}</p>}<button disabled={busy} onClick={() => void confirm()}>{busy ? 'Working…' : 'Confirm'}</button></div></Modal>}

  </div>

}



export function BookRequestControl({ libraryId, bookId, availability, changed }: { libraryId: string; bookId: string; availability: { requestable: number; circulation_status: string }; changed: (message?: string) => void }) {

  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [submitted, setSubmitted] = useState(false), [key] = useState(commandKey)

  const mounted = useRef(true)

  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])

  return <div><button disabled={submitted || busy || availability.requestable < 1 || availability.circulation_status !== 'CIRCULATING'} onClick={() => { setBusy(true); setError(''); void lendingCommand(`${lendingBase(libraryId)}/lending/borrow-requests`, { library_book_id: bookId }, key).then(() => { if (mounted.current) { setSubmitted(true); changed() } }).catch(reason => { if (mounted.current) setError(errorMessage(reason)) }).finally(() => { if (mounted.current) setBusy(false) }) }}>{busy ? 'Requesting…' : submitted ? 'Request submitted' : 'Request Book'}</button>{error && <p role="alert">{error}</p>}<Link to={patronPath(libraryId, 'my-library')}>View my requests</Link>{!submitted && availability.circulation_status === 'CIRCULATING' && availability.requestable > 0 && <AssistantLibraryRequestButton libraryId={libraryId} bookId={bookId} />}{availability.circulation_status === 'CIRCULATING' && availability.requestable === 0 && <ReservationControl key={`${libraryId}:${bookId}`} libraryId={libraryId} bookId={bookId} unavailable changed={() => changed('Reservation updated in the library waiting queue.')} />}</div>

}

