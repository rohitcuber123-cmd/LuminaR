import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Modal } from '../components/StaffUI'
import { ActionMenu, PageHeading, StatePanel } from '../components/WorkspaceUI'
import { institutionApi } from '../lib/institutions'
import { inventoryBase, uploadInventory, commitInventory, type LibraryBook, type InventoryPage, type InventoryPreview, type InventoryResult } from '../lib/libraryInventory'
import { useAuthStore } from '../store/useAuthStore'
import { activeLibrary, useInstitutionStore } from '../store/useInstitutionStore'
import { BookRequestControl } from './LibraryCirculation'
import { commandKey, withdrawLibraryBook } from '../lib/libraryLending'
import { LibraryCopyCondition, RegisterLibraryCopy } from '../components/LibraryCopyControls'
import { LibraryStockEditor } from '../components/LibraryStockEditor'
import { catalogueChanged } from '../lib/catalogueInvalidation'
import './Staff.css'
import './Institutions.css'
import './LibraryInventory.css'

const errorText = (error: unknown) => error instanceof Error ? error.message : 'Unable to complete this inventory action.'
const values = (value: FormDataEntryValue | null) => String(value || '').split(';').map(v => v.trim()).filter(Boolean)
const optional = (fields: FormData, name: string) => String(fields.get(name) || '').trim() || null

export function LibraryInventoryPage() {
  const current = useInstitutionStore(activeLibrary)
  const session = useAuthStore(s => s.token)
  const [params] = useSearchParams()
  const initialView = params.get('action') === 'add' ? 'add' : params.get('action') === 'import' ? 'import' : 'inventory'
  if (!current?.membership || current.membership.status !== 'ACTIVE') return <div className="institutions"><h1>Library Inventory</h1><p>Select a library with active membership to view its inventory.</p><Link to="/libraries">Explore Libraries</Link></div>
  return <InventoryDetails key={`${current.library_id}:${session}:${current.membership.role}:${initialView}`} initialView={initialView} libraryId={current.library_id} name={current.name} role={current.membership.role} />
}

