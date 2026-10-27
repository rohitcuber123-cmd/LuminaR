import { LuminarSelect } from './LuminarSelect'
import { useState } from 'react'
import { commandKey, lendingBase, lendingCommand } from '../lib/libraryLending'
import { inventoryBase } from '../lib/libraryInventory'

export function LibraryCopyCondition({ libraryId, bookId, copy, saved }: { libraryId: string; bookId: string; copy: { copy_id: string; status: string }; saved: () => void }) {
  const [status, setStatus] = useState(copy.status), [key, setKey] = useState(commandKey), [busy, setBusy] = useState(false), [error, setError] = useState('')
  const allocated = ['BORROWED', 'HELD_FOR_REQUEST', 'RESERVED'].includes(copy.status)
  return <div><label>Condition for copy {copy.copy_id}<LuminarSelect value={status} disabled={busy || allocated} onChange={e => { setStatus(e.target.value); setKey(commandKey()) }}>{[...new Set([copy.status, 'AVAILABLE', 'LOST', 'DAMAGED', 'WITHDRAWN'])].map(s => <option key={s}>{s}</option>)}</LuminarSelect></label><button disabled={busy || allocated || status === copy.status} onClick={() => { setBusy(true); setError(''); void lendingCommand(`${lendingBase(libraryId)}/staff/lending/books/${bookId}/copies/${copy.copy_id}/condition`, { status }, key, 'PUT').then(saved).catch(e => setError(e instanceof Error ? e.message : 'Unable to update copy.')).finally(() => setBusy(false)) }}>Save Copy Condition</button>{allocated && <p>This copy is allocated. Complete its request or physical return before changing its condition.</p>}{error && <p role="alert">{error}</p>}</div>
}

export function RegisterLibraryCopy({ libraryId, bookId, saved }: { libraryId: string; bookId: string; saved: () => void }) {
  const [key] = useState(commandKey), [busy, setBusy] = useState(false), [error, setError] = useState('')
  return <form className="institution-form" onSubmit={e => {
    e.preventDefault(); const fields = new FormData(e.currentTarget); setBusy(true); setError('')
    void lendingCommand(`${inventoryBase(libraryId)}/books/${bookId}/copies`, { barcode: String(fields.get('barcode') || '').trim() || null, status: 'AVAILABLE' }, key).then(saved).catch(e => setError(e instanceof Error ? e.message : 'Unable to register copy.')).finally(() => setBusy(false))
  }}><h3>Register a Known Physical Copy</h3><p>Register only a physical unit you have verified. This records its identity within existing total stock.</p><label>Known Barcode (optional)<input name="barcode" maxLength={128} /></label><button disabled={busy}>Register Known Copy</button>{error && <p role="alert">{error}</p>}</form>
}
