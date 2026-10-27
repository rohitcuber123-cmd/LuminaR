import { Link, useLocation } from 'react-router-dom'
import type { BackendBook } from '../lib/api'
import { useLibraryStore } from '../store/useLibraryStore'
import { useAuthStore } from '../store/useAuthStore'
import { useProductContext } from '../hooks/useProductContext'
/** Existing digital entitlements remain account scoped. Physical lending uses tenant commands. */
export function BookCapabilities({book,showUnavailable=false,presentation='full'}: {book:BackendBook;showUnavailable?:boolean;presentation?:'full'|'primary'|'overflow'}) {
  const issues=useLibraryStore(s=>s.issues),loading=useLibraryStore(s=>s.userDataLoading),loaded=useLibraryStore(s=>s.userDataLoaded)
  const authenticated=useAuthStore(s=>s.isAuthenticated),context=useProductContext(),location=useLocation()
  const issue=authenticated ? issues.find(i=>i.work_id===book.work_id && i.borrowed===true) : undefined
  const readable=issue?.readable ?? book.readable===true,ragAvailable=issue?.rag_available ?? book.rag_available===true
  if(authenticated && (!loaded || loading))return showUnavailable ? <p role="status" className="mt-4 text-xs text-ink-soft">Loading access…</p> : null
  if(!issue && !authenticated && readable)return presentation==='overflow' ? null : <Link className="assistant-button mt-4 inline-block" to={'/login?next='+encodeURIComponent(location.pathname+location.search)}>Sign in to view reading access</Link>
  if(!issue || (!readable && !ragAvailable))return showUnavailable && issue ? <p className="mt-4 text-xs text-ink-soft">Digital text unavailable</p> : null
  return <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-brand">
    {readable && presentation!=='overflow' && <Link className="assistant-button" to={context.personalPath('/book/'+encodeURIComponent(book.work_id)+'/read')}>READ NOW</Link>}
    {ragAvailable && presentation!=='primary' && <Link className="assistant-button" to={context.personalPath('/llm?book='+encodeURIComponent(book.work_id))}>KNOW MORE</Link>}
  </div>
}
