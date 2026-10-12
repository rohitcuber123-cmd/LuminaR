import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useLibraryStore } from '../store/useLibraryStore'
import { useAuthStore } from '../store/useAuthStore'
import { validWorkId } from '../lib/assistant'
import { personalBookKey } from '../lib/bookPresentation'
import type { DisplayBook } from '../lib/libraryCatalogue'
import { BookSelectButton } from './BookSelectButton'
import { BookDiscoveryMenu } from './BookDiscoveryMenu'
import { showToast } from './Toast'

export function BookPersonalActions({ book, detailed = false }: { book: DisplayBook; detailed?: boolean }) {
  const navigate = useNavigate(), location = useLocation(), authenticated = useAuthStore(s => s.isAuthenticated)
  const key = personalBookKey(book), inList = useLibraryStore(s => !!key && s.readingList.includes(key))
  const [busy, setBusy] = useState(false)
  const linked = !!book.global_work_id && validWorkId(book.global_work_id)
  async function save() {
    if (!authenticated) { navigate(`/login?next=${encodeURIComponent(location.pathname + location.search)}`); return }
    if (!key || busy) return
    const token = useAuthStore.getState().token
    setBusy(true)
    try {
      await useLibraryStore.getState().toggleList(key)
      if (token !== useAuthStore.getState().token) return
      showToast(inList ? `Removed "${book.title}" from reading list` : `Added "${book.title}" to reading list`, inList ? 'info' : 'success', {scope: token || undefined})
    } catch (error) {
      if (token !== useAuthStore.getState().token) return
      showToast(error instanceof Error ? error.message : 'Unable to update reading list.', 'warning', {scope: token || undefined})
    }
    finally { setBusy(false) }
  }
  return <div className="book-personal-actions">
    {linked && <BookSelectButton book={{work_id:book.global_work_id!,title:book.title,authors:book.authors}} />}
    {key && <button type="button" className={`assistant-button book-save-button ${inList ? 'is-saved' : ''}`} aria-pressed={inList} disabled={busy} onClick={() => void save()}>
      {busy ? 'Saving…' : inList ? 'In Reading List ✓' : 'Add to Reading List'}</button>}
    {linked && <BookDiscoveryMenu workId={book.global_work_id!} libraryId={book.library_id || undefined} />}
    {!linked && detailed && <p className="book-capability-note">AI selection and related discovery require a linked LuminaR global work. You can save this library book to your Reading List.</p>}
  </div>
}
