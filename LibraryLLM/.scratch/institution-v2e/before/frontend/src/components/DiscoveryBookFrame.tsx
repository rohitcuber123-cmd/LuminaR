import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { BookCoverArt } from './BookCoverArt'

/** The original recommendation card geometry, shared by global and library discovery. */
export function DiscoveryBookFrame({ title, author, seed, path, availability, children, coverUrl }: {
  title: string; author: string; seed: number; path: string; availability: ReactNode; children?: ReactNode; coverUrl?: string | null
}) {
  return <><Link to={path} className="block flex-1 flex flex-col">
    <div className="mb-4 transform transition-transform duration-300 group-hover:-translate-y-2 group-hover:scale-[1.02]">
      <BookCoverArt title={title} author={author} seed={seed} url={coverUrl}
        className="shadow-[0_12px_32px_rgba(0,0,0,0.12)] group-hover:shadow-[0_18px_40px_rgba(0,0,0,0.18)]" />
    </div><div className="space-y-2 flex-1">
      <h3 className="line-clamp-2 min-h-[2.5rem] text-sm font-medium leading-snug text-ink transition-colors group-hover:text-brand">{title}</h3>
      <p className="text-xs text-ink-soft line-clamp-2 min-h-[2rem]">{author}</p>
      <p className="text-xs text-ink-soft">{availability}</p>
    </div></Link>{children}</>
}
