import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Modal } from './StaffUI'
import { patronPath } from '../lib/libraryWorkspace'
import { lendingCommand, commandKey } from '../lib/libraryLending'
import type { DisplayBook } from '../lib/libraryCatalogue'
import { useInstitutionStore } from '../store/useInstitutionStore'
import { useAuthStore } from '../store/useAuthStore'
import { resolveLibraryBookCapabilities } from '../lib/libraryBookCapabilities'
import { notifyBorrowChanged } from '../lib/api'
import { bookPath } from '../lib/bookPresentation'

export function CatalogueBookActions({ book, changed, concise = false }: { book: DisplayBook; changed: () => void; concise?: boolean }) {
  const token=useAuthStore(s=>s.token),state=useInstitutionStore()
  const current=state.libraries.find(row=>row.library_id===book.library_id)
  const capability=resolveLibraryBookCapabilities(book,current?.membership)
  const [busy, setBusy] = useState(false), [error, setError] = useState('')
  const [action, setAction] = useState<'reserve' | 'cancel_request' | 'cancel_reservation' | null>(null)
  const plan = useRef<{ action: string; key: string } | null>(null), alive = useRef(true), sending = useRef(false)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  async function run(kind: 'request' | 'reserve' | 'cancel_request' | 'cancel_reservation') {
    if (sending.current) return
    sending.current = true; setBusy(true); setError('')
    if (plan.current?.action !== kind) plan.current = { action: kind, key: commandKey() }
    const base = `/libraries/${encodeURIComponent(book.library_id)}`
    const endpoint = kind === 'request' ? `${base}/lending/borrow-requests` : kind === 'reserve' ? `${base}/reservations` :
      kind === 'cancel_request' ? `${base}/lending/borrow-requests/${book.user_request_state!.id}/cancel` : `${base}/reservations/${book.user_reservation_state!.id}/cancel`
    try {
      await lendingCommand(endpoint, ['request', 'reserve'].includes(kind) ? { library_book_id: book.library_book_id } : {}, plan.current.key)
      if (alive.current) { setAction(null); plan.current = null; notifyBorrowChanged(); changed() }
    } catch (reason) { if (alive.current) setError(reason instanceof Error ? reason.message : 'Unable to update this library book.') }
    finally { sending.current = false; if (alive.current) setBusy(false) }
  }
  if (!token || state.session!==token || book.source !== 'LIBRARY' || !book.owned_by_current_library || !book.library_book_id || current?.library_id !== book.library_id || current.membership?.status !== 'ACTIVE' || current.membership.role !== 'GENERAL_USER') return null
  return <div className="catalogue-actions">
    {concise && (book.user_request_state || book.user_reservation_state || book.user_loan_state) && <Link className="text-xs text-brand" to={bookPath(book)}>{book.user_loan_state ? 'On loan to you' : book.user_request_state ? 'Request pending' : 'Reservation details'}</Link>}
    {!concise && book.user_loan_state && <p className="catalogue-state">{book.user_loan_state.return_requested ? 'Return awaiting physical receipt' : 'On loan to you'}{book.user_loan_state.due_at && ` · Due ${new Date(book.user_loan_state.due_at).toLocaleDateString()}`} <Link to={patronPath(book.library_id, 'my-library')}>My Library</Link></p>}
    {!concise && book.user_request_state && <p className="catalogue-state">Borrow request · Awaiting librarian approval</p>}
    {!concise && book.user_reservation_state && <p className="catalogue-state">{book.user_reservation_state.status === 'WAITING' ? `Reservation position ${book.user_reservation_state.queue_position} of ${book.user_reservation_state.queue_length}` : 'Ready for borrow approval'}</p>}
    {capability.canRequestPhysical && (!concise || !(book.user_request_state || book.user_reservation_state || book.user_loan_state)) && <button className="ui-button" disabled={busy} onClick={() => void run('request')}>{busy ? 'Requesting…' : 'Request Book'}</button>}
    {capability.canJoinWaitlist && (!concise || !(book.user_request_state || book.user_reservation_state || book.user_loan_state)) && <button className="ui-button ui-secondary" disabled={busy} onClick={() => { plan.current = null; setAction('reserve') }}>Join Waitlist</button>}
    {capability.readPath && (!concise || (!capability.canRequestPhysical && !capability.canJoinWaitlist && !book.user_request_state && !book.user_reservation_state && !book.user_loan_state)) && <Link className={`ui-button${!concise && capability.hasPhysical ? ' ui-secondary' : ''}`} to={capability.readPath}>Read Online</Link>}
    {!concise && capability.knowMorePath && <Link className="ui-button ui-secondary" to={capability.knowMorePath}>Know More</Link>}
    {!concise && book.actions.cancel_request && <button className="ui-button ui-secondary" disabled={busy} onClick={() => { plan.current = null; setAction('cancel_request') }}>Cancel Request</button>}
    {!concise && book.actions.cancel_reservation && <button className="ui-button ui-secondary" disabled={busy} onClick={() => { plan.current = null; setAction('cancel_reservation') }}>Cancel Reservation</button>}
    {error && <p role="alert">{error}</p>}
    {action && <Modal title={action === 'reserve' ? 'Join Waitlist' : action === 'cancel_request' ? 'Cancel Request' : 'Cancel Reservation'} busy={busy} onClose={() => setAction(null)}>
      <p>{book.title}</p><p>{action === 'reserve' ? 'Join this library’s waiting queue. An available unit becomes a borrow request for staff approval.' : 'Cancel your current library request?'}</p>
      {error && <p role="alert">{error}</p>}<button className="ui-button" disabled={busy} onClick={() => void run(action)}>{busy ? 'Saving…' : 'Confirm'}</button>
    </Modal>}
  </div>
}