function InventoryDetails({ libraryId, name, role, initialView }: { libraryId: string; name: string; role: string; initialView: 'inventory' | 'add' | 'import' }) {
  const [view, setView] = useState(initialView)
  const [data, setData] = useState<InventoryPage>({ results: [], total: 0, has_more: false, role })
  const staff = ['ADMIN', 'LIBRARIAN'].includes(role) && ['ADMIN', 'LIBRARIAN'].includes(data.role)
  const [draft, setDraft] = useState(''), [search, setSearch] = useState(''), [kind, setKind] = useState('all'), [state, setState] = useState('active'), [page, setPage] = useState(0), [revision, setRevision] = useState(0)
  const [loading, setLoading] = useState(true), [busy, setBusy] = useState(false), [error, setError] = useState(''), [success, setSuccess] = useState('')
  const [action, setAction] = useState<{ type: 'view' | 'edit' | 'holding' | 'link' | 'withdraw' | 'copies'; row: LibraryBook; key?: string } | null>(null)
  const [copyRows, setCopyRows] = useState<{ copy_id: string; copy_number: number; barcode: string | null; status: string }[]>([])
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => {
    const controller = new AbortController(); let alive = true
    queueMicrotask(() => { if (alive) { setLoading(true); setError(''); setData({ results: [], total: 0, has_more: false, role }) } })
    institutionApi<InventoryPage>(`${inventoryBase(libraryId)}/books?search=${encodeURIComponent(search)}&kind=${kind}&state=${state}&offset=${page * 20}&limit=20`, 'GET', undefined, controller.signal)
      .then(result => { if (alive) setData(result) })
      .catch(reason => { if (alive) { setError(errorText(reason)); setAction(null) } })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false; controller.abort() }
  }, [libraryId, search, kind, state, page, revision, role])
  async function run(operation: () => Promise<unknown>, message: string) {
    setBusy(true); setError('')
    try {
      await operation()
      catalogueChanged(libraryId)
      if (mounted.current) { setSuccess(message); setAction(null); setRevision(r => r + 1) }
      return true
    } catch (reason) { if (mounted.current) setError(errorText(reason)); return false }
    finally { if (mounted.current) setBusy(false) }
  }
  const base = inventoryBase(libraryId)
  const readyStaff = staff && !error
  function showCopies(row: LibraryBook) {
    setCopyRows([]); setAction({ type: 'copies', row, key: commandKey() })
    void institutionApi<{ results: typeof copyRows }>(`${base}/books/${row.library_book_id}/copies`).then(r => { if (mounted.current) setCopyRows(r.results) }).catch(reason => { if (mounted.current) { setError(errorText(reason)); setAction(null) } })
  }
  const filtered = !!search || kind !== 'all' || state !== 'active'
  return <div className="institutions library-inventory">
    <PageHeading title={staff ? 'Inventory' : 'Browse Books'} description={staff ? `Manage the collection at ${name}.` : `Find a book in ${name} and check its shelf and availability.`} actions={staff && <><button disabled={loading || !!error} onClick={() => { setView('add'); setSuccess('') }}>Add Book</button><button className="secondary" disabled={loading || !!error} onClick={() => { setView('import'); setSuccess('') }}>Upload Inventory</button></>} />
    {!loading && data.lending_state !== 'CANONICAL' && <p className="inventory-note">Circulation setup required. Inventory counts are snapshots until staff reconciles historical records and completes migration.</p>}
    {error && <StatePanel kind="error" title="Unable to load inventory" action={<button className="secondary" onClick={() => setRevision(r => r + 1)}>Retry</button>}>{error}</StatePanel>}
    {success && <p role="status" className="institution-success">{success}</p>}
    <form className="ui-filter-toolbar" onSubmit={e => { e.preventDefault(); setSearch(draft); setPage(0) }}><label className="inventory-search">Search collection<input aria-label="Search library inventory" value={draft} maxLength={150} onChange={e => setDraft(e.target.value)} placeholder="Title, subject, author or accession" /></label><label>Records<select aria-label="Record filter" value={kind} onChange={e => { setKind(e.target.value); setPage(0) }}><option value="all">All records</option><option value="global">Global Linked</option><option value="local">Local Only</option><option value="review">Needs Review</option></select></label><label>State<select aria-label="Inventory state" value={state} onChange={e => { setState(e.target.value); setPage(0) }}><option value="active">Active</option><option value="withdrawn">Withdrawn</option><option value="all">All states</option></select></label><button>Search</button></form>
    {loading ? <StatePanel kind="loading" title="Loading collection…" /> : !error && <>
      {!data.results.length ? <StatePanel title={filtered ? 'No books match these filters' : `No active books in ${name}`} action={staff && !filtered ? <><button onClick={() => setView('add')}>Add First Book</button><button className="secondary" onClick={() => setView('import')}>Upload Inventory</button></> : filtered ? <button className="secondary" onClick={() => { setDraft(''); setSearch(''); setKind('all'); setState('active'); setPage(0) }}>Clear filters</button> : undefined}>{filtered ? 'Try a different title, subject or record filter.' : staff ? 'Start your collection with a book or import an inventory file.' : 'Library staff has not added books to this collection yet.'}</StatePanel> : <>
        <p className="ui-result-count">{data.total} {data.total === 1 ? 'record' : 'records'}</p>
        {staff ? <div className="ui-table-wrap" tabIndex={0} role="region" aria-label="Library inventory table"><table className="ui-table inventory-table"><thead><tr><th>Accession</th><th>Title</th><th>Subject / Genre</th><th>Shelf</th><th>Stock</th><th>{data.lending_state === 'CANONICAL' ? 'Available to request' : 'Available snapshot'}</th><th>Status</th><th>Actions</th></tr></thead><tbody>{data.results.map(row => <tr key={row.library_book_id}><td className="inventory-accession">{row.accession_number}</td><td><h2>{row.title}</h2><small>{row.global_work_id ? 'Global linked' : 'Library record'}{row.needs_review ? ' · Needs review' : ''}</small></td><td>{row.subjects.join('; ')}</td><td>{row.holding?.shelf_location || '—'}</td><td>{row.holding?.total_copies ?? '—'}</td><td>{data.lending_state === 'CANONICAL' ? row.availability?.requestable ?? '—' : row.holding?.available_copies ?? '—'}</td><td><span className="ui-badge">{row.status === 'WITHDRAWN' ? 'Withdrawn' : row.availability?.circulation_status?.replaceAll('_', ' ') || 'Active'}</span></td><td><ActionMenu label={row.accession_number} actions={[
          { label: 'View details', run: () => setAction({ type: 'view', row }) },
          ...(row.status === 'ACTIVE' ? [
            { label: 'Edit metadata', disabled: busy, run: () => setAction({ type: 'edit', row, key: commandKey() }) },
            { label: data.lending_state === 'CANONICAL' ? 'Manage Stock & Shelf' : 'Inventory quantities', disabled: busy, run: () => setAction({ type: 'holding', row, key: commandKey() }) },
            { label: 'Link Global Catalogue Book', disabled: busy, run: () => setAction({ type: 'link', row, key: commandKey() }) },
            { label: 'Withdraw', danger: true, disabled: busy, run: () => setAction({ type: 'withdraw', row, key: commandKey() }) },
          ] : []),
          { label: 'Copy identities', disabled: busy, run: () => showCopies(row) },
        ]} /></td></tr>)}</tbody></table></div> : <div className="inventory-books">{data.results.map(row => <article className="inventory-book" key={row.library_book_id}><span className="inventory-accession">{row.accession_number}</span><h2>{row.title}</h2><p>{row.subjects.join('; ')}{row.authors?.length ? ` · ${row.authors.join('; ')}` : ''}</p><dl><div><dt>Shelf / Location</dt><dd>{row.holding?.shelf_location || 'Not recorded'}</dd></div><div><dt>Stock</dt><dd>{row.holding?.total_copies ?? '—'}</dd></div></dl>{row.availability && <><p>{row.availability.requestable} available to request · {row.availability.circulation_status.replaceAll('_', ' ')}</p>{role === 'GENERAL_USER' && <BookRequestControl libraryId={libraryId} bookId={row.library_book_id} availability={row.availability} changed={message => { setSuccess(message || 'Book requested. Awaiting librarian approval.'); setRevision(r => r + 1) }} />}</>}</article>)}</div>}
        <div className="ui-pagination"><button className="secondary" disabled={!page} onClick={() => setPage(p => p - 1)}>Previous</button><span>Page {page + 1}</span><button className="secondary" disabled={!data.has_more} onClick={() => setPage(p => p + 1)}>Next</button></div>
      </>}
    </>}
    {view === 'add' && readyStaff && <Modal title="Add Book" onClose={() => setView('inventory')}><div className="institutions inventory-dialog"><BookEditor hideHeading libraryId={libraryId} onSaved={row => { if (mounted.current) { setSuccess(`Book added successfully. Accession number: ${row.accession_number}.`); setView('inventory'); setRevision(r => r + 1) } }} /></div></Modal>}
    {view === 'import' && readyStaff && <Modal title="Upload Inventory" onClose={() => setView('inventory')}><div className="institutions inventory-dialog"><InventoryImport hideHeading libraryId={libraryId} onCommitted={() => { if (mounted.current) setRevision(r => r + 1) }} /></div></Modal>}
    {action && (staff || action.type === 'copies') && <Modal title={`${action.type === 'view' ? 'Book details' : action.type === 'edit' ? 'Edit book' : action.type === 'holding' ? data.lending_state === 'CANONICAL' ? 'Manage Stock & Shelf' : 'Inventory quantities' : action.type === 'link' ? 'Link Global Catalogue Book' : action.type === 'copies' ? 'Copy identities' : 'Withdraw book'} · ${action.row.accession_number}`} busy={busy} onClose={() => setAction(null)}><div className="institutions inventory-dialog">
      {action.type === 'view' && <><h2>{action.row.title}</h2><dl className="ui-details"><div><dt>Subject / Genre</dt><dd>{action.row.subjects.join('; ')}</dd></div><div><dt>Author(s)</dt><dd>{action.row.authors?.join('; ') || 'Not recorded'}</dd></div><div><dt>ISBN</dt><dd>{action.row.isbn_13 || action.row.isbn_10 || 'Not recorded'}</dd></div><div><dt>Shelf / Location</dt><dd>{action.row.holding.shelf_location || 'Not recorded'}</dd></div><div><dt>Stock</dt><dd>{action.row.holding.total_copies}</dd></div></dl>{action.row.description && <p>{action.row.description}</p>}</>}
      {action.type === 'edit' && <BookEditor libraryId={libraryId} initial={action.row} onSaved={() => { if (mounted.current) { setAction(null); setSuccess('Library metadata saved. Accession remains unchanged.'); setRevision(r => r + 1) } }} />}
      {action.type === 'holding' && data.lending_state === 'CANONICAL' && <LibraryStockEditor libraryId={libraryId} row={action.row} saved={() => { setAction(null); setRevision(r => r + 1); setSuccess('Stock / shelf updated.') }} />}
      {action.type === 'holding' && data.lending_state !== 'CANONICAL' && <form className="institution-form" onSubmit={e => { e.preventDefault(); const fields = new FormData(e.currentTarget); void run(() => institutionApi(`${base}/books/${action.row.library_book_id}/holding`, 'PUT', { total_copies: Number(fields.get('total')), available_copies: Number(fields.get('available')) }), 'Inventory snapshot updated.') }}><p>These counts do not change the legacy lending system.</p><label>Total copies<input type="number" name="total" min={0} max={1000000} required defaultValue={action.row.holding.total_copies} /></label><label>Available inventory snapshot<input type="number" name="available" min={0} max={1000000} required defaultValue={action.row.holding.available_copies} /></label><button disabled={busy}>Save Quantities</button></form>}
      {action.type === 'link' && <form className="institution-form" onSubmit={e => { e.preventDefault(); const fields = new FormData(e.currentTarget); void run(() => institutionApi(`${base}/books/${action.row.library_book_id}/global-link`, 'PUT', { global_work_id: optional(fields, 'work'), ...(data.lending_state === 'CANONICAL' ? { idempotency_key: action.key } : {}) }), 'Global catalogue link saved; local identity and accession preserved.') }}><p>Use a verified catalogue reference. Leave it empty to remove the link. Your library record and accession stay the same.</p><label>Catalogue reference<input name="work" maxLength={100} defaultValue={action.row.global_work_id || ''} /></label><a href="/catalog" target="_blank" rel="noreferrer">Browse the global catalogue</a><button disabled={busy}>Save Global Link</button></form>}
      {action.type === 'withdraw' && <><p>Withdraw “{action.row.title}”? Its history and accession number will be preserved.</p><button disabled={busy} onClick={() => void run(() => data.lending_state === 'CANONICAL' ? withdrawLibraryBook(`${base}/books/${action.row.library_book_id}`, action.key!) : institutionApi(`${base}/books/${action.row.library_book_id}`, 'DELETE'), 'Book withdrawn. Its accession will never be reused.')}>Confirm Withdraw</button></>}
      {action.type === 'copies' && <><p>Known copy identities are recorded separately. Aggregate quantities have no invented historical barcodes.</p>{copyRows.map(copy => <div key={copy.copy_id}><p>Copy {copy.copy_number} · {copy.barcode || 'No barcode recorded'} · {copy.status}</p>{staff && data.lending_state === 'CANONICAL' && <LibraryCopyCondition libraryId={libraryId} bookId={action.row.library_book_id} copy={copy} saved={() => { setAction(null); setRevision(r => r + 1) }} />}</div>)}{!copyRows.length && <p>No individual copy identities registered.</p>}{staff && data.lending_state === 'CANONICAL' && <RegisterLibraryCopy libraryId={libraryId} bookId={action.row.library_book_id} saved={() => { setAction(null); setRevision(r => r + 1) }} />}</>}
      {error && <p role="alert" className="institution-error">{error}</p>}
    </div></Modal>}
  </div>
}

