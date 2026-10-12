import { useAssistantStore } from '../store/useAssistantStore'

export function AssistantLibraryRequestButton({ libraryId, bookId, loanId, disabled = false }: { libraryId: string; bookId: string; loanId?: string; disabled?: boolean }) {
  const busy = useAssistantStore(s => s.busy)
  return <button className="secondary" disabled={busy || disabled} onClick={() => {
    const assistant = useAssistantStore.getState(); assistant.setOpen(true)
    void assistant.send(loanId ? 'Request return for this library loan' : 'Request this library book', {}, {
      action: loanId ? 'REQUEST_RETURN' : 'REQUEST_BOOK', lending_context: { library_id: libraryId, library_book_id: bookId, ...(loanId ? { loan_id: loanId } : {}) },
    })
  }}>{loanId ? 'Ask Assistant to Request Return' : 'Ask Assistant to Request Book'}</button>
}
