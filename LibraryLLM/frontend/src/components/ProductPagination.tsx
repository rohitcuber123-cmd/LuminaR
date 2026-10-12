import { ChevronLeft, ChevronRight } from 'lucide-react'
export function ProductPagination({ page, totalPages, hasMore, busy = false, onPrevious, onNext, label = 'Catalogue pagination', nextLabel='Next page', previousLabel='Previous page' }: {
  page: number; totalPages?: number; hasMore: boolean; busy?: boolean; onPrevious: () => void; onNext: () => void; label?: string; nextLabel?:string; previousLabel?:string
}) {
  return <nav className="product-pagination ui-pagination" aria-label={label}>
    <button type="button" disabled={busy || page <= 1} onClick={onPrevious} aria-label={previousLabel}><ChevronLeft size={16} aria-hidden="true" /><span className="sr-only">Previous</span></button>
    <span aria-live="polite">Page {page}{totalPages ? ` of ${totalPages.toLocaleString()}` : ''}</span>
    <button type="button" disabled={busy || !hasMore} onClick={onNext} aria-label={nextLabel}><ChevronRight size={16} aria-hidden="true" /><span className="sr-only">{nextLabel}</span></button>
  </nav>
}
