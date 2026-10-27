import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { BookCoverArt } from './BookCoverArt'

/** The original recommendation card geometry, shared by global and library discovery. */
export function DiscoveryBookFrame({ title, author, seed, path, availability, children, coverUrl, status }: {
  title: string; author: string; seed: number; path: string; availability: ReactNode; children?: ReactNode; coverUrl?: string | null; status?: ReactNode
}) {
  return <><div className="book-card-cover"><Link to={path} aria-label={`View ${title}`} className="block">
      <BookCoverArt title={title} author={author} seed={seed} url={coverUrl}
        className="shadow-[0_8px_24px_rgba(0,0,0,0.10)] motion-safe:transition-shadow motion-safe:duration-150 motion-safe:group-hover:shadow-[0_12px_32px_rgba(0,0,0,0.14)]" />
    </Link>{status}</div><div className="book-card-description space-y-1">
      <Link to={path}><h3 className="line-clamp-2 min-h-[2.5rem] text-sm font-medium leading-snug text-ink transition-colors duration-100 group-hover:text-brand" title={title}>{title}</h3></Link>
      <p className="text-xs text-ink-soft line-clamp-1 min-h-[1.15rem] truncate" title={author}>{author || 'Author not recorded'}</p>
      <p className="text-xs text-ink-soft min-h-[1.15rem] truncate">{availability}</p>
    </div>{children}</>
}
