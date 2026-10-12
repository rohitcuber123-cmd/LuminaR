import { date, Pager, Table } from './StaffUI'
import type { Page } from '../lib/institutions'

export type ActivityIdentity = { user_id: number | null; display_name: string | null; email: string | null; identity_source: 'CURRENT_ACCOUNT' | 'EVENT_SNAPSHOT' }
export type StaffActivity = { event_id: string; event: string; created_at: string; actor_user_id: number | null; target_user_id?: number | null; actor?: ActivityIdentity | null; member?: ActivityIdentity | null; metadata?: { library_book_id?: string; loan_id?: string; reservation_id?: string; fee_id?: string; asset_id?: string } }

export function ActivityAccount({ identity, userId, actor = false }: { identity?: ActivityIdentity | null; userId?: number | null; actor?: boolean }) {
  if (identity?.email) return <span className="staff-activity-identity" title={`${identity.identity_source === 'EVENT_SNAPSHOT' ? 'Email recorded at event time' : 'Current account email'}${userId != null ? ` · Account #${userId}` : ''}`}>{identity.email}</span>
  if (identity?.display_name) return <span className="staff-activity-identity" title={userId != null ? `Account #${userId}` : undefined}>{identity.display_name}</span>
  if (userId != null) return <span title="Account identity unavailable">Account #{userId}</span>
  return <span>{actor ? 'System' : '—'}</span>
}

export function ActivityReference({ value }: { value?: string }) {
  if (!value) return <>—</>
  const short = value.length > 20 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value
  return <span className="staff-activity-reference" title={value}><span aria-hidden="true">{short}</span><span className="sr-only">{value}</span></span>
}

export function StaffActivityTable({ data, page, onPageChange, operational = false }: { data: Page<StaffActivity>; page: number; onPageChange: (page: number) => void; operational?: boolean }) {
  const label = operational ? 'Operational activity' : 'Library audit'
  return <div className="staff-activity-results">
    <p className="staff-activity-identity-note">Account emails reflect current account details. Event references remain unchanged.</p>
    <Table label={label} className={`staff-activity-table ${operational ? 'staff-operational-table' : 'staff-audit-table'}`} headers={operational ? ['When', 'Event', 'Actor', 'Member / subject', 'Reference'] : ['When', 'Event', 'Actor']} widths={operational ? ['16%', '22%', '23%', '23%', '16%'] : ['24%', '38%', '38%']} count={data.results.length} empty={operational ? 'No operational activity yet' : 'No audit activity yet'}>
      {data.results.map(row => <tr key={row.event_id}>
        <td><time dateTime={row.created_at}>{date(row.created_at)}</time></td>
        <td><span title={row.event}>{row.event.charAt(0) + row.event.slice(1).toLowerCase().replaceAll('_', ' ')}</span></td>
        <td><ActivityAccount identity={row.actor} userId={row.actor_user_id} actor /></td>
        {operational && <><td><ActivityAccount identity={row.member} userId={row.target_user_id} /></td><td><ActivityReference value={row.metadata?.loan_id || row.metadata?.reservation_id || row.metadata?.fee_id || row.metadata?.library_book_id || row.metadata?.asset_id} /></td></>}
      </tr>)}
    </Table>
    <Pager page={page} count={data.total ?? 0} onChange={onPageChange} label={`${label} pagination`} />
  </div>
}
