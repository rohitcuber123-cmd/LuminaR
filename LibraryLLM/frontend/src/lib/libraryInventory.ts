import { request } from './api'
import { institutionApi } from './institutions'
import type { Availability } from './libraryLending'
import { catalogueChanged } from './catalogueInvalidation'

export type Holding = { holding_id: string; library_id: string; library_book_id: string; total_copies: number; available_copies: number; shelf_location: string | null; call_number: string | null; quantity_semantics: string }
export type LibraryBook = { library_book_id: string; library_id: string; accession_number: string; title: string; subjects: string[]; authors: string[]; global_work_id: string | null; isbn_10: string | null; isbn_13: string | null; publisher: string | null; publication_year: number | null; edition: string | null; language: string | null; description: string | null; shelf_location: string | null; local_call_number: string | null; local_tags: string[]; acquisition_note: string | null; status: 'ACTIVE' | 'WITHDRAWN'; needs_review: boolean; holding: Holding | null; book_format?: 'PHYSICAL_ONLY'|'DIGITAL_ONLY'|'PHYSICAL_AND_DIGITAL'|'UNAVAILABLE'; has_physical?:boolean; has_online?:boolean; online_asset_id?:string|null }
export type InventoryPage = { results: (LibraryBook & { availability?: Availability })[]; total: number; has_more: boolean; role: string; lending_state?: string }
export type ImportRow = { row_number: number; title?: string; subjects?: string[]; classification: string; reason?: string | null; outcome?: string; accession_number?: string }
export type InventoryPreview = { import_id: string; library_id: string; filename: string; status: string; rows_total: number; rows_valid: number; rows_invalid: number; global_matches: number; new_library_records: number; existing_holdings: number; possible_duplicates: number; rows: ImportRow[] }
export type InventoryResult = { import_id: string; library_id: string; status: string; created_records: number; increased_holdings: number; skipped_existing: number; invalid_rows: number; rows: ImportRow[] }
export const inventoryBase = (libraryId: string) => `/libraries/${encodeURIComponent(libraryId)}/inventory`

export function uploadInventory(libraryId: string, file: File) {
  const data = new FormData(); data.append('file', file)
  return request<InventoryPreview>('/api' + inventoryBase(libraryId) + '/imports/preview', { method: 'POST', body: data, cache: 'no-store' })
}

export async function commitInventory(libraryId: string, importId: string, existingPolicy: string) {
  const result = await institutionApi<InventoryResult>(`${inventoryBase(libraryId)}/imports/${encodeURIComponent(importId)}/apply`, 'POST', { existing_policy: existingPolicy })
  catalogueChanged(libraryId)
  return result
}
