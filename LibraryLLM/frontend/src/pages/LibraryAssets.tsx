import { LuminarSelect } from '../components/LuminarSelect'
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { libraryReadOnlinePath, libraryKnowMorePath } from '../lib/libraryBookCapabilities'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { PageHeading, StatePanel } from '../components/WorkspaceUI'
import { Modal, date } from '../components/StaffUI'
import { KnowledgeTools } from '../components/knowledge/KnowledgeTools'
import { LibraryBookTitleLink } from '../components/LibraryBookTitleLink'
import { observeCatalogue } from '../lib/catalogueInvalidation'
import { institutionApi } from '../lib/institutions'
import { inventoryBase, type InventoryPage } from '../lib/libraryInventory'
import { assetFile, assetPath, assetStatusText, assetVisibilityText, fetchAsset, fetchAssets, mutateAsset, uploadAsset, type AssetPage, type AssetVisibility, type LibraryAsset } from '../lib/libraryAssets'
import { libraryRole, libraryBookPath } from '../lib/libraryWorkspace'
import { scrollToContentAnchor } from '../lib/paginationScroll'
import { useAuthStore } from '../store/useAuthStore'
import { useInstitutionStore } from '../store/useInstitutionStore'
import './LibraryAssets.css'
import { useAssistantStore } from '../store/useAssistantStore'
import { useLocation } from 'react-router-dom'

const errorText = (error: unknown) => error instanceof Error ? error.message : 'Unable to complete this document action.'
const pending = (asset: LibraryAsset) => ['UPLOADING', 'PROCESSING', 'DELETING'].includes(asset.status)
const permitted = (asset: LibraryAsset, staff: boolean) => staff || asset.visibility === 'MEMBERS' && asset.status === 'READY'

const ACCEPTED_TYPES = 'application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.pdf,.txt,.docx'

function AssetFacts({ asset, staff }: { asset: LibraryAsset; staff: boolean }) {
  return <dl className="asset-facts">
    <div><dt>Type</dt><dd>{asset.asset_type} · {(asset.byte_size / 1024).toLocaleString(undefined, { maximumFractionDigits: 1 })} KB</dd></div>
    <div><dt>Status</dt><dd>{assetStatusText(asset.status)}</dd></div>
    {staff && <div><dt>Visibility</dt><dd>{assetVisibilityText(asset.visibility)}</dd></div>}
    <div><dt>Added</dt><dd>{date(asset.created_at)}</dd></div>
    {staff && <div><dt>Uploader</dt><dd>{asset.uploader_name || 'Library staff'}</dd></div>}
    {asset.library_book_id && <div><dt>Linked book</dt><dd><LibraryBookTitleLink libraryId={asset.library_id} bookId={asset.library_book_id} staff={staff} title={asset.linked_book_title || 'Linked library book'} /></dd></div>}
  </dl>
}

function AssetGate({ staff, children }: { staff: boolean; children: (libraryId: string, name: string, token: string) => React.ReactNode }) {
  const { libraryId = '' } = useParams(), token = useAuthStore(s => s.token), state = useInstitutionStore()
  const library = state.libraries.find(row => row.library_id === libraryId), role = libraryRole(library)
  if (!token || state.session !== token) return <StatePanel title="Loading library permissions…" kind="loading" />
  if (!library || staff && !['ADMIN', 'LIBRARIAN'].includes(role || '') || !staff && role !== 'GENERAL_USER') return <StatePanel title={staff ? 'Staff membership required' : 'Patron membership required'}>Open a library workspace where you have an active membership.</StatePanel>
  return <div key={`${libraryId}:${token}:${role}`} className={staff ? 'institutions library-assets' : 'institutions library-assets asset-patron-page'}>{children(libraryId, library.name, token)}</div>
}

export function LibraryAssetsPage({ staff = false }: { staff?: boolean }) {
  return <AssetGate staff={staff}>{(libraryId, name, token) => <AssetList libraryId={libraryId} name={name} token={token} staff={staff} />}</AssetGate>
}

