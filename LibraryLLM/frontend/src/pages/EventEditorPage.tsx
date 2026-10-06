import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useAuthStore } from '../store/useAuthStore'
import { categories, eventApi, author, EVENTS_CHANGED, type EventInput, type EventBook, type EventCategory, type LibraryEvent } from '../lib/events'
import { searchBooks } from '../lib/api'
import { BookCover } from '../components/BookCover'
import { Modal } from '../components/StaffUI'
import { EventPublishSummary } from '../components/events/EventPublishSummary'
import { EVENT_PRESETS, EVENT_PUBLISH_REQUIREMENTS, baseErrors, publishErrors, requiresPublishedValidation, type EventFieldError } from '../lib/eventPresets'
import { EventSkeleton, EventIcon } from '../components/events/EventUI'
import './Staff.css'
import './Events.css'

function empty(): EventInput { return { title: '', category: 'NEW_ARRIVALS', summary: '', description: '', start_at: null, end_at: null, location: null, featured: EVENT_PRESETS.NEW_ARRIVALS.defaultFeatured, related_work_ids: [] } }
function localTime(value: string | null) { if (!value) return ''; const date = new Date(value); return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16) }
function BookPicker({ selected, change, disabled, label, helper, invalid }: { selected: EventBook[]; change: (books: EventBook[]) => void; disabled: boolean; label: string; helper: string; invalid: boolean }) {
  const [query, setQuery] = useState(''), [rows, setRows] = useState<EventBook[]>([]), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  const serial = useRef(0), token = useAuthStore(s => s.token)
  async function search() { const request = ++serial.current; setBusy(true); setError(''); try { const response = await searchBooks(query.trim(), 12, 'LIB001', false, false); if (request === serial.current && useAuthStore.getState().token === token) setRows(response.results.filter(r => r.work_id).map(r => ({ work_id: r.work_id!, title: r.title, authors: r.authors }))) } catch (e) { if (request === serial.current) setError(e instanceof Error ? e.message : 'Catalogue search failed.') } finally { if (request === serial.current) setBusy(false) } }
  return <section className="event-picker" id="event-related_work_ids" tabIndex={-1} aria-invalid={invalid || undefined}><h2>{label} <span>{selected.length}/12</span></h2><p className="event-muted">{helper}</p><div className="event-picker-search"><label>Search catalogue<input aria-label="Search catalogue" value={query} maxLength={120} onChange={e => setQuery(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); if (query.trim()) void search() } }} /></label><button type="button" className="event-button" disabled={disabled || busy || !query.trim()} onClick={() => void search()}>{busy ? 'Searching…' : 'Search catalogue'}</button></div>{error && <p role="alert">{error}</p>}
    <ul className="event-picker-selected" aria-label="Selected related books">{selected.map((book, i) => <li key={book.work_id}><div className="event-picker-cover"><BookCover title={book.title || book.work_id} author={author(book)} paletteIndex={i} variant="split" /></div><div><strong>{book.title || book.work_id}</strong><p>{author(book)}</p><small>{book.work_id}</small></div><button type="button" className="event-button" aria-label={'Remove ' + (book.title || book.work_id)} disabled={disabled} onClick={() => change(selected.filter(b => b.work_id !== book.work_id))}>Remove</button></li>)}</ul>
    {selected.length === 12 && <p role="status">Select no more than 12 related books.</p>}<div className="event-picker-results">{rows.map(book => { const exists = selected.some(b => b.work_id === book.work_id); return <div key={book.work_id}><div><strong>{book.title || book.work_id}</strong><p>{author(book)}</p><small>{book.work_id}</small></div><button type="button" className="event-button" disabled={disabled || exists || selected.length >= 12} onClick={() => change([...selected, book])}>{exists ? 'Selected' : 'Select book'}</button></div> })}</div>
  </section>
}
export function EventEditorPage() {
  const { eventId } = useParams(), token = useAuthStore(s => s.token), navigate = useNavigate()
  const key = `${token}:${eventId || 'new'}`
  const [owner, setOwner] = useState(''), [form, setForm] = useState<EventInput>(empty)
  const [books, setBooks] = useState<EventBook[]>([]), [loaded, setLoaded] = useState<LibraryEvent | null>(null)
  const [savedId, setSavedId] = useState<string | null>(null), [error, setError] = useState('')
  const [errors, setErrors] = useState<EventFieldError[]>([]), [busy, setBusy] = useState(false)
  const [publish, setPublish] = useState(false), [nextType, setNextType] = useState<EventCategory | null>(null), lock = useRef(false)
  useEffect(() => {
    const controller = new AbortController()
    void (eventId ? eventApi.detail(eventId, true, controller.signal) : Promise.resolve(null)).then(event => {
      if (controller.signal.aborted || useAuthStore.getState().token !== token) return
      setForm(event ? { title: event.title, category: event.category, summary: event.summary, description: event.description, start_at: localTime(event.start_at), end_at: localTime(event.end_at), location: event.location, featured: event.featured, related_work_ids: event.related_work_ids } : empty())
      setBooks(event ? [...event.related_books, ...(event.missing_related_work_ids || []).map(work_id => ({ work_id, title: 'Unavailable book: ' + work_id }))] : [])
      setLoaded(event); setSavedId(event?.event_id || null); setOwner(key); setError(''); setErrors([]); setPublish(false); setNextType(null)
    }).catch(e => { if (!controller.signal.aborted) { setOwner(key); setError(e instanceof Error ? e.message : 'Event unavailable.') } })
    return () => controller.abort()
  }, [eventId, token, key])
  const preset = EVENT_PRESETS[form.category], requirements = EVENT_PUBLISH_REQUIREMENTS[form.category]
  const immutable = loaded?.status === 'ARCHIVED', disabled = busy || Boolean(immutable)
  const current: EventInput = { ...form, related_work_ids: books.map(b => b.work_id) }
  function changeType(category: EventCategory) {
    if (category === form.category) return
    if (loaded?.status === 'PUBLISHED') setNextType(category)
    else { setForm(value => ({ ...value, category })); setErrors([]); setError('') }
  }
  function focusField(field: keyof EventInput) {
    const control = document.getElementById('event-' + field), details = control?.closest('details')
    if (details) details.open = true
    control?.focus()
  }
  async function save(andPublish: boolean) {
    if (lock.current) return
    const problems = [...baseErrors(current), ...(andPublish || loaded?.status === 'PUBLISHED' && requiresPublishedValidation(loaded, current) ? publishErrors(current) : [])]
    setErrors(problems); setError('')
    if (problems.length) return
    lock.current = true; setBusy(true)
    try {
      const payload: EventInput = { ...current, start_at: form.start_at ? new Date(form.start_at).toISOString() : null, end_at: form.end_at ? new Date(form.end_at).toISOString() : null, location: form.location?.trim() || null }
      const event = savedId ? await eventApi.edit(savedId, payload) : await eventApi.create(payload)
      if (useAuthStore.getState().token !== token) return
      setSavedId(event.event_id); setLoaded(event)
      if (andPublish) setPublish(true); else navigate('/staff/events')
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to save event.') }
    finally { lock.current = false; setBusy(false) }
  }
  async function publishSaved() {
    if (!savedId || lock.current) return
    lock.current = true; setBusy(true); setError('')
    try { await eventApi.action(savedId, 'publish'); if (useAuthStore.getState().token !== token) return; window.dispatchEvent(new Event(EVENTS_CHANGED)); navigate('/staff/events') }
    catch (e) { setError(e instanceof Error ? e.message : 'Unable to publish event.') }
    finally { lock.current = false; setBusy(false) }
  }
  function invalid(field: keyof EventInput) { return errors.some(e => e.field === field) || undefined }
  function required(field: string) { return field in requirements.fields ? ' · required to publish' : '' }
  const schedule = <section className="event-editor-section event-schedule"><h2>Schedule &amp; Location</h2>
    <div className="event-date-fields">
      <label htmlFor="event-start_at">{preset.startLabel}{required('start_at')}<input id="event-start_at" type="datetime-local" aria-label={preset.startLabel} aria-invalid={invalid('start_at')} value={form.start_at || ''} disabled={disabled} onChange={e => setForm({ ...form, start_at: e.target.value || null })} /></label>
      <label htmlFor="event-end_at">{preset.endLabel}{required('end_at')}<input id="event-end_at" type="datetime-local" aria-label={preset.endLabel} aria-invalid={invalid('end_at')} value={form.end_at || ''} disabled={disabled} onChange={e => setForm({ ...form, end_at: e.target.value || null })} /></label>
    </div><p className="event-muted">Times use your local timezone. Dates can stay blank in drafts.</p>
    <label htmlFor="event-location">Location{required('location')}<input id="event-location" aria-label="Event location" aria-invalid={invalid('location')} maxLength={200} value={form.location || ''} disabled={disabled} onChange={e => setForm({ ...form, location: e.target.value })} /><small>{preset.locationHelper}</small></label>
  </section>
  const picker = <BookPicker selected={books} change={setBooks} disabled={disabled} label={preset.booksLabel} helper={preset.booksHelper} invalid={Boolean(invalid('related_work_ids'))} />
  return <div className="events-shell event-editor-shell">
    <Link className="event-link" to="/staff/events">← Manage Events</Link>
    <header className="events-heading"><div><span className="event-eyebrow">LIBRARY STAFF</span><h1>{eventId ? 'Edit Event' : 'Create Event'}</h1><p>{loaded?.status === 'PUBLISHED' ? 'Corrections preserve the first publication date and do not notify users again.' : 'Save an incomplete draft, then publish when it is ready.'}</p></div></header>
    {owner !== key ? <EventSkeleton /> : <form noValidate className="event-editor event-preset-editor" onSubmit={e => { e.preventDefault(); void save(false) }}>
      <section className="event-type-selector">
        <label htmlFor="event-category">What kind of event are you publishing?<select id="event-category" aria-label="Event Type" value={form.category} disabled={disabled} onChange={e => changeType(e.target.value as EventCategory)}>{Object.entries(categories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <div className="event-preset-heading"><EventIcon category={form.category} /><div><strong>{categories[form.category]}</strong><p className="event-muted">{preset.helper}</p></div></div>
      </section>
      {(errors.length > 0 || error) && <div className="event-error-summary" role="alert" aria-label="Event validation errors"><strong>{errors.length ? 'Check these fields before continuing.' : 'Unable to complete this action.'}</strong>{errors.length > 0 && <ul>{errors.map(e => <li key={e.field + e.message}><button type="button" className="event-link" onClick={() => focusField(e.field)}>{e.message}</button></li>)}</ul>}{error && <p>{error}</p>}</div>}
      <section className="event-editor-section event-editor-fields"><h2>Basic Information</h2>
        <label htmlFor="event-title">Title *<input id="event-title" aria-label="Event title" aria-invalid={invalid('title')} required minLength={3} maxLength={140} value={form.title} disabled={disabled} onChange={e => setForm({ ...form, title: e.target.value })} /></label>
        <label htmlFor="event-summary">{preset.summaryLabel}<textarea id="event-summary" aria-label="Event summary" rows={2} maxLength={300} value={form.summary} disabled={disabled} onChange={e => setForm({ ...form, summary: e.target.value })} /><small>{form.summary.length}/300</small></label>
        <label htmlFor="event-description">{preset.descriptionLabel}{required('description')}<textarea id="event-description" aria-label="Event description" aria-invalid={invalid('description')} rows={4} maxLength={5000} value={form.description} disabled={disabled} onChange={e => setForm({ ...form, description: e.target.value })} /><small>{preset.descriptionHelper} · {form.description.length}/5000</small></label>
      </section>
      {preset.order.map(section => section === 'schedule' ? <div key="schedule">{preset.scheduleCollapsed ? <details className="event-optional"><summary>Optional Schedule &amp; Location</summary>{schedule}</details> : schedule}</div> : <div key="books">{preset.booksMode === 'hidden' ? books.length > 0 && <p className="event-muted">{books.length} previously linked books are retained. Choose another event type to manage them.</p> : preset.booksMode === 'collapsed' ? <details className="event-optional"><summary>Optional Related Books ({books.length})</summary>{picker}</details> : picker}</div>)}
      <section className="event-editor-section event-editor-footer">
        <label className="event-checkbox"><input type="checkbox" checked={form.featured} disabled={disabled} onChange={e => setForm({ ...form, featured: e.target.checked })} />Featured event</label>
        {Boolean(loaded?.missing_related_work_ids?.length) && <p role="status" className="event-error">Some linked books have left the catalogue. Remove unavailable links before saving.</p>}
        <div className="events-actions"><button className="event-button primary" disabled={disabled}>{busy ? 'Saving…' : loaded && loaded.status !== 'DRAFT' ? 'Save changes' : 'Save Draft'}</button>{(!loaded || loaded.status === 'DRAFT') && <button type="button" className="event-button" disabled={disabled} onClick={() => void save(true)}>Publish Now</button>}<Link className="event-button" to="/staff/events">Cancel editing</Link></div>
        {loaded && <details className="event-optional event-audit"><summary>Event history · {loaded.status}</summary><p>Created by {loaded.created_by?.email || 'Unavailable staff account'}</p><p>Last updated by {loaded.updated_by?.email || 'Unavailable staff account'}</p>{loaded.published_at && <p>Published {new Date(loaded.published_at).toLocaleString()}</p>}</details>}
      </section>
    </form>}
    {publish && <Modal title="Publish this event?" busy={busy} onClose={() => setPublish(false)}><p>It will become visible to library users and create a new-event badge.</p><EventPublishSummary event={current} />{error && <p role="alert">{error}</p>}<div className="events-actions"><button className="event-button" disabled={busy} onClick={() => setPublish(false)}>Keep as draft</button><button className="event-button primary" disabled={busy} onClick={() => void publishSaved()}>{busy ? 'Publishing…' : 'Publish event'}</button></div></Modal>}
    {nextType && <Modal title="Change published event type?" busy={busy} onClose={() => setNextType(null)}><p>Change event type from {categories[form.category]} to {categories[nextType]}?</p><p>Entered values will be kept. Saving this correction will not publish it again or notify readers.</p><div className="events-actions"><button className="event-button" onClick={() => setNextType(null)}>Keep current type</button><button className="event-button primary" onClick={() => { setForm(value => ({ ...value, category: nextType })); setNextType(null); setErrors([]); setError('') }}>Change event type</button></div></Modal>}
  </div>
}
