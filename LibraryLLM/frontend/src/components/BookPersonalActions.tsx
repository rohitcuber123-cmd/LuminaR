import { useState, type ReactNode } from 'react'
import { Bookmark, BookmarkCheck } from 'lucide-react'
import { Button } from './Button'
import { useLocation, useNavigate } from 'react-router-dom'
import { useLibraryStore } from '../store/useLibraryStore'
import { useAuthStore } from '../store/useAuthStore'
import { validWorkId } from '../lib/assistant'
import { personalBookKey } from '../lib/bookPresentation'
import type { DisplayBook } from '../lib/libraryCatalogue'
import { BookSelectButton } from './BookSelectButton'
import { BookDiscoveryMenu } from './BookDiscoveryMenu'
import { showToast } from './Toast'

export function BookPersonalActions({ book, detailed = false, overflow }: { book: DisplayBook; detailed?: boolean; overflow?: ReactNode }) {
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
    {key && <Button variant="secondary" busy={busy} className={`assistant-button book-save-button ${inList ? 'is-saved' : ''}`} aria-label={busy ? 'Saving…' : inList ? 'In Reading List ✓' : 'Add to Reading List'} aria-pressed={inList} onClick={() => void save()}>
      {inList ? <BookmarkCheck size={15} aria-hidden="true" /> : <Bookmark size={15} aria-hidden="true" />}{busy ? 'Saving…' : inList ? 'Saved' : detailed ? 'Add to Reading List' : 'Save'}</Button>}
    {linked && <BookSelectButton compact={!detailed} book={{work_id:book.global_work_id!,title:book.title,authors:book.authors}} />}
    {(linked || overflow) && <BookDiscoveryMenu workId={linked ? book.global_work_id! : ''} libraryId={book.library_id || undefined}>{overflow}</BookDiscoveryMenu>}
    {!linked && detailed && <p className="book-capability-note">AI selection and related discovery require a linked LuminaR global work. You can save this library book to your Reading List.</p>}
  </div>
}
