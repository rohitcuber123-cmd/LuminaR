import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { RelatedBookCard } from './RelatedBookCard'
import { useAssistantStore } from '@/store/useAssistantStore'
import type { useMoreLikeThis } from '@/hooks/useMoreLikeThis'

export function MoreLikeThisSection({ workId, related }: { workId: string; related: ReturnType<typeof useMoreLikeThis> }) {
  const ref = useRef<HTMLElement>(null)
  const currentStatus = related.state?.status
  useEffect(() => {
    if (currentStatus) { ref.current?.focus({ preventScroll: true }); ref.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' }) }
  }, [currentStatus, workId])
  if (!related.state) return null
  const { status, data, error } = related.state
  return <section id="more-like-this" ref={ref} tabIndex={-1} aria-label="More Like This" className="mt-12 scroll-mt-24 border-t border-line pt-8 outline-none">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-display text-2xl text-ink">More Like This</h2><p className="mt-2 text-sm text-ink-soft">Related through shared authors, subjects and verified graph relationships.</p></div><button onClick={related.hide} className="assistant-button">Hide related books</button></div>
    {status === 'loading' && <p role="status" className="py-8 text-sm text-ink-soft">Finding related books…</p>}
    {status === 'error' && <div className="mt-5 text-sm"><p role="alert">{error}</p><button className="assistant-button mt-3" onClick={() => void related.load()}>Retry related books</button>{error?.startsWith('Sign in') && <Link className="ml-3 underline" to="/login">Sign in</Link>}</div>}
    {status === 'ready' && data && <>
      {!data.recommendations.length ? <div className="py-8 text-sm"><p>No graph relationships are available for this title yet.</p><button className="assistant-button mt-3" onClick={() => {
        const assistant = useAssistantStore.getState(); assistant.setOpen(true)
        void assistant.send('Recommend Similar', { work_id: workId }, { action: 'RECOMMEND_SIMILAR', action_work_ids: [workId] })
      }}>Try Recommend Similar</button></div> : <div className="mt-6 grid min-w-0 grid-cols-1 gap-4 lg:grid-cols-2">{data.recommendations.map(book => <RelatedBookCard key={book.work_id} book={book} seed={data.seed} />)}</div>}
      <div className="mt-6 flex flex-wrap gap-4 text-xs"><button className="text-moss underline" onClick={() => void related.load()}>Refresh related books</button><Link className="text-moss underline" to={`/experimental/kg?seed=${encodeURIComponent(workId)}`}>Explore full graph →</Link></div>
    </>}
  </section>
}
