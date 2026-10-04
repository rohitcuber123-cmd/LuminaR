export type AssistantIntent = 'SEARCH_BOOKS' | 'RECOMMEND_BOOKS' | 'RECOMMEND_FROM_BOOK' | 'RECOMMEND_FROM_SELECTION' | 'COMPARE_BOOKS' | 'CHECK_AVAILABILITY' | 'BOOK_DETAILS' | 'BORROW_BOOK' | 'RETURN_BOOK' | 'RESERVE_BOOK' | 'USER_LOANS' | 'USER_RESERVATIONS' | 'USER_HISTORY' | 'USER_FEES' | 'GENERAL_LIBRARY_HELP' | 'BOOK_CONTENT_QUESTION' | 'DOCUMENT_QUESTION' | 'CLARIFICATION' | 'UNKNOWN'
export type RecommendationMode = 'PERSONALIZED_EXISTING_FORMULA' | 'SINGLE_SELECTED_BOOK' | 'MULTI_SELECTED_BOOKS' | 'EXPLICIT_BOOK_SEED'
export type AssistantActionType = 'VIEW_BOOK' | 'SELECT_BOOK' | 'UNSELECT_BOOK' | 'COMPARE' | 'RECOMMEND_SIMILAR' | 'RECOMMEND_FROM_SELECTION' | 'CHECK_AVAILABILITY' | 'BORROW' | 'RESERVE' | 'RETURN' | 'CONFIRM_ACTION' | 'CANCEL_ACTION'
export interface AssistantPageContext { work_id?: string | null; work_ids?: string[]; document_id?: string | null }
export interface AssistantRequest {
  message: string
  conversation_id?: string | null
  selected_work_ids: string[]
  recent_work_ids: string[]
  page_context: AssistantPageContext
  pending_action_id?: string | null
  action?: 'CONFIRM_ACTION' | 'CANCEL_ACTION' | null
}
export interface AssistantBook {
  work_id: string
  title?: string | null
  authors?: string | string[] | null
  subjects?: string | string[] | null
  description?: string | null
  average_rating?: number | null
  available_copies?: number | null
  total_copies?: number | null
  shelf_location?: string | null
}
export interface AssistantAvailability { work_id: string; available: boolean | null; available_copies: number | null; total_copies: number | null }
export interface AssistantComparison { books: AssistantBook[]; requested_fields: string[]; missing_fields: string[] }
export interface AssistantAction { type: AssistantActionType; work_id?: string | null; action_id?: string | null }
export interface AssistantClarification { reason: string; choices: AssistantBook[] }
export interface AssistantPendingAction { action_id: string; type: AssistantIntent; work_id: string; requires_confirmation: boolean; expires_at: string; enabled: boolean }
// Core account/RAG envelopes are intentionally extensible; values stay structured.
export interface AssistantAccountRecord {
  work_id?: string; title?: string; book_title?: string; due_date?: string; issue_date?: string; return_date?: string
  status?: string; amount?: number; [field: string]: unknown
}
export interface AssistantAccountResult {
  count?: number; total_unpaid?: number; issues?: AssistantAccountRecord[]; reservations?: AssistantAccountRecord[]; fines?: AssistantAccountRecord[]
  message?: string; [field: string]: unknown
}
export interface AssistantRAGResult {
  answer?: string; verdict?: string; depth?: string; question?: string
  sources?: Array<{ filename?: string; page?: number; chunk_id?: string; chapter?: string; title?: string; author?: string; rerank_score?: number }>
  timing_ms?: { total?: number; generation?: number; retrieval?: number }
  [field: string]: unknown
}
export interface AssistantResponse {
  conversation_id: string; intent: AssistantIntent; message: string; books: AssistantBook[]
  comparison: AssistantComparison | null; recommendation_mode: RecommendationMode | null; seed_work_ids: string[]
  availability: AssistantAvailability[]; actions: AssistantAction[]; clarification: AssistantClarification | null
  pending_action: AssistantPendingAction | null; account: AssistantAccountResult | null; rag: AssistantRAGResult | null
  errors: Array<{ code: string; service: string; message: string }>
}
export type AssistantChatMessage =
  | { id: number; kind: 'USER_TEXT' | 'SYSTEM_NOTICE' | 'ERROR'; text: string }
  | { id: number; kind: 'ASSISTANT_RESPONSE'; response: AssistantResponse; latencyMs: number }
