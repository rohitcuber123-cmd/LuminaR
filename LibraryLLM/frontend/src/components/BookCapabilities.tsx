import { useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { issueBook, type BackendBook } from '@/lib/api'
import { useLibraryStore } from '@/store/useLibraryStore'
import { useAuthStore } from '@/store/useAuthStore'
import { showToast } from '@/components/Toast'
import { useBookActionState } from '@/hooks/useBookActionState'
import { createReadNowOperation, readNowState } from '@/lib/readNow'

export function BookCapabilities({ book, showUnavailable = false }: { book: BackendBook; showUnavailable?: boolean }) {
  const issues = useLibraryStore(state => state.issues)
  const loading = useLibraryStore(state => state.userDataLoading)
  const loaded = useLibraryStore(state => state.userDataLoaded)
  const fetchUserData = useLibraryStore(state => state.fetchUserData)
  const isAuthenticated = useAuthStore(state => state.isAuthenticated)
  const role = useAuthStore(state => state.user?.role)
  const navigate = useNavigate()
  const { action } = useBookActionState(book)
  const [opening, setOpening] = useState(false)
  const readNow = useRef(createReadNowOperation()).current
  const issue = issues.find(candidate =>
    candidate.work_id === book.work_id && candidate.borrowed === true
  )
  const borrowed = isAuthenticated && Boolean(issue)
  const readable = issue?.readable ?? (book.readable === true)
  const ragAvailable = issue?.rag_available ?? (book.rag_available === true)
  const readerState = readNowState({
    authenticated: isAuthenticated,
    role,
    readable,
    borrowed,
    accessReady: loaded && !loading,
    borrowAction: action,
  })

  if (readerState === 'LOADING') {
    return showUnavailable
      ? <p className="mt-4 text-[0.7rem] text-ink-soft" role="status">Loading access…</p>
      : null
  }
  if (readerState === 'HIDDEN' && !(borrowed && ragAvailable)) {
    if (borrowed && showUnavailable && !readable && !ragAvailable) {
      return <p className="mt-4 text-[0.7rem] text-ink-soft">Digital text unavailable</p>
    }
    return null
  }

  const handleReadNow = async () => {
    if (readerState === 'LOGIN') {
      navigate('/login')
      return
    }
    if (readerState !== 'AUTO_BORROW' || opening) return
    setOpening(true)
    try {
      await readNow({
        workId: book.work_id,
        borrowed: false,
        borrow: issueBook,
        refresh: fetchUserData,
        navigate,
      })
    } catch (error: unknown) {
      showToast(error instanceof Error ? error.message : 'Unable to borrow this book.', 'warning')
    } finally {
      setOpening(false)
    }
  }

  if (!readable && !ragAvailable) {
    return showUnavailable
      ? <p className="mt-4 text-[0.7rem] text-ink-soft">Digital text unavailable</p>
      : null
  }
  return (
    <div className="mt-4 flex flex-wrap items-center gap-3 text-[0.7rem] text-brand">
      {readerState === 'DIRECT' && (
        <Link className="border border-brand/30 bg-brand/5 px-3 py-2 font-display hover:bg-brand/10"
          to={`/book/${encodeURIComponent(book.work_id)}/read`}>
          READ NOW
        </Link>
      )}
      {(readerState === 'AUTO_BORROW' || readerState === 'LOGIN') && (
        <button
          className="border border-brand/30 bg-brand/5 px-3 py-2 font-display hover:bg-brand/10 disabled:cursor-wait disabled:opacity-60"
          disabled={opening}
          onClick={(event) => {
            event.preventDefault()
            event.stopPropagation()
            void handleReadNow()
          }}
          title={readerState === 'AUTO_BORROW' ? 'Reading this book will borrow it to your account.' : 'Sign in to borrow and read this book.'}
        >
          {opening ? 'OPENING…' : 'READ NOW'}
        </button>
      )}
      {borrowed && ragAvailable && (
        <Link className="border border-brand/30 px-3 py-2 font-display hover:bg-brand/10"
          to={`/llm?book=${encodeURIComponent(book.work_id)}`}>
          KNOW MORE
        </Link>
      )}
    </div>
  )
}
