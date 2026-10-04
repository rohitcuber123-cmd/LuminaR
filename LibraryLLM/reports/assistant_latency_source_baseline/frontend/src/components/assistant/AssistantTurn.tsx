import { Link } from 'react-router-dom'
import { BookCover } from '../BookCover'
import { BookSelectButton } from '../BookSelectButton'
import { displayText, recommendationHeading } from '../../lib/assistant'
import type { AssistantAction, AssistantAvailability, AssistantBook, AssistantComparison, AssistantResponse } from '../../lib/assistantTypes'

const label = (key: string) => key.replaceAll('_', ' ').replace(/^./, first => first.toUpperCase())
const ACTION_LABELS: Record<AssistantAction['type'], string> = {
  VIEW_BOOK: 'View book', SELECT_BOOK: 'Select', UNSELECT_BOOK: 'Unselect', COMPARE: 'Compare with AI',
  RECOMMEND_SIMILAR: 'Recommend Similar', RECOMMEND_FROM_SELECTION: 'Recommend From These', CHECK_AVAILABILITY: 'Check Availability',
  BORROW: 'Borrow', RESERVE: 'Reserve', RETURN: 'Return', CONFIRM_ACTION: 'Confirm', CANCEL_ACTION: 'Cancel',
}
export function AvailabilityBadge({ availability, book }: { availability?: AssistantAvailability; book?: AssistantBook }) {
  const copies = availability ? availability.available_copies : book?.available_copies
  const available = availability ? availability.available : copies != null ? copies > 0 : null
  return <span className={`text-xs ${available === true ? 'text-moss' : 'text-ink-soft'}`}>
    {available == null ? 'Availability unknown' : available ? `Available${copies != null ? ` · ${copies} ${copies === 1 ? 'copy' : 'copies'}` : ''}` : 'Unavailable'}
  </span>
}
function LongValue({ field, value }: { field: string; value: unknown }) {
  const text = displayText(value)
  if (!text) return <span className="text-ink-soft">Not recorded</span>
  if (field === 'description' || field === 'subjects') return <details><summary className="cursor-pointer line-clamp-2" title={text}>{text}</summary><p className="mt-2 whitespace-pre-wrap">{text}</p></details>
  return <span>{text}</span>
}
export function ComparisonView({ comparison, availability }: { comparison: AssistantComparison; availability: AssistantAvailability[] }) {
  // Discover supplied metadata; no fixed Pages/Year/Language/Difficulty columns.
  const missing = comparison.missing_fields
  const fields = [...new Set(comparison.books.flatMap(book => Object.entries(book).filter(([key, value]) => key !== 'work_id' && key !== 'title' && value != null && value !== '').map(([key]) => key)))]
  const value = (book: AssistantBook, field: string) => <LongValue field={field} value={(book as unknown as Record<string, unknown>)[field]} />
  return <section aria-label="Book comparison" className="assistant-comparison">
    <h3 className="font-display text-sm">Book comparison</h3>
    <div className="mt-3 hidden overflow-x-auto sm:block">
      <table className="w-full table-fixed border-collapse text-xs">
        <caption className="sr-only">Verified catalogue metadata</caption>
        <thead><tr><th scope="col" className="w-24">Field</th>{comparison.books.map(book => <th scope="col" key={book.work_id}>{book.title || book.work_id}</th>)}</tr></thead>
        <tbody>{fields.map(field => <tr key={field}><th scope="row">{label(field)}</th>{comparison.books.map(book => <td key={book.work_id}>{value(book, field)}</td>)}</tr>)}
          {!!availability.length && <tr><th scope="row">Availability</th>{comparison.books.map(book => <td key={book.work_id}><AvailabilityBadge availability={availability.find(item => item.work_id === book.work_id)} book={book} /></td>)}</tr>}
        </tbody>
      </table>
    </div>
    <div className="mt-3 space-y-3 sm:hidden">{comparison.books.map(book => <article key={book.work_id} className="border border-line p-3">
      <h4 className="font-display text-sm">{book.title || book.work_id}</h4><dl className="mt-2 space-y-2">{fields.map(field => <div key={field}><dt className="text-xs font-medium">{label(field)}</dt><dd className="text-xs text-ink-soft">{value(book, field)}</dd></div>)}</dl>
      <AvailabilityBadge availability={availability.find(item => item.work_id === book.work_id)} book={book} />
    </article>)}</div>
    {!!missing.length && <p className="mt-3 text-xs text-ink-soft">Not recorded: {missing.map(label).join(', ')}. That information isn't recorded for these books.</p>}
  </section>
}
export function AssistantTurn({ response, busy, pendingActive, now, onAction, onChoice }: {
  response: AssistantResponse; busy: boolean; pendingActive: boolean; now: number
  onAction: (action: AssistantAction, book?: AssistantBook) => void
  onChoice: (book: AssistantBook) => void
}) {
  const pending = response.pending_action
  const confirmationLabel = pending ? ({ BORROW_BOOK: 'borrowing', RESERVE_BOOK: 'reservation', RETURN_BOOK: 'return' } as Partial<Record<AssistantResponse['intent'], string>>)[pending.type] || 'action' : 'action'
  const pendingExpired = pending ? Date.parse(pending.expires_at) <= now : false
  const bookTitle = (id: string) => response.books.find(book => book.work_id === id)?.title || id
  const renderCard = (book: AssistantBook) => {
    const actions = response.actions.filter(action => action.work_id === book.work_id && !['CONFIRM_ACTION', 'CANCEL_ACTION'].includes(action.type))
    const hash = [...book.work_id].reduce((sum, char) => sum + char.charCodeAt(0), 0)
    return <article key={book.work_id} className="border border-line bg-paper p-3" aria-label={book.title || book.work_id}>
      <div className="flex gap-3">
        <div className="w-12 shrink-0" aria-hidden="true"><BookCover title={book.title || book.work_id} author={displayText(book.authors)} paletteIndex={hash} variant="stripe" /></div>
        <div className="min-w-0 flex-1"><h4 className="font-display break-words text-sm">{book.title || book.work_id}</h4>
          {book.authors && <p className="mt-1 text-xs text-ink-soft">{displayText(book.authors)}</p>}
          {book.subjects && <p className="mt-1 line-clamp-2 text-xs text-ink-soft">{displayText(book.subjects)}</p>}
          {book.average_rating != null && Number.isFinite(book.average_rating) && book.average_rating > 0 && <p className="mt-1 text-xs">★ {book.average_rating.toFixed(1)}</p>}
          <AvailabilityBadge availability={response.availability.find(item => item.work_id === book.work_id)} book={book} />
          {book.shelf_location && <p className="mt-1 text-xs text-ink-soft">Shelf: {book.shelf_location}</p>}
        </div>
      </div>
      {book.description && <details className="mt-2 text-xs"><summary className="cursor-pointer">Read description</summary><p className="mt-2 whitespace-pre-wrap">{book.description}</p></details>}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {actions.some(action => ['SELECT_BOOK', 'UNSELECT_BOOK'].includes(action.type)) && <BookSelectButton book={book} />}
        {actions.filter(action => ['VIEW_BOOK', 'RECOMMEND_SIMILAR'].includes(action.type)).map(action => action.type === 'VIEW_BOOK'
          ? <Link key={action.type} className="assistant-button" to={`/book/${encodeURIComponent(book.work_id)}`}>View book</Link>
          : <button key={action.type} className="assistant-button" disabled={busy} onClick={() => onAction(action, book)}>{ACTION_LABELS[action.type]}</button>)}
        {actions.some(action => !['SELECT_BOOK', 'UNSELECT_BOOK', 'VIEW_BOOK', 'RECOMMEND_SIMILAR'].includes(action.type)) && <details className="text-xs"><summary className="assistant-button cursor-pointer">More actions</summary><div className="mt-2 flex flex-wrap gap-2">{actions.filter(action => !['SELECT_BOOK', 'UNSELECT_BOOK', 'VIEW_BOOK', 'RECOMMEND_SIMILAR'].includes(action.type)).map(action => <button key={action.type} className="assistant-button" disabled={busy} onClick={() => onAction(action, book)}>{ACTION_LABELS[action.type]}</button>)}</div></details>}
      </div>
    </article>
  }
  const account = response.account
  const accountGroups = account ? (['issues', 'reservations', 'fines'] as const).filter(key => Array.isArray(account[key])) : []
  return <div className="space-y-4 break-words">
    {!!response.message && <p className="whitespace-pre-wrap text-sm leading-relaxed">{response.message}</p>}
    {response.recommendation_mode && <div><h3 className="font-display text-sm">{recommendationHeading[response.recommendation_mode]}</h3>
      {!!response.seed_work_ids.length && <p className="mt-1 text-xs text-ink-soft">{response.seed_work_ids.length} {response.seed_work_ids.length === 1 ? 'book' : 'books'} used as context</p>}
      {!response.books.length && !response.errors.some(error => error.service === 'recommendation') && <p className="mt-2 text-xs text-ink-soft">{response.recommendation_mode === 'PERSONALIZED_EXISTING_FORMULA' ? 'No personalized recommendations are available yet.' : 'No similar recommendations are available right now.'}</p>}
    </div>}
    {response.intent === 'SEARCH_BOOKS' && !response.books.length && !response.clarification && !response.errors.length && <p className="text-xs text-ink-soft">No matching catalogue books were found.</p>}
    {response.comparison && <ComparisonView comparison={response.comparison} availability={response.availability} />}
    {!!response.books.length && !response.comparison && <section aria-label="Book results" className="space-y-3">{response.books.map(renderCard)}</section>}
    {response.comparison && <div className="flex flex-wrap gap-2">{response.comparison.books.map(book => <BookSelectButton key={book.work_id} book={book} />)}</div>}
    {response.availability.filter(item => !response.books.some(book => book.work_id === item.work_id)).map(item => <div key={item.work_id} className="text-xs">{bookTitle(item.work_id)}: <AvailabilityBadge availability={item} /></div>)}
    {response.clarification && <section aria-label="Clarification" className="border-l-2 border-brand bg-panel p-3">
      <h3 className="font-display text-sm">Let's clarify</h3><p className="mt-2 text-xs">{response.clarification.reason}</p>
      <div className="mt-3 space-y-2">{response.clarification.choices.map(book => <button key={book.work_id} className="assistant-button block w-full text-left" disabled={busy} onClick={() => onChoice(book)} aria-label={`Continue with ${book.title || book.work_id}, ${displayText(book.authors)}, ${book.work_id}`}>
        <span className="block font-medium">{book.title || book.work_id}</span><span className="block text-ink-soft">{displayText(book.authors)} · {book.work_id}</span>
      </button>)}</div>
    </section>}
    {account && <section aria-label="Your account" className="border border-line p-3">
      <h3 className="font-display text-sm">Your account</h3>
      {account.total_unpaid != null && <p className="mt-2 text-sm">Unpaid fees: <strong>{displayText(account.total_unpaid)}</strong></p>}
      {accountGroups.map(key => <div key={key} className="mt-3"><h4 className="text-xs font-medium">{key === 'issues' ? response.intent === 'USER_HISTORY' ? 'Loan history' : 'Current loans' : label(key)}</h4>
        {!account[key]?.length && <p className="mt-1 text-xs text-ink-soft">No {key === 'issues' ? 'loans' : key} recorded.</p>}
        {account[key]?.map((record, index) => <dl key={index} className="mt-2 border-t border-line pt-2 text-xs">{Object.entries(record).filter(([field, value]) => !['user_id', '_id'].includes(field) && value != null).map(([field, value]) => <div key={field} className="flex flex-wrap gap-x-2"><dt className="font-medium">{label(field)}:</dt><dd><LongValue field={field} value={value} /></dd></div>)}</dl>)}
      </div>)}
      {!accountGroups.length && <dl className="mt-2 text-xs">{Object.entries(account).filter(([field]) => !['user_id', '_id', 'total_unpaid'].includes(field)).map(([field, value]) => <div key={field}><dt className="font-medium">{label(field)}</dt><dd><LongValue field={field} value={value} /></dd></div>)}</dl>}
    </section>}
    {response.rag && <section aria-label="Source answer" className="border border-line p-3">
      <h3 className="font-display text-sm">From your source</h3>
      {response.rag.verdict && <p className="mt-1 text-xs text-ink-soft">{label(response.rag.verdict.toLowerCase())}</p>}
      {response.rag.answer && response.rag.answer !== response.message && <p className="mt-2 whitespace-pre-wrap text-sm">{response.rag.answer}</p>}
      {!!response.rag.sources?.length && <details className="mt-3 text-xs"><summary className="cursor-pointer">Sources ({response.rag.sources.length})</summary><ul className="mt-2 space-y-2">{response.rag.sources.map((source, index) => <li key={index}>{source.title || source.filename || 'Source'}{source.page != null ? ` · Page ${source.page}` : ''}{source.chapter ? ` · ${source.chapter}` : ''}</li>)}</ul></details>}
    </section>}
    {pending && <section aria-label="Confirm library action" className="border border-brand/30 bg-panel p-3">
      <h3 className="font-display text-sm">{label(pending.type.replace('_BOOK', '').toLowerCase())} {bookTitle(pending.work_id)}?</h3>
      {!pending.enabled && <p className="mt-2 text-xs">Library actions are currently disabled.</p>}
      <p className="mt-2 text-xs text-ink-soft">{!pendingActive ? 'This confirmation is no longer active.' : pendingExpired ? 'This confirmation expired. Ask again to create a new one.' : `Confirm by ${new Date(pending.expires_at).toLocaleTimeString()}.`}</p>
      <div className="mt-3 flex gap-2"><button className="assistant-button" disabled={busy || !pendingActive || pendingExpired} onClick={() => onAction({ type: 'CONFIRM_ACTION', action_id: pending.action_id })}>Confirm {confirmationLabel}</button>
        <button className="assistant-button" disabled={busy || !pendingActive || pendingExpired} onClick={() => onAction({ type: 'CANCEL_ACTION', action_id: pending.action_id })}>Cancel</button></div>
    </section>}
    {response.actions.filter(action => !action.work_id && !['CONFIRM_ACTION', 'CANCEL_ACTION'].includes(action.type)).map((action, index) => <button key={index} disabled={busy} className="assistant-button" onClick={() => onAction(action)}>{ACTION_LABELS[action.type]}</button>)}
    {!!response.errors.length && <div role="status" className="space-y-2 border-l-2 border-brand/40 pl-3 text-xs text-ink-soft">{response.errors.map((error, index) => <p key={index}>{error.code === 'MUTATIONS_DISABLED' ? 'Library actions are currently disabled. No action was performed.' : error.message}</p>)}</div>}
  </div>
}
