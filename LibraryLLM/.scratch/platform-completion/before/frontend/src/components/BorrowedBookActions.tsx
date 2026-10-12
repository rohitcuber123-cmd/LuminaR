import { Link } from 'react-router-dom'

export interface BorrowedBookAccess {
  work_id: string
  borrowed?: boolean
  readable?: boolean
  rag_available?: boolean
  can_read?: boolean
  can_know_more?: boolean
}

export function BorrowedBookActions({ issue }: { issue: BorrowedBookAccess }) {
  if (issue.borrowed !== true) return null

  const canRead = issue.can_read ?? issue.readable === true
  const canKnowMore = issue.can_know_more ?? issue.rag_available === true

  if (!canRead && !canKnowMore) {
    return <span className="text-xs text-ink-soft">Digital text unavailable</span>
  }

  return (
    <div className="flex flex-wrap gap-2">
      {canRead && (
        <Link
          className="font-display rounded-sm bg-brand px-3 py-2 text-[0.68rem] tracking-wide text-paper hover:bg-brand-dark"
          to={`/book/${encodeURIComponent(issue.work_id)}/read`}
        >
          READ NOW
        </Link>
      )}
      {canKnowMore && (
        <Link
          className="font-display rounded-sm border border-brand px-3 py-2 text-[0.68rem] tracking-wide text-brand hover:bg-brand/5"
          to={`/llm?book=${encodeURIComponent(issue.work_id)}`}
        >
          KNOW MORE
        </Link>
      )}
    </div>
  )
}
