export type ReservationRow = { reservation_id: string; library_id: string; library_book_id: string; title: string; accession_number: string; status: string; requested_at: string; queue_position: number | null; queue_length: number; lending_request_id?: string | null; reason?: string; borrower?: { name: string; email: string }; availability?: { requestable: number } }
export type FeeRow = { fee_id: string; library_id: string; library_book_id?: string; loan_id: string; title: string; accession_number: string; status: string; currency: string; fee_type: string; original_amount_minor: number; current_amount_minor: number; paid_amount_minor: number; balance_minor: number; policy_snapshot: FeePolicy; calculation: { kind: string; overdue_days?: number; due_at?: string; return_requested_at?: string; valid_return_requested_at?: string; physical_received_at?: string; charge_stop_at?: string }; created_at: string; borrower?: { name: string; email: string }; ledger?: LedgerEntry[] }
export type LedgerEntry = { entry_id: string; entry_type: string; amount_minor: number; reason: string; created_at: string; actor_user_id: number; method?: string; receipt_id?: string; reference?: string }
export type FeePolicy = { policy_id: string; version: number; overdue_enabled: boolean; rate_minor_per_day: number; currency: string; grace_days: number; charge_stop_policy: string; effective_from: string }
export type QueuePage = { results: ReservationRow[]; total: number }
export type FeePage = { results: FeeRow[]; total: number; estimates?: { library_book_id?: string; loan_id: string; title: string; currency: string; amount_minor: number; kind: string }[] }
export const money = (minor: number, currency = 'INR') => new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(minor / 100)
export function minorAmount(text: string): number {
  if (!/^\d+(\.\d{1,2})?$/.test(text.trim())) throw new Error('Enter an amount with at most two decimal places.')
  const [whole, fraction = ''] = text.trim().split('.')
  const value = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'))
  if (value > 1000000000000n) throw new Error('Amount exceeds the supported range.')
  return Number(value)
}