function AssetList({ libraryId, name, token, staff }: { libraryId: string; name: string; token: string; staff: boolean }) {
  const [params]=useSearchParams(),bookId=params.get('book')
  const [draft, setDraft] = useState(''), [search, setSearch] = useState(''), [visibility, setVisibility] = useState(''), [status, setStatus] = useState(''), [offset, setOffset] = useState(0), [revision, setRevision] = useState(0), [upload, setUpload] = useState(false)
  const [result, setResult] = useState<{ key: string; data?: AssetPage; error?: string } | null>(null)
  const key = `${libraryId}:${token}:${search}:${visibility}:${status}:${offset}:${revision}:${bookId}`
  useEffect(() => {
    let alive = true; const controller = new AbortController()
    const query = new URLSearchParams({ search, offset: String(offset), limit: '20', ...(visibility ? { visibility } : {}), ...(status ? { status } : {}),...(bookId?{library_book_id:bookId}:{}) })
    void fetchAssets(libraryId, query.toString(), controller.signal).then(data => { if (alive && !controller.signal.aborted && useAuthStore.getState().token === token) setResult({ key, data }) }).catch(error => { if (alive && !controller.signal.aborted) setResult({ key, error: errorText(error) }) })
    return () => { alive = false; controller.abort() }
  }, [libraryId, token, search, visibility, status, offset, key, bookId])
  const data = result?.key === key ? result.data : undefined, error = result?.key === key ? result.error : undefined
  useEffect(() => { const refresh = () => setRevision(value => value + 1); window.addEventListener('focus', refresh); const timer = data?.results.some(pending) ? setInterval(refresh, 3000) : undefined; return () => { window.removeEventListener('focus', refresh); if (timer) clearInterval(timer) } }, [data])
  return <>
    <PageHeading title={staff ? 'Digital Assets' : 'Library Resources'} description={staff ? `Manage documents owned by ${name}.` : `Read and explore documents shared with ${name}'s members.`} actions={staff && <button className="ui-button" onClick={() => setUpload(true)}>Upload Document</button>} />
    <form className="ui-filter-toolbar" onSubmit={event => { event.preventDefault(); setSearch(draft); setOffset(0) }}><label className="asset-search" htmlFor="asset-search">Search documents<input id="asset-search" value={draft} maxLength={150} placeholder="Title or filename" onChange={event => setDraft(event.target.value)} /></label>{staff && <><label htmlFor="asset-visibility-filter">Visibility<LuminarSelect id="asset-visibility-filter" value={visibility} onChange={event => { setVisibility(event.target.value); setOffset(0) }}><option value="">All visibility</option><option value="MEMBERS">Library members</option><option value="STAFF_ONLY">Staff only</option></LuminarSelect></label><label htmlFor="asset-status-filter">Processing status<LuminarSelect id="asset-status-filter" value={status} onChange={event => { setStatus(event.target.value); setOffset(0) }}><option value="">All current states</option>{['UPLOADING', 'PROCESSING', 'READY', 'FAILED'].map(value => <option key={value} value={value}>{assetStatusText(value as LibraryAsset['status'])}</option>)}</LuminarSelect></label></>}<button className="ui-button">Search</button><button className="ui-button ui-secondary" type="button" onClick={() => setRevision(value => value + 1)}>Refresh documents</button></form>
    {error ? <StatePanel title="Unable to load documents" kind="error" action={<button className="ui-button ui-secondary" onClick={() => setRevision(value => value + 1)}>Retry</button>}>{error}</StatePanel> : !data ? <StatePanel title="Loading library documents…" kind="loading" /> : <><p className="ui-result-count">{data.total} {data.total === 1 ? 'document' : 'documents'}</p>{!data.results.length ? <StatePanel title={search || visibility || status ? 'No documents match these filters' : staff ? 'No library documents yet' : 'No resources available yet'}>{staff ? 'Upload a PDF, TXT or DOCX and choose who can access it.' : 'Library staff can share ready documents with members.'}</StatePanel> : <div className="asset-list">{data.results.filter(asset => permitted(asset, staff)).map(asset => <article className="ui-card asset-card" key={asset.asset_id}><div className="asset-card-heading"><h2><Link to={assetPath(libraryId, staff, asset.asset_id)}>{asset.title}</Link></h2><span className="ui-badge">{assetStatusText(asset.status)}</span></div><p className="asset-filename">{asset.original_filename}</p><AssetFacts asset={asset} staff={staff} />{pending(asset) && <p role="status">{asset.status === 'DELETING' ? 'Document access has been revoked. Cleanup is in progress.' : 'Preparing text and document Q&A. This page refreshes while processing.'}</p>}{asset.status === 'FAILED' && <p>Processing did not finish. Open the document to review its status and retry.</p>}<Link className="ui-button ui-secondary" to={assetPath(libraryId, staff, asset.asset_id)}>{asset.status === 'READY' ? 'Read / Ask LuminaR' : 'View document'}</Link></article>)}</div>}<div className="ui-pagination"><button className="ui-button ui-secondary" disabled={!offset} onClick={() => { setOffset(value => Math.max(0, value - 20)); requestAnimationFrame(() => scrollToContentAnchor('.asset-list, .library-assets')) }}>Previous</button><span>Page {Math.floor(offset / 20) + 1}</span><button className="ui-button ui-secondary" disabled={offset + 20 >= data.total} onClick={() => { setOffset(value => value + 20); requestAnimationFrame(() => scrollToContentAnchor('.asset-list, .library-assets')) }}>Next</button></div></>}
    {upload && <AssetUpload libraryId={libraryId} saved={() => { setUpload(false); setOffset(0); setRevision(value => value + 1) }} close={() => setUpload(false)} />}
  </>
}

