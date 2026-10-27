import { ApiError, getToken, request } from './api'
import { institutionApi, revalidateDeniedAccess } from './institutions'
import type { AssistantRAGResult } from './assistantTypes'

export type AssetVisibility = 'STAFF_ONLY' | 'MEMBERS'
export type AssetStatus = 'UPLOADING' | 'PROCESSING' | 'READY' | 'FAILED' | 'DELETING' | 'DELETED'
export type LibraryAssetTarget = { libraryId: string; assetId: string }
export type LibraryAsset = {
  asset_id: string; library_id: string; uploaded_by_user_id: number; asset_type: 'PDF' | 'TXT' | 'DOCX'; title: string
  original_filename: string; media_type: string; byte_size: number; checksum: string; status: AssetStatus
  visibility: AssetVisibility; library_book_id: string | null; global_work_id: string | null
  extraction_status: string; rag_status: string; created_at: string; updated_at: string
  deleted_at: string | null; deleted_by_user_id: number | null; pages?: number; chunks?: number
  error_code?: string | null; duplicate_warning?: string | null
  uploader_name?: string | null; linked_book_title?: string | null
  processing_job?: { job_id: string; state: string; attempt: number; error_code: string | null } | null
}
export type AssetPage = { results: LibraryAsset[]; total: number; offset: number; limit: number }
export type AssetRAGResult = AssistantRAGResult & { library_id: string; asset_id: string }
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
export function assetBase(libraryId: string, assetId?: string) {
  if (!uuid.test(libraryId) || assetId !== undefined && !uuid.test(assetId)) throw new Error('A canonical library and document identity is required.')
  return `/libraries/${libraryId}/assets${assetId ? `/${assetId}` : ''}`
}
export const assetPath = (libraryId: string, staff = false, assetId?: string) => `${staff ? '/staff' : ''}/libraries/${libraryId}/${staff ? 'assets' : 'resources'}${assetId ? `/${assetId}` : ''}`
export function checkAsset(asset: LibraryAsset, libraryId: string, assetId?: string) {
  if (!asset || asset.library_id !== libraryId || !uuid.test(asset.asset_id) || assetId && asset.asset_id !== assetId) throw new Error('Document response did not match the current library context.')
  return asset
}
export async function fetchAssets(libraryId: string, query: string, signal?: AbortSignal) {
  const page = await institutionApi<AssetPage>(`${assetBase(libraryId)}?${query}`, 'GET', undefined, signal)
  if (!Array.isArray(page.results) || !Number.isInteger(page.total) || page.total < 0) throw new Error('Document list was incomplete. Refresh the page.')
  page.results.forEach(asset => checkAsset(asset, libraryId))
  return page
}
export async function fetchAsset(libraryId: string, assetId: string, signal?: AbortSignal) {
  return checkAsset(await institutionApi<LibraryAsset>(assetBase(libraryId, assetId), 'GET', undefined, signal), libraryId, assetId)
}
export async function uploadAsset(libraryId: string, data: FormData, uploadId: string, signal?: AbortSignal) {
  const token = getToken()
  const result = await request<LibraryAsset>('/api' + assetBase(libraryId), { method: 'POST', body: data, signal, cache: 'no-store', headers: { 'X-Luminar-Upload': uploadId } })
  if (token !== getToken()) throw new DOMException('The signed-in account changed.', 'AbortError')
  return checkAsset(result, libraryId)
}
export async function mutateAsset(libraryId: string, assetId: string, method: 'PATCH' | 'DELETE' | 'POST', body?: unknown, reprocess = false) {
  return checkAsset(await institutionApi<LibraryAsset>(assetBase(libraryId, assetId) + (reprocess ? '/reprocess' : ''), method, body), libraryId, assetId)
}
export async function assetFile(libraryId: string, assetId: string, signal?: AbortSignal, pageNumber?: number) {
  const token = getToken()
  if (!token) throw new Error('Sign in to read this library document.')
  const response = await fetch('/api' + assetBase(libraryId, assetId) + (pageNumber ? '/preview/pages/' + pageNumber : '/file'), { cache: 'no-store', signal, headers: { Authorization: `Bearer ${token}` } })
  if (token !== getToken() || signal?.aborted) throw new DOMException('Document context changed.', 'AbortError')
  if (!response.ok) {
    if ([403,404].includes(response.status)) await revalidateDeniedAccess(libraryId,token)
    throw new ApiError(response.status === 404 || response.status === 403 ? 'This library document is no longer accessible.' : 'Unable to open this document. Refresh and try again.', response.status)
  }
  const file = await response.blob()
  if (token !== getToken() || signal?.aborted) throw new DOMException('Document context changed.', 'AbortError')
  return file
}
export async function askAsset(target: LibraryAssetTarget, query: string, depth: string, signal?: AbortSignal) {
  const token = getToken()
  const result = await request<AssetRAGResult>('/rag-api' + assetBase(target.libraryId, target.assetId) + '/rag', { method: 'POST', body: JSON.stringify({ query, depth }), signal, cache: 'no-store' })
  if (token !== getToken() || signal?.aborted) throw new DOMException('Document context changed.', 'AbortError')
  if (result.library_id !== target.libraryId || result.asset_id !== target.assetId) throw new Error('The answer did not match the selected library document.')
  return result
}
export const assetStatusText = (status: AssetStatus) => ({ UPLOADING: 'Uploading', PROCESSING: 'Processing', READY: 'Ready', FAILED: 'Processing failed', DELETING: 'Deleting', DELETED: 'Deleted' })[status]
export const assetVisibilityText = (value: AssetVisibility) => value === 'MEMBERS' ? 'Library members' : 'Staff only'
