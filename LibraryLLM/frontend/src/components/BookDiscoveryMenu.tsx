import { Link } from 'react-router-dom'

export function BookDiscoveryMenu({ workId }: { workId: string }) {
  if (!workId) return null
  return <details className="relative mt-2 text-xs"><summary className="inline-block cursor-pointer text-ink-soft underline-offset-2 hover:text-moss" aria-label={`More discovery actions for ${workId}`}>More actions</summary>
    <Link className="mt-2 block w-fit rounded-sm border border-line bg-paper px-3 py-2 text-moss" to={`/book/${encodeURIComponent(workId)}?related=1#more-like-this`}>More Like This</Link>
  </details>
}