function BookPicker({ libraryId, initial = '', selected, setSelected }: { libraryId: string; initial?: string; selected: string; setSelected: (value: string) => void }) {
  const [draft, setDraft] = useState(''), [search, setSearch] = useState(''), [books, setBooks] = useState<InventoryPage | null>(null), [error, setError] = useState('')
  useEffect(() => { let alive = true; const controller = new AbortController(); void institutionApi<InventoryPage>(`${inventoryBase(libraryId)}/books?state=active&search=${encodeURIComponent(search)}&offset=0&limit=20`, 'GET', undefined, controller.signal).then(result => { if (alive) { setBooks(result); setError('') } }).catch(reason => { if (alive && !controller.signal.aborted) setError(errorText(reason)) }); return () => { alive = false; controller.abort() } }, [libraryId, search])
  return <fieldset className="asset-book-picker"><legend>Linked library book (optional)</legend><div className="asset-book-search"><label htmlFor="asset-book-search">Find a library book<input id="asset-book-search" value={draft} maxLength={150} onChange={event => setDraft(event.target.value)} /></label><button type="button" className="ui-button ui-secondary" onClick={() => setSearch(draft)}>Find books</button></div><label htmlFor="asset-book-link">Linked book<LuminarSelect searchable id="asset-book-link" value={selected} onChange={event => setSelected(event.target.value)}><option value="">No book link</option>{initial && !books?.results.some(book => book.library_book_id === initial) && <option value={initial}>Current linked library book</option>}{books?.results.map(book => <option key={book.library_book_id} value={book.library_book_id}>{book.title} · {book.accession_number}</option>)}</LuminarSelect></label><p>Choose a book from this library. {books?.has_more ? 'Search to find other books.' : ''}</p>{error && <p role="alert">{error}</p>}</fieldset>
}

function AssetUpload({ libraryId, saved, close }: { libraryId: string; saved: () => void; close: () => void }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [book, setBook] = useState(''), [uploadId, setUploadId] = useState(() => crypto.randomUUID()), controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy) return
    const fields = new FormData(event.currentTarget), file = fields.get('file')
    if (!(file instanceof File) || !file.size) { setError('Choose a non-empty PDF, TXT or DOCX.'); return }
    if (book) fields.set('library_book_id', book); else fields.delete('library_book_id')
    const abort = new AbortController(); controller.current = abort; setBusy(true); setError('')
    try { await uploadAsset(libraryId, fields, uploadId, abort.signal); if (!abort.signal.aborted) saved() } catch (reason) { if (!abort.signal.aborted) setError(errorText(reason)) } finally { if (!abort.signal.aborted) setBusy(false) }
  }
  return <Modal title="Upload Document" onClose={close} busy={busy} className="asset-dialog"><div className="institutions library-assets"><form className="institution-form" onSubmit={event => void submit(event)}><p>Upload a document owned by this library. Accepted formats: PDF, UTF-8 TXT and DOCX. DOCX uses extracted-text preview; legacy .doc is unsupported. It becomes available after document processing finishes.</p><label htmlFor="asset-upload-file">Document file<input id="asset-upload-file" name="file" type="file" accept={ACCEPTED_TYPES} required data-autofocus onChange={() => setUploadId(crypto.randomUUID())} /></label><label htmlFor="asset-upload-title">Title<input id="asset-upload-title" name="title" maxLength={200} required /></label><label htmlFor="asset-upload-visibility">Visibility<LuminarSelect id="asset-upload-visibility" name="visibility" defaultValue="STAFF_ONLY"><option value="STAFF_ONLY">Staff only</option><option value="MEMBERS">Library members</option></LuminarSelect></label><BookPicker libraryId={libraryId} selected={book} setSelected={setBook} />{error && <p role="alert" className="institution-error">{error}</p>}{busy && <p role="status">Uploading document… Keep this dialog open until the upload is acknowledged.</p>}<button className="ui-button" disabled={busy}>{busy ? 'Uploading…' : 'Upload Document'}</button></form></div></Modal>
}

