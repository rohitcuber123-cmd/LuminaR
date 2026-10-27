import { Link } from 'react-router-dom'
import { useProductContext } from '../hooks/useProductContext'
import { withPatronContext } from '../lib/productContext'
import type { ReactNode } from 'react'
import { ActionOverflow } from './ActionOverflow'

export function BookDiscoveryMenu({ workId, libraryId, children }: { workId: string; libraryId?: string; children?: ReactNode }) {
  const context = useProductContext()
  if (!workId && !children) return null
  return <ActionOverflow label={`More discovery actions for ${workId || 'this book'}`}>
    {children}
    {workId && <Link to={context.personalPath(withPatronContext(`/book/${encodeURIComponent(workId)}?related=1#more-like-this`, libraryId || context.libraryId))}>More Like This</Link>}
  </ActionOverflow>
}