export function BookEditor({ libraryId, initial, onSaved, hideHeading = false }: { libraryId: string; initial?: LibraryBook; onSaved: (row: LibraryBook) => void; hideHeading?: boolean }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [key] = useState(commandKey)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); const fields = new FormData(event.currentTarget)
    const subjects = values(fields.get('subjects'))
    if (!subjects.length) { setError('At least one Subject / Genre is required.'); return }
    const data = { idempotency_key: key, title: String(fields.get('title') || '').trim(), subjects, authors: values(fields.get('authors')), isbn: optional(fields, 'isbn'),
      publisher: optional(fields, 'publisher'), publication_year: fields.get('year') ? Number(fields.get('year')) : null,
      edition: optional(fields, 'edition'), language: optional(fields, 'language'), description: optional(fields, 'description'),
      local_call_number: optional(fields, 'call'), shelf_location: optional(fields, 'shelf'), local_tags: values(fields.get('tags')), acquisition_note: optional(fields, 'note'),
      ...(!initial ? { circulation_status: fields.get('circulation_status') || 'CIRCULATING', copies: fields.get('copies') ? Number(fields.get('copies')) : 1, barcode: optional(fields, 'barcode'), global_work_id: optional(fields, 'work') } : {}) }
    setBusy(true)
    try { const row = await institutionApi<LibraryBook>(`${inventoryBase(libraryId)}/books${initial ? '/' + initial.library_book_id : ''}`, initial ? 'PATCH' : 'POST', data); catalogueChanged(libraryId); onSaved(row) }
    catch (reason) { setError(errorText(reason)) } finally { setBusy(false) }
  }
  return <form className="institution-form inventory-editor" onSubmit={submit}>{!hideHeading && <h2>{initial ? 'Library metadata' : 'Add Book'}</h2>}<p>Only Title and Subject / Genre are required. ISBN, author and a global catalogue link are optional.</p>
    {initial && <label>Accession number<input readOnly value={initial.accession_number} /></label>}
    <label>Title *<input name="title" required maxLength={500} defaultValue={initial?.title} /></label><label>Subject / Genre *<input name="subjects" required maxLength={4000} defaultValue={initial?.subjects.join('; ')} /><small>Separate multiple values with semicolons. Use your institution’s own subjects.</small></label>
    <details><summary>Optional bibliographic details</summary><div className="inventory-optional">
      <label>Author(s)<input name="authors" maxLength={4000} defaultValue={initial?.authors?.join('; ')} /><small>Separate authors with semicolons.</small></label><label>ISBN<input name="isbn" maxLength={40} defaultValue={initial?.isbn_13 || initial?.isbn_10 || ''} /></label><label>Publisher<input name="publisher" maxLength={300} defaultValue={initial?.publisher || ''} /></label><label>Publication Year<input name="year" type="number" min={1} max={new Date().getFullYear() + 1} defaultValue={initial?.publication_year || ''} /></label><label>Edition<input name="edition" maxLength={100} defaultValue={initial?.edition || ''} /></label><label>Language<input name="language" maxLength={100} defaultValue={initial?.language || ''} /></label><label>Description<textarea name="description" maxLength={4000} defaultValue={initial?.description || ''} /></label>
    </div></details>
    <h3>Shelf / Location</h3><label>Shelf Location<input name="shelf" maxLength={200} defaultValue={initial?.shelf_location || ''} /></label><label>Call Number<input name="call" maxLength={100} defaultValue={initial?.local_call_number || ''} /></label>{!initial && <fieldset><legend>Set Stock & Availability</legend><label>Copies<input name="copies" type="number" min={0} max={1000000} placeholder="1" /><small>Total copies; defaults to one. Requestable availability is calculated from stock and circulation.</small></label><label>Circulation Status<select name="circulation_status" defaultValue="CIRCULATING">{['CIRCULATING', 'REFERENCE_ONLY', 'TEMPORARILY_UNAVAILABLE', 'WITHDRAWN'].map(value => <option key={value}>{value}</option>)}</select></label></fieldset>}<details><summary>Library details (optional)</summary><div className="inventory-optional">
      <label>Local Tags<input name="tags" maxLength={4000} defaultValue={initial?.local_tags?.join('; ')} /></label><label>Acquisition Note<textarea name="note" maxLength={1000} defaultValue={initial?.acquisition_note || ''} /></label>{!initial && <label>Known Barcode<input name="barcode" maxLength={128} /><small>Optional; no barcode will be invented.</small></label>}
    </div></details>
    {!initial && <details><summary>Link Global Catalogue Book (optional)</summary><label>Catalogue reference<input name="work" maxLength={100} /></label><p>Leave empty for a valid library record. A supplied reference must resolve in the global catalogue.</p><a href="/catalog" target="_blank" rel="noreferrer">Browse global catalogue</a></details>}
    {error && <p role="alert" className="institution-error">{error}</p>}<button disabled={busy}>{busy ? 'Saving…' : initial ? 'Save Book' : 'Save New Book'}</button>
  </form>
}