export function LibraryAssetDetailPage({ staff = false }: { staff?: boolean }) {
  const { assetId = '' } = useParams()
  return <AssetGate staff={staff}>{(libraryId, name, token) => <AssetDetail key={assetId} libraryId={libraryId} assetId={assetId} name={name} token={token} staff={staff} />}</AssetGate>
}

function AssetDetail({ libraryId, assetId, name, token, staff }: { libraryId: string; assetId: string; name: string; token: string; staff: boolean }) {
  const [params]=useSearchParams(),expectedBook=params.get('book')
  const [result, setResult] = useState<{ key: string; asset?: LibraryAsset; error?: string } | null>(null), [revision, setRevision] = useState(0), [action, setAction] = useState<'edit' | 'delete' | null>(null), [busy, setBusy] = useState(false), [notice, setNotice] = useState('')
  const navigate = useNavigate(), key = `${libraryId}:${assetId}:${token}:${revision}`
  useEffect(() => { let alive = true; const controller = new AbortController(); void fetchAsset(libraryId, assetId, controller.signal).then(asset => { if (alive && !controller.signal.aborted && useAuthStore.getState().token === token) setResult({ key, asset }) }).catch(reason => { if (alive && !controller.signal.aborted) { setResult({ key, error: errorText(reason) }); setAction(null) } }); return () => { alive = false; controller.abort() } }, [libraryId, assetId, token, key])
  const asset = result?.key === key ? result.asset : undefined, error = result?.key === key ? result.error : undefined
  useEffect(() => { const refresh = () => setRevision(value => value + 1); window.addEventListener('focus', refresh); const timer = asset && pending(asset) ? setInterval(refresh, 3000) : undefined; return () => { window.removeEventListener('focus', refresh); if (timer) clearInterval(timer) } }, [asset])

  async function run(method: 'DELETE' | 'POST', reprocess = false) { setBusy(true); setNotice(''); try { const row = await mutateAsset(libraryId, assetId, method, undefined, reprocess); if (useAuthStore.getState().token !== token) return; if (row.status === 'DELETED' || row.status === 'DELETING') navigate(assetPath(libraryId, staff)); else { setAction(null); setRevision(value => value + 1); setNotice('Document reprocessing started.') } } catch (reason) { setNotice(errorText(reason)) } finally { setBusy(false) } }
  if (error) return <StatePanel title="Document unavailable" kind="error" action={<Link className="ui-button ui-secondary" to={assetPath(libraryId, staff)}>Back to documents</Link>}>{error}</StatePanel>
  if (!asset) return <StatePanel title="Loading document…" kind="loading" />
  if (expectedBook && asset.library_book_id!==expectedBook) return <StatePanel title="Document unavailable" kind="error">This resource is no longer linked to the selected book.</StatePanel>
  if (!permitted(asset, staff) || ['DELETING', 'DELETED'].includes(asset.status)) return <StatePanel title="Document unavailable">This document is no longer accessible.</StatePanel>
  return <>
    <Link className="asset-back" to={assetPath(libraryId, staff)}>← {staff ? 'Digital Assets' : 'Library Resources'}</Link>
    <PageHeading title={asset.title} eyebrow={name} description={asset.original_filename} />
    {/* ── Metadata card ── */}
    <section className="ui-card"><AssetFacts asset={asset} staff={staff} />{asset.library_book_id && <Link className="asset-linked-book" to={libraryBookPath(libraryId, asset.library_book_id, staff)}>{asset.linked_book_title ? `Linked book: ${asset.linked_book_title}` : 'View linked book'}</Link>}{asset.duplicate_warning && <p>{asset.duplicate_warning}</p>}{pending(asset) && <p role="status">Preparing document text and Q&A. This page refreshes while processing.</p>}{asset.status === 'FAILED' && <StatePanel title="Document processing failed" action={staff && <button className="ui-button" disabled={busy} onClick={() => void run('POST', true)}>Reprocess failed document</button>}>Staff can retry processing when the source file is available. Missing files need recovery before retrying. {asset.error_code ? `Failure: ${asset.error_code.replaceAll('_', ' ').toLowerCase()}.` : ''}</StatePanel>}</section>
    {notice && <p role="status" className="asset-notice">{notice}</p>}
    {/* ── READY workspace: viewer + actions + Knowledge Tools ── */}
    {asset.status === 'READY' && <AssetWorkspace key={`${token}:${libraryId}:${assetId}:${asset.updated_at}`} libraryId={libraryId} assetId={assetId} title={asset.title} staff={staff} asset={asset} />}
    {/* ── Staff actions at bottom ── */}
    {staff && <div className="ui-actions asset-staff-actions">{!pending(asset) && <button className="ui-button ui-secondary" disabled={busy} onClick={() => setAction('edit')}>Edit metadata</button>}<button className="ui-button ui-danger" disabled={busy} onClick={() => setAction('delete')}>Delete document</button></div>}
    {action === 'edit' && <AssetEditor libraryId={libraryId} asset={asset} close={() => setAction(null)} saved={() => { setAction(null); setRevision(value => value + 1) }} />}
    {action === 'delete' && <Modal title="Delete document" busy={busy} onClose={() => setAction(null)} className="asset-dialog"><div className="institutions library-assets"><p>Delete "{asset.title}"? File access, Q&A and Knowledge Tools will be revoked. An audit record is retained.</p>{notice && <p role="alert">{notice}</p>}<div className="ui-actions"><button className="ui-button ui-secondary" disabled={busy} data-autofocus onClick={() => setAction(null)}>Cancel</button><button className="ui-button ui-danger" disabled={busy} onClick={() => void run('DELETE')}>{busy ? 'Deleting…' : 'Confirm Delete'}</button></div></div></Modal>}
  </>
}

