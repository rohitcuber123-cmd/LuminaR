import { request } from './api.ts'
import type { AssistantPageContext, AssistantRequest, AssistantResponse, AssistantBook, RecommendationMode, AssistantRequestAction } from './assistantTypes.ts'

export const MAX_SELECTION_MESSAGE = 'You can select up to 4 books. Remove one first.'
export const validWorkId = (id: string) => /^[A-Za-z0-9_-]{1,128}$/.test(id)
export const uniqueIds = (ids: string[], limit: number) => [...new Set(ids.filter(validWorkId))].slice(0, limit)
export const displayText = (value: unknown): string => Array.isArray(value) ? value.map(displayText).filter(Boolean).join(' · ') : value == null ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value)
export const recommendLabel = (count: number) => count === 0 ? 'Recommend' : count === 1 ? 'Recommend Similar' : 'Recommend From These'
export const recommendAction = (count: number): AssistantRequestAction => count === 0 ? 'RECOMMEND' : count === 1 ? 'RECOMMEND_SIMILAR' : 'RECOMMEND_FROM_SELECTION'
export const recommendationHeading: Record<RecommendationMode, string> = {
  PERSONALIZED_EXISTING_FORMULA: 'Recommended for you', SINGLE_SELECTED_BOOK: 'Similar recommendations',
  MULTI_SELECTED_BOOKS: 'Based on your selected books', EXPLICIT_BOOK_SEED: 'Based on the book you mentioned',
}
export function sanitizePageContext(context: AssistantPageContext): AssistantPageContext {
  return {
    ...(context.work_id && validWorkId(context.work_id) ? { work_id: context.work_id } : {}),
    ...(context.work_ids?.length ? { work_ids: uniqueIds(context.work_ids, 4) } : {}),
    ...(context.document_id && context.document_id.length <= 128 ? { document_id: context.document_id } : {}),
  }
}
export function recentIds(books: AssistantBook[], previous: string[]) {
  return uniqueIds([...books.map(book => book.work_id), ...previous], 20)
}
export function assistantChat(payload: AssistantRequest, signal?: AbortSignal) {
  // Explicit fields prevent accidental identity or UI metadata from entering strict backend schema.
  const body: AssistantRequest = {
    message: payload.message.trim(), conversation_id: payload.conversation_id ?? null,
    selected_work_ids: uniqueIds(payload.selected_work_ids, 4), recent_work_ids: uniqueIds(payload.recent_work_ids, 20),
    ...(payload.action_work_ids?.length ? { action_work_ids: uniqueIds(payload.action_work_ids, 4) } : {}),
    page_context: sanitizePageContext(payload.page_context), pending_action_id: payload.pending_action_id ?? null, action: payload.action ?? null,
    ...(payload.result_offset ? { result_offset: Math.max(0, Math.min(200, payload.result_offset)) } : {}),
  }
  return request<AssistantResponse>('/rag-api/assistant/chat', { method: 'POST', body: JSON.stringify(body), signal })
}