export function InventoryImport({ libraryId, onCommitted, hideHeading = false }: { libraryId: string; onCommitted: () => void; hideHeading?: boolean }) {
  const [preview, setPreview] = useState<InventoryPreview | null>(null), [result, setResult] = useState<InventoryResult | null>(null)
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [policy, setPolicy] = useState('skip'), [page, setPage] = useState(0)
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const file = (event.currentTarget.elements.namedItem('file') as HTMLInputElement | null)?.files?.[0]
    if (!file?.size) { setError('Choose a CSV or XLSX inventory file.'); return }
    if (file.size > 5 * 1024 * 1024) { setError('Inventory files must be at most 5 MiB.'); return }
    setBusy(true); setError(''); setPreview(null); setResult(null); setPage(0)
    try { setPreview(await uploadInventory(libraryId, file)) } catch (reason) { setError(errorText(reason)) } finally { setBusy(false) }
  }
  const rows = result?.rows || preview?.rows || []
  return <section className="inventory-import">{!hideHeading && <h2>Upload Inventory</h2>}<p>Minimum required columns: <strong>title</strong> and <strong>subject or genre</strong>. All bibliographic identifiers and other metadata are optional.</p><p>CSV (UTF-8) or XLSX, up to 5 MiB and 2,000 rows. Separate subjects/authors/tags with semicolons. Formulas are never executed.</p><p><a download="luminar-inventory-minimal.csv" href="data:text/csv;charset=utf-8,title%2Csubject%0AOperating%20Systems%20Laboratory%20Manual%2COperating%20Systems%0A">Download minimal template</a></p>
    <form className="institution-form" onSubmit={upload}><label>Inventory file<input name="file" type="file" accept=".csv,.xlsx" required /></label><button disabled={busy}>{busy ? 'Working…' : 'Preview Inventory'}</button></form>{error && <p role="alert" className="institution-error">{error}</p>}
    {preview && <div className="inventory-preview"><h2>{result ? 'Import result' : 'Inventory preview'}</h2><p>{preview.filename} · {preview.rows_total} rows</p><div className="inventory-counts"><span>{preview.rows_valid} valid</span><span>{preview.rows_invalid} invalid</span><span>{preview.global_matches} global matches</span><span>{preview.new_library_records} new library records</span><span>{preview.existing_holdings} existing holdings</span><span>{preview.possible_duplicates} possible duplicates</span></div>
      <p>Possible duplicates remain separate records. Existing verified identities follow your selected policy. Preview does not allocate accession numbers.</p>
      {!result && <><label className="inventory-policy">Existing holding policy<select aria-label="Existing holding policy" value={policy} onChange={e => setPolicy(e.target.value)}><option value="skip">Skip existing holding</option><option value="increase_quantity">Increase quantity</option></select></label><button disabled={busy || !preview.rows_valid} onClick={() => { setBusy(true); setError(''); void commitInventory(libraryId, preview.import_id, policy).then(value => { setResult(value); setPage(0); onCommitted() }).catch(reason => setError(errorText(reason))).finally(() => setBusy(false)) }}>Confirm Import</button></>}
      {result && <p role="status" className="institution-success">{result.status}: {result.created_records} created, {result.increased_holdings} quantities increased, {result.skipped_existing} existing skipped, {result.invalid_rows} invalid.</p>}
      <div className="institution-table-wrap" tabIndex={0} aria-label="Inventory import row results"><table><thead><tr><th>Row</th><th>Title</th><th>Classification</th><th>Result / reason</th><th>Accession</th></tr></thead><tbody>{rows.slice(page * 20, page * 20 + 20).map(row => <tr key={row.row_number}><td>{row.row_number}</td><td>{row.title || '—'}</td><td>{row.classification.replaceAll('_', ' ')}</td><td>{row.reason || row.outcome?.replaceAll('_', ' ') || 'Ready'}</td><td>{row.accession_number || (row.classification === 'INVALID' || result ? '—' : 'Assigned on creation')}</td></tr>)}</tbody></table></div><div className="institution-actions"><button disabled={!page} onClick={() => setPage(p => p - 1)}>Previous rows</button><span>Page {page + 1}</span><button disabled={(page + 1) * 20 >= rows.length} onClick={() => setPage(p => p + 1)}>Next rows</button></div>
    </div>}
  </section>
}