function AssetEditor({ libraryId, asset, close, saved }: { libraryId: string; asset: LibraryAsset; close: () => void; saved: () => void }) {
  const [book, setBook] = useState(asset.library_book_id || ''), [busy, setBusy] = useState(false), [error, setError] = useState('')
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (busy) return; const fields = new FormData(event.currentTarget); setBusy(true); setError(''); try { await mutateAsset(libraryId, asset.asset_id, 'PATCH', { title: String(fields.get('title') || '').trim(), visibility: fields.get('visibility') as AssetVisibility, library_book_id: book || null }); saved() } catch (reason) { setError(errorText(reason)) } finally { setBusy(false) } }
  return <Modal title="Edit document" busy={busy} onClose={close} className="asset-dialog"><div className="institutions library-assets"><form className="institution-form" onSubmit={event => void submit(event)}><label htmlFor="asset-edit-title">Title<input id="asset-edit-title" name="title" required maxLength={200} defaultValue={asset.title} data-autofocus /></label><label htmlFor="asset-edit-visibility">Visibility<LuminarSelect id="asset-edit-visibility" name="visibility" defaultValue={asset.visibility}><option value="STAFF_ONLY">Staff only</option><option value="MEMBERS">Library members</option></LuminarSelect></label><p>Changing to Staff only blocks members from new document requests.</p><BookPicker libraryId={libraryId} initial={asset.library_book_id || ''} selected={book} setSelected={setBook} />{error && <p role="alert">{error}</p>}<button className="ui-button" disabled={busy}>{busy ? 'Saving…' : 'Save document'}</button></form></div></Modal>
}

type ViewerState = 'CLOSED' | 'LOADING' | 'OPEN' | 'ERROR'

