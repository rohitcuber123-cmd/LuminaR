import { Check, Plus } from 'lucide-react'
import { useAssistantStore } from '../store/useAssistantStore'
import { showToast } from './Toast'
import type { AssistantBook } from '../lib/assistantTypes'
import { MAX_SELECTION_MESSAGE } from '../lib/assistant'
export function BookSelectButton({ book }: { book: Pick<AssistantBook, 'work_id' | 'title' | 'authors'> }) {
  const selected = useAssistantStore(state => state.selected.some(item => item.work_id === book.work_id))
  return <button type="button" aria-label={`${selected ? 'Unselect' : 'Select'} ${book.title || book.work_id}`} aria-pressed={selected}
    disabled={!book.work_id} className={`assistant-button mt-2 inline-flex items-center gap-1.5 ${selected ? 'border-brand text-brand' : ''}`}
    onClick={event => {
      event.preventDefault(); event.stopPropagation()
      const store = useAssistantStore.getState()
      if (selected) store.unselect(book.work_id)
      else if (!store.select(book)) showToast(MAX_SELECTION_MESSAGE, 'warning')
    }}>
    {selected ? <Check size={13} aria-hidden="true" /> : <Plus size={13} aria-hidden="true" />}{selected ? 'Selected' : 'Select for AI'}
  </button>
}
