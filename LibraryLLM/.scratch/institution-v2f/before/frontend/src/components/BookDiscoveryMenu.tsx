import { Link } from 'react-router-dom'
import { useProductContext } from '../hooks/useProductContext'
import { withPatronContext } from '../lib/productContext'

export function BookDiscoveryMenu({ workId, libraryId }: { workId: string; libraryId?: string }) {
  const context = useProductContext()
  if (!workId) return null
  return <details className="relative mt-2 text-xs"><summary className="inline-block cursor-pointer text-ink-soft underline-offset-2 hover:text-moss" aria-label={`More discovery actions for ${workId}`}>More actions</summary>
    <Link className="mt-2 block w-fit rounded-sm border border-line bg-paper px-3 py-2 text-moss" to={context.personalPath(withPatronContext(`/book/${encodeURIComponent(workId)}?related=1#more-like-this`, libraryId || context.libraryId))}>More Like This</Link>
  </details>
}
