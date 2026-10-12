import { institutionApi } from './institutions'

export type AnalyticsRange = '7d' | '30d' | '90d' | 'all'
export type AnalyticsCount = number | null
export type AnalyticsMinorAmount = string | null
export type AnalyticsTrend = {
  date: string
  acquisitions: number
  borrow_requests: AnalyticsCount
  loans_issued: AnalyticsCount
  returns_confirmed: AnalyticsCount
  renewals: AnalyticsCount
  reservations: AnalyticsCount
  events_published: number
  fees_assessed_minor: AnalyticsMinorAmount
  payments_minor: AnalyticsMinorAmount
}
export type LibraryAnalytics = {
  library_id: string; library_name: string; membership_role: 'ADMIN' | 'LIBRARIAN'; generated_at: string
  range: { key: AnalyticsRange; start_at: string | null; end_at: string; timezone: 'UTC'; bucket: 'day' | 'month'; trend_start_at: string; trend_window_limited: boolean }
  capabilities: { membership_breakdown: boolean; financial_detail: boolean; outbox_health: boolean }
  overview: { active_books: number; total_holding_quantity: number; requestable_units: AnalyticsCount; active_loans: AnalyticsCount; pending_borrow_requests: AnalyticsCount; pending_return_requests: AnalyticsCount; active_reservations: AnalyticsCount; open_fee_balance_minor: AnalyticsMinorAmount; currency: string | null; upcoming_events: number; active_members: number }
  collection: { available: true; active_books: number; total_holding_quantity: number; requestable_units: AnalyticsCount; circulation_status: { CIRCULATING: number; REFERENCE_ONLY: number; TEMPORARILY_UNAVAILABLE: number }; local_only_books: number; globally_linked_books: number; recent_acquisitions: number; subjects: { subject: string; count: number }[] }
  circulation: { available: boolean; unavailable_reason: string | null; pending_borrow_requests: AnalyticsCount; pending_return_requests: AnalyticsCount; active_loans: AnalyticsCount; requested_in_range: AnalyticsCount; approved_in_range: AnalyticsCount; rejected_in_range: AnalyticsCount; returns_confirmed_in_range: AnalyticsCount; renewals_in_range: AnalyticsCount }
  reservations: { available: boolean; unavailable_reason: string | null; active: AnalyticsCount; waiting: AnalyticsCount; ready: AnalyticsCount; fulfilled_in_range: AnalyticsCount; cancelled_in_range: AnalyticsCount; expired_in_range: AnalyticsCount; created_in_range: AnalyticsCount; average_queue_depth: number | null }
  fees: { available: boolean; unavailable_reason: string | null; currency: string | null; minor_units_per_major: number | null; open_count: AnalyticsCount; open_balance_minor: AnalyticsMinorAmount; assessed_in_range: AnalyticsCount; assessed_minor: AnalyticsMinorAmount; payments_minor: AnalyticsMinorAmount; waived_minor: AnalyticsMinorAmount; settled_minor: AnalyticsMinorAmount }
  events: { available: true; upcoming: number; published_in_range: number; cancelled_in_range: number; completed: number; drafts: number }
  membership: { active_total: number; role_counts: { ADMIN: number; LIBRARIAN: number; GENERAL_USER: number } | null }
  popular_books: { library_book_id: string; title: string; authors: string[]; global_work_id: string | null; score: number; loans: number; approved_requests: number; reservations: number }[]
  trends: AnalyticsTrend[]
  outbox: { pending: number; retry_required: number; delivered: number; suppressed: number } | null
}

export function libraryAnalyticsPath(libraryId: string, range: AnalyticsRange = '30d') {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(libraryId)) throw new Error('A canonical library UUID is required.')
  return `/libraries/${encodeURIComponent(libraryId)}/analytics?range=${range}`
}
export function fetchLibraryAnalytics(libraryId: string, range: AnalyticsRange, signal: AbortSignal) {
  return institutionApi<LibraryAnalytics>(libraryAnalyticsPath(libraryId, range), 'GET', undefined, signal)
}

/** Format persisted integer minor units without passing the amount through a float. */
export function analyticsMoney(amount: AnalyticsMinorAmount, currency: string | null, minorUnitsPerMajor: number | null = 100): string {
  if (amount === null || !currency || !minorUnitsPerMajor || !/^\d+$/.test(amount)) return 'Unavailable'
  const unit = BigInt(minorUnitsPerMajor)
  const digits = String(minorUnitsPerMajor).length - 1
  if (unit < 1n || unit !== 10n ** BigInt(digits)) return 'Unavailable'
  const value = BigInt(amount)
  const major = (value / unit).toLocaleString('en-IN')
  const fraction = digits ? `.${String(value % unit).padStart(digits, '0')}` : ''
  return `${currency} ${major}${fraction}`
}