function AssetWorkspace({ libraryId, assetId, title, asset }: { libraryId: string; assetId: string; title: string; staff?: boolean; asset: LibraryAsset }) {
  const [params]=useSearchParams(),autoOpen=params.get('open')==='1',openedAutomatically=useRef(false)
  const target = useMemo(() => ({ libraryId, assetId }), [libraryId, assetId])
  const [viewerState, setViewerState] = useState<ViewerState>('CLOSED')
  const [fileUrl, setFileUrl] = useState('')
  const [pdfPage, setPdfPage] = useState(1)
  const [textContent, setTextContent] = useState('')
  const [viewerError, setViewerError] = useState('')
  const [showKnowledge, setShowKnowledge] = useState(false)
  const location = useLocation()
  const controllerRef = useRef<AbortController | null>(null)
  const isText = asset.asset_type === 'TXT' || asset.asset_type === 'DOCX'

  useEffect(() => () => {controllerRef.current?.abort()}, [])
  useEffect(() => () => { if (fileUrl) URL.revokeObjectURL(fileUrl) }, [fileUrl])

  const openDocument=useCallback(async(pageNumber = 1) => {
    if (viewerState === 'LOADING') return
    const abort = new AbortController(); controllerRef.current = abort
    setViewerState('LOADING'); setViewerError(''); setTextContent('')
    try {
      if (isText) {
        const preview = await institutionApi<{text:string;library_id:string;asset_id:string}>(`/libraries/${libraryId}/assets/${assetId}/preview`, 'GET', undefined, abort.signal)
        if (preview.library_id !== libraryId || preview.asset_id !== assetId) throw new Error('Document identity did not match.')
        const text = preview.text
        if (abort.signal.aborted) return
        setTextContent(text)
        setViewerState('OPEN')
      } else {
        const file = await assetFile(libraryId, assetId, abort.signal, pageNumber)
        if (abort.signal.aborted) return
        if (file.type !== 'image/png') throw new Error('The PDF page preview could not be rendered.')
        const url = URL.createObjectURL(file)
        if (fileUrl) URL.revokeObjectURL(fileUrl)
        setFileUrl(url)
        setPdfPage(pageNumber)
        setViewerState('OPEN')
      }
    } catch (reason) {
      if (!abort.signal.aborted) {
        setViewerState('ERROR')
        setViewerError(errorText(reason))
      }
    }
  },[viewerState,isText,libraryId,assetId,fileUrl])

  useEffect(()=>{
    if (!autoOpen || openedAutomatically.current) return
    let cancelled=false
    queueMicrotask(()=>{if(!cancelled && !openedAutomatically.current){openedAutomatically.current=true;void openDocument()}})
    return ()=>{cancelled=true}
  },[autoOpen,openDocument])

  function closeDocument() {
    if (fileUrl) { URL.revokeObjectURL(fileUrl); setFileUrl('') }
    setTextContent('')
    setViewerState('CLOSED')
  }

  async function downloadDocument() {
    const abort = new AbortController(); controllerRef.current = abort
    try {
      const file = await assetFile(libraryId, assetId, abort.signal)
      if (abort.signal.aborted) return
      const url = URL.createObjectURL(file)
      const link = document.createElement('a'); link.href = url; link.download = asset.original_filename || `${title}.pdf`
      document.body.append(link); link.click(); link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (reason) {
      if (!abort.signal.aborted) { closeDocument();setViewerError(errorText(reason)) }
    }
  }

  function openAskLuminaR() {
    const assistant = useAssistantStore.getState()
    assistant.setDocumentContext(location.pathname + location.search, libraryId, assetId, title)
    assistant.setOpen(true)
  }

  return <section className="asset-workspace" aria-label="Library document tools">
    {/* ── Action bar ── */}
    <div className="asset-action-group">
      {/* Open / Close — stateful, never both */}
      {viewerState === 'CLOSED' || viewerState === 'ERROR' ? (
        <button className="ui-button ui-secondary" onClick={() => void openDocument()}>Open document</button>
      ) : viewerState === 'LOADING' ? (
        <button className="ui-button ui-secondary" disabled>Opening…</button>
      ) : (
        <button className="ui-button ui-secondary" onClick={closeDocument}>Close document</button>
      )}
      <button className="ui-button ui-secondary" onClick={openAskLuminaR}>Ask LuminaR</button>
      <button className="ui-button ui-secondary" aria-pressed={showKnowledge} onClick={() => setShowKnowledge(v => !v)}>Knowledge Tools</button>
      <button className="ui-button ui-secondary" onClick={() => void downloadDocument()}>Download document</button>
    </div>

    {/* ── Document viewer ── */}
    {viewerState === 'LOADING' && <div className="asset-viewer-loading" role="status"><p>Loading document…</p></div>}
    {viewerState === 'ERROR' && <div className="asset-viewer-error" role="alert">
      <p>Unable to preview this document.</p>
      {viewerError && <p className="asset-viewer-error-detail">{viewerError}</p>}
      <div className="ui-actions">
        <button className="ui-button ui-secondary" onClick={() => void openDocument()}>Retry</button>
        <button className="ui-button ui-secondary" onClick={() => void downloadDocument()}>Download document</button>
      </div>
    </div>}
    {viewerState === 'OPEN' && textContent && <div className="asset-reader">
      {asset.asset_type === 'DOCX' && <p>Extracted text preview. Word page layout, images and formatting are not rendered.</p>}<pre className="asset-text-viewer">{textContent}</pre>
    </div>}
    {viewerState === 'OPEN' && fileUrl && <div className="asset-reader">
      <div className="ui-pagination"><button className="ui-button ui-secondary" disabled={pdfPage <= 1} onClick={() => void openDocument(pdfPage - 1)}>Previous page</button><span>Page {pdfPage} of {asset.pages || 1}</span><button className="ui-button ui-secondary" disabled={pdfPage >= (asset.pages || 1)} onClick={() => void openDocument(pdfPage + 1)}>Next page</button></div>
      <img className="asset-pdf-page" alt={`Page ${pdfPage} of ${title}`} src={fileUrl} onError={() => { closeDocument(); setViewerState('ERROR'); setViewerError('The PDF page preview could not be rendered.') }} />
    </div>}
    {viewerError&&viewerState!=='ERROR'&&<p role="alert">{viewerError}</p>}
    {/* ── Ask LuminaR context chip ── */}
    <p className="asset-context-chip">
      <span className="asset-context-label">Document context</span>
      <span className="asset-context-title">{title}</span>
      <span className="asset-context-id">{assetId.slice(0, 8)}</span>
    </p>

    {/* ── Knowledge Tools (toggle) ── */}
    {showKnowledge && <div className="asset-knowledge"><KnowledgeTools documentId={assetId} title={title} libraryAsset={target} /></div>}
  </section>
}

/** Only mounted inside a library book detail; global work detail never calls this API. */
export function LibraryBookResources({ libraryId, bookId, staff = false }: { libraryId: string; bookId: string; staff?: boolean }) {
  const token = useAuthStore(s => s.token), [result, setResult] = useState<{ key: string; data?: AssetPage; error?: string } | null>(null), [revision, setRevision] = useState(0), key = `${libraryId}:${bookId}:${token}:${staff}:${revision}`
  useEffect(() => observeCatalogue(libraryId, () => setRevision(value => value + 1)), [libraryId])
  useEffect(() => { let alive = true; const controller = new AbortController(); void fetchAssets(libraryId, new URLSearchParams({ library_book_id: bookId, ...(!staff ? { status: 'READY', visibility: 'MEMBERS' } : {}), offset: '0', limit: '20' }).toString(), controller.signal).then(data => { if (alive && !controller.signal.aborted && useAuthStore.getState().token === token) setResult({ key, data }) }).catch(reason => { if (alive && !controller.signal.aborted) setResult({ key, error: errorText(reason) }) }); return () => { alive = false; controller.abort() } }, [libraryId, bookId, token, staff, key])
  const data = result?.key === key ? result.data : undefined, error = result?.key === key ? result.error : undefined
  useEffect(() => { if(data && window.location.hash === "#digital-resources") document.getElementById("digital-resources")?.scrollIntoView?.({block:"start"}) }, [data])
  if (error) return <section id="digital-resources" className="library-book-resources"><h2>Digital Resources</h2><p>Unable to load this book's resources.</p><button className="ui-button ui-secondary" onClick={() => setRevision(value => value + 1)}>Retry resources</button></section>
  if (!data || !staff && !data.results.length) return null
  const assets = data.results.filter(asset => permitted(asset, staff) && asset.library_id === libraryId && asset.library_book_id === bookId)
  const ready = assets.filter(asset => asset.status === 'READY')
  return <section id="digital-resources" className="library-book-resources" aria-label="Digital Resources"><h2>Digital Resources</h2>
    {ready.length > 0 && <p className="library-book-digital-badge">Online copy available</p>}
    {!assets.length && <p>No online copies attached to this book.</p>}
    <ul>{assets.map(asset => <li key={asset.asset_id}>
      <Link to={asset.status==='READY' ? libraryReadOnlinePath(libraryId,bookId,asset.asset_id,staff) : assetPath(libraryId, staff, asset.asset_id)}>{asset.title}</Link>
      <span>{asset.asset_type} · {assetStatusText(asset.status)}{staff ? ` · ${assetVisibilityText(asset.visibility)}` : ' · Read / Ask LuminaR'}</span>
      {asset.status === 'READY' && <Link className="ui-button ui-secondary" to={libraryKnowMorePath(libraryId,bookId,asset.asset_id,staff)}>Know More</Link>}
    </li>)}</ul>
    {staff && ready.length===1 && <Link className="ui-button ui-secondary" to={libraryReadOnlinePath(libraryId,bookId,ready[0].asset_id,staff)}>Read Online</Link>}
    {data.total > 20 && <Link to={`${assetPath(libraryId, staff)}?book=${encodeURIComponent(bookId)}`}>All online copies for this book</Link>}
  </section>
}

/** Upload soft copy for an existing physical book — used from inventory */
export function AddSoftCopyModal({ libraryId, bookId, bookTitle, close, saved }: { libraryId: string; bookId: string; bookTitle: string; close: () => void; saved: () => void }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [uploadId, setUploadId] = useState(() => crypto.randomUUID()), controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy) return
    const fields = new FormData(event.currentTarget), file = fields.get('file')
    if (!(file instanceof File) || !file.size) { setError('Choose a non-empty document.'); return }
    fields.set('library_book_id', bookId)
    if (!fields.get('title')) fields.set('title', bookTitle)
    const abort = new AbortController(); controller.current = abort; setBusy(true); setError('')
    try {
      let uploaded=await uploadAsset(libraryId,fields,uploadId,abort.signal)
      const deadline=Date.now()+120000
      while(uploaded.status!=='READY') {
        if(uploaded.status==='FAILED')throw new Error('Online copy failed to process. The existing book and physical holding are preserved; retry from Digital Assets.')
        if(Date.now()>=deadline)throw new Error('Online copy is still processing. Check its status in Digital Assets.')
        await new Promise(resolve=>setTimeout(resolve,700))
        uploaded=await fetchAsset(libraryId,uploaded.asset_id,abort.signal)
      }
      if (!abort.signal.aborted) saved()
    } catch (reason) { if (!abort.signal.aborted) setError(errorText(reason)) }
    finally { if (!abort.signal.aborted) setBusy(false) }
  }
  return <Modal title={`Add Online Copy · ${bookTitle}`} onClose={close} busy={busy} className="asset-dialog"><div className="institutions library-assets"><form className="institution-form" onSubmit={event => void submit(event)}>
    <p>Upload an online copy for this book. Accepted: PDF, UTF-8 TXT and DOCX. Its format is derived from READY online resources and existing physical stock.</p>
    <label htmlFor="softcopy-file">Document file<input id="softcopy-file" name="file" type="file" accept={ACCEPTED_TYPES} required data-autofocus onChange={() => setUploadId(crypto.randomUUID())} /></label>
    <label htmlFor="softcopy-title">Document title<input id="softcopy-title" name="title" maxLength={200} defaultValue={bookTitle} required /></label>
    <label htmlFor="softcopy-visibility">Visibility<LuminarSelect id="softcopy-visibility" name="visibility" defaultValue="MEMBERS"><option value="STAFF_ONLY">Staff only</option><option value="MEMBERS">Library members</option></LuminarSelect></label>
    {error && <p role="alert" className="institution-error">{error}</p>}
    {busy && <p role="status">Uploading document…</p>}
    <button className="ui-button" disabled={busy}>{busy ? 'Uploading…' : 'Add Online Copy'}</button>
  </form></div></Modal>
}
