import { institutionApi } from './institutions'
import { request } from './api'

export type Availability = { total: number; requestable: number; pending_holds: number; active_loans: number; unavailable_stock: number; circulation_status: string; allocation_mode: string; shelf_location: string | null }
export type LendingRow = { user_id?: number; lending_request_id: string; loan_id: string | null; library_id: string; library_book_id: string; holding_id: string; copy_id: string | null; title: string; accession_number: string; status: string; allocation_mode: string; proposed_due_at?: string; requested_at?: string; borrowed_at?: string; due_at?: string; returned_at?: string; return_requested_at?: string; pending_return_request_id?: string | null; rejection_reason?: string | null; shelf_location: string | null; borrower?: { name: string; email: string; membership_status: string }; availability?: Availability }
export type LendingPage = { results: LendingRow[]; total: number; pending_counts?: { BORROW: number; RETURN: number } }
export const lendingBase = (id: string) => `/libraries/${encodeURIComponent(id)}`
export const commandKey = () => crypto.randomUUID()
export const withdrawLibraryBook = (path: string, key: string) => request('/api' + path, { method: 'DELETE', cache: 'no-store', headers: { 'Idempotency-Key': key } })
export const lendingCommand = <T,>(path: string, fields: object = {}, key: string = commandKey(), method = 'POST') => institutionApi<T>(path, method, { ...fields, idempotency_key: key })
