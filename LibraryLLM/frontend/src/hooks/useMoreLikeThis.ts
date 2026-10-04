import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '@/lib/api'
import { relatedBooks, type RelatedBooksResponse } from '@/lib/knowledgeGraph'

export function useMoreLikeThis(workId: string | undefined, auto = false, authenticated = true) {
  const [state, setState] = useState<{ workId: string; status: 'loading' | 'ready' | 'error'; data?: RelatedBooksResponse; error?: string } | null>(null)
  const controller = useRef<AbortController | null>(null)
  const load = useCallback(async () => {
    if (!workId) return
    controller.current?.abort()
    const current = new AbortController(); controller.current = current
    setState({ workId, status: 'loading' })
    if (!authenticated) { setState({ workId, status: 'error', error: 'Sign in to find related books.' }); return }
    try {
      const data = await relatedBooks(workId, current.signal)
      if (!current.signal.aborted) setState({ workId, status: 'ready', data })
    } catch (cause) {
      if (!current.signal.aborted) setState({ workId, status: 'error', error: cause instanceof ApiError && cause.status === 409
        ? 'Related-book data for this title is being refreshed.' : cause instanceof ApiError && cause.status === 404
          ? 'Related books are not available for this title yet.' : cause instanceof Error ? cause.message : 'Unable to load related books. Please try again.' })
    }
  }, [workId, authenticated])
  useEffect(() => {
    let active = true
    if (auto && workId) void Promise.resolve().then(() => { if (active) return load() })
    return () => { active = false; controller.current?.abort() }
  }, [workId, auto, load])
  return { state: state?.workId === workId ? state : null, load,
    hide: () => { controller.current?.abort(); setState(null) } }
}
