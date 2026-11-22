import {useProductContext} from '../hooks/useProductContext'
import { useState, type ReactNode } from 'react'
import { Bookmark, BookmarkCheck } from 'lucide-react'
import { Button } from './Button'
import { useLocation, useNavigate } from 'react-router-dom'
import { useLibraryStore } from '../store/useLibraryStore'
import { useAuthStore } from '../store/useAuthStore'
import { validWorkId } from '../lib/assistant'
import {productLibraryId} from '../lib/productContext'
import { personalBookKey } from '../lib/bookPresentation'
import type { DisplayBook } from '../lib/libraryCatalogue'
import { BookSelectButton } from './BookSelectButton'
import { BookDiscoveryMenu } from './BookDiscoveryMenu'
import { showToast } from './Toast'

export function BookPersonalActions({ book, detailed = false, overflow }: { book: DisplayBook; detailed?: boolean; overflow?: ReactNode }) {
  const navigate = useNavigate(), location = useLocation(), authenticated = useAuthStore(s => s.isAuthenticated)
  const key = personalBookKey(book), inList = useLibraryStore(s => !!key && s.readingList.includes(key))
  const [busy, setBusy] = useState(false)
  const product=useProductContext()
  const localSelection=(product.libraryId||product.staffLibraryId)===book.library_id&&book.source==='LIBRARY'&&book.owned_by_current_library&&book.library_book_id
  const selectionId=localSelection&&!/^OL\d+W$/.test(book.global_work_id||'')?book.library_book_id!:book.global_work_id&&validWorkId(book.global_work_id)?book.global_work_id:localSelection?book.library_book_id!:''
  const linked = !!book.global_work_id && validWorkId(book.global_work_id)
  // Personal saved references retain their existing selection action. Core
  // resolves that reference against current holdings before scoped tool use.
  const selectionAllowed=localSelection||linked&&(!productLibraryId(location.pathname,location.search)||location.pathname==='/reading-list')
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
    {selectionAllowed && <BookSelectButton compact={!detailed} book={{work_id:selectionId,title:book.title,authors:book.authors}} />}
    {(linked || overflow) && <BookDiscoveryMenu workId={linked ? book.global_work_id! : ''} libraryId={book.library_id || undefined}>{overflow}</BookDiscoveryMenu>}
    {!linked && !localSelection && detailed && <p className="book-capability-note">AI selection and related discovery require a linked LuminaR global work. You can save this library book to your Reading List.</p>}
  </div>
}
