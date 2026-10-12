import { useState, type FormEvent } from 'react'
import { commandKey, lendingCommand, lendingBase } from '../lib/libraryLending'
import type { LibraryBook } from '../lib/libraryInventory'

export function LibraryStockEditor({ libraryId, row, saved }: { libraryId: string; row: LibraryBook; saved: () => void }) {
  const [key] = useState(commandKey), [shelfKey] = useState(commandKey), [busy, setBusy] = useState(false), [error, setError] = useState('')
  const holding = row.holding as typeof row.holding & { allocation_mode?: string; unavailable_stock?: number; circulation_status?: string }
  async function submit(e: FormEvent<HTMLFormElement>, shelf = false) {
    e.preventDefault(); const fields = new FormData(e.currentTarget); setBusy(true); setError('')
    try {
      await lendingCommand(`${lendingBase(libraryId)}/staff/lending/books/${row.library_book_id}/${shelf ? 'shelf' : 'stock'}`, shelf ? { shelf_location: fields.get('shelf') || null, call_number: fields.get('call') || null } : { total_copies: Number(fields.get('total')), unavailable_stock: Number(fields.get('unavailable')), allocation_mode: fields.get('mode'), circulation_status: fields.get('status') }, shelf ? shelfKey : key, 'PUT')
      saved()
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to update stock.') } finally { setBusy(false) }
  }
  return <div><h2>Manage Stock</h2><p>Requestable availability is derived from total stock, pending holds, active loans and unavailable units.</p><form className="institution-form" onSubmit={e => void submit(e)}><label>Total copies<input name="total" type="number" min={0} max={1000000} required defaultValue={holding.total_copies} /></label><label>Other unavailable units<input name="unavailable" type="number" min={0} max={1000000} required defaultValue={holding.unavailable_stock ?? 0} /></label><label>Circulation Status<select name="status" defaultValue={holding.circulation_status ?? 'CIRCULATING'}>{['CIRCULATING', 'REFERENCE_ONLY', 'TEMPORARILY_UNAVAILABLE', 'WITHDRAWN'].map(s => <option key={s}>{s}</option>)}</select></label><label>Allocation mode<select name="mode" defaultValue={holding.allocation_mode ?? 'AGGREGATE'}><option>AGGREGATE</option><option>COPY</option></select><small>Copy mode requires every unit to have a verified copy identity. Existing holds and loans prevent mode changes.</small></label><button disabled={busy}>Save Stock</button></form><h2>Shelf / Location</h2><form className="institution-form" onSubmit={e => void submit(e, true)}><label>Shelf Location<input name="shelf" maxLength={200} defaultValue={holding.shelf_location ?? ''} /></label><label>Call Number<input name="call" maxLength={100} defaultValue={holding.call_number ?? ''} /></label><button disabled={busy}>Save Shelf</button></form>{error && <p role="alert">{error}</p>}</div>
}
