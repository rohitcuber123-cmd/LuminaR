export interface RenewalPolicy {
  eligible: boolean; enabled: boolean; days: number; max_renewals: number
  renewal_count: number; remaining_renewals: number; reason: string | null; message: string | null
}
export interface RenewalLoan { issue_id: number; due_date: string; renewal?: RenewalPolicy }
export interface RenewalResult {
  issue_id: number; work_id: string; old_due_date: string; new_due_date: string
  renewal_count: number; remaining_renewals: number; status: string; idempotent_replay: boolean
}
