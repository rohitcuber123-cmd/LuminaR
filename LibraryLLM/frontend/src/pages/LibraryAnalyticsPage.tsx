import { LuminarSelect } from '../components/LuminarSelect'
import { LibraryBookTitleLink } from '../components/LibraryBookTitleLink'
import { useEffect, useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { PageHeading, StatePanel } from '../components/WorkspaceUI'
import { analyticsMoney, fetchLibraryAnalytics, type AnalyticsRange, type AnalyticsTrend, type LibraryAnalytics } from '../lib/libraryAnalytics'
import { libraryRole, staffPath } from '../lib/libraryWorkspace'
import { useAuthStore } from '../store/useAuthStore'
import { useInstitutionStore } from '../store/useInstitutionStore'
import './LibraryAnalytics.css'

const count = (value: number | null | undefined) => value == null ? 'Unavailable' : value.toLocaleString()
const utcDate = (value: string | null) => value ? value.slice(0, 10) : 'the first canonical record'
const ranges: { value: AnalyticsRange; label: string }[] = [{ value: '7d', label: '7 days' }, { value: '30d', label: '30 days' }, { value: '90d', label: '90 days' }, { value: 'all', label: 'All time' }]
type Metric = { label: string; value: ReactNode }
function Metrics({ items, snapshot = false }: { items: Metric[]; snapshot?: boolean }) {
  return <dl className={snapshot ? 'analytics-snapshot-grid' : 'analytics-metrics'}>{items.map(item => <div key={item.label} className={snapshot ? 'ui-card' : undefined}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}</dl>
}
function AnalyticsSection({ title, children, description, unavailable }: { title: string; children: ReactNode; description?: string; unavailable?: string | null }) {
  return <section className="ui-card analytics-section"><h2>{title}</h2>{description && <p>{description}</p>}{unavailable ? <p className="analytics-unavailable">Unavailable · {unavailable}</p> : children}</section>
}

export function LibraryAnalyticsPage() {
  const { libraryId = '' } = useParams(), token = useAuthStore(s => s.token), user = useAuthStore(s => s.user)
  const state = useInstitutionStore(), library = state.libraries.find(row => row.library_id === libraryId), role = libraryRole(library)
  if (!token || state.session !== token) return <StatePanel title="Loading library permissions…" kind="loading" />
  if (!library || !['ADMIN', 'LIBRARIAN'].includes(role || '')) return <StatePanel title="Staff membership required">Analytics is available only to active staff of this library.</StatePanel>
  return <AnalyticsView key={`${libraryId}:${token}:${user?.user_id}:${role}`} libraryId={libraryId} name={library.name} token={token} admin={role === 'ADMIN'} />
}

function AnalyticsView({ libraryId, name, token, admin }: { libraryId: string; name: string; token: string; admin: boolean }) {
  const [range, setRange] = useState<AnalyticsRange>('30d'), [revision, setRevision] = useState(0)
  const [result, setResult] = useState<{ key: string; data?: LibraryAnalytics; error?: string } | null>(null)
  const key = `${libraryId}:${token}:${range}:${revision}`
  useEffect(() => {
    let alive = true; const controller = new AbortController()
    void fetchLibraryAnalytics(libraryId, range, controller.signal).then(data => {
      if (!alive || controller.signal.aborted || useAuthStore.getState().token !== token || useInstitutionStore.getState().session !== token) return
      if (data.library_id !== libraryId || !['ADMIN', 'LIBRARIAN'].includes(data.membership_role) || data.range.key !== range) throw new Error('Analytics response did not match the current library context.')
      setResult({ key, data })
    }).catch(error => {
      if (alive && !controller.signal.aborted) setResult({ key, error: error instanceof Error ? error.message : 'Unable to load library analytics.' })
    })
    return () => { alive = false; controller.abort() }
  }, [libraryId, range, token, key])
  const data = result?.key === key ? result.data : undefined, error = result?.key === key ? result.error : undefined
  return <div className="institutions library-analytics"><PageHeading title="Analytics" description={`Operational aggregates for ${name}.`} />
    <div className="analytics-toolbar"><label htmlFor="analytics-range">Activity range<LuminarSelect id="analytics-range" value={range} onChange={event => setRange(event.target.value as AnalyticsRange)}>{ranges.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</LuminarSelect></label><button className="ui-button ui-secondary" onClick={() => setRevision(value => value + 1)}>Refresh analytics</button></div>
    <p className="analytics-range-note">Snapshot cards show current state. Activity uses persisted library records and UTC date boundaries.</p>
    {error ? <StatePanel title="Unable to load analytics" kind="error" action={<button className="ui-button" onClick={() => setRevision(value => value + 1)}>Retry</button>}>{error}</StatePanel> : !data ? <StatePanel title="Loading library analytics…" kind="loading" /> : <AnalyticsContent data={data} admin={admin && data.membership_role === 'ADMIN'} />}
  </div>
}

function AnalyticsContent({ data, admin }: { data: LibraryAnalytics; admin: boolean }) {
  const o = data.overview, c = data.collection, lending = data.circulation, res = data.reservations, fees = data.fees, events = data.events
  const money = (value: string | null) => analyticsMoney(value, fees.currency, fees.minor_units_per_major)
  return <><p className="analytics-range-note">Activity from {utcDate(data.range.start_at)} through {utcDate(data.range.end_at)} (UTC). Updated <time dateTime={data.generated_at}>{data.generated_at.replace('T', ' ').replace('Z', ' UTC')}</time>.</p>
    <section aria-labelledby="analytics-snapshot-heading"><h2 id="analytics-snapshot-heading">Current snapshot</h2><Metrics snapshot items={[{ label: 'Active local books', value: count(o.active_books) }, { label: 'Active loans', value: count(o.active_loans) }, { label: 'Pending borrow requests', value: count(o.pending_borrow_requests) }, { label: 'Pending return requests', value: count(o.pending_return_requests) }, { label: 'Active reservations', value: count(o.active_reservations) }, { label: 'Open fee balance', value: analyticsMoney(o.open_fee_balance_minor, o.currency, fees.minor_units_per_major) }, { label: 'Upcoming events', value: count(o.upcoming_events) }, { label: 'Active members', value: count(o.active_members) }]} /></section>
    {o.active_books === 0 && <StatePanel title="No active books in this library">Analytics will reflect canonical operations as your library begins using its collection.</StatePanel>}
    <div className="analytics-section-grid">
      <AnalyticsSection title="Collection" description="Current local catalogue and holdings. Acquisitions use the selected activity range."><Metrics items={[{ label: 'Active books', value: count(c.active_books) }, { label: 'Holdings quantity', value: count(c.total_holding_quantity) }, { label: 'Requestable units', value: count(c.requestable_units) }, { label: 'Circulating records', value: count(c.circulation_status.CIRCULATING) }, { label: 'Reference-only records', value: count(c.circulation_status.REFERENCE_ONLY) }, { label: 'Temporarily unavailable', value: count(c.circulation_status.TEMPORARILY_UNAVAILABLE) }, { label: 'Local-only books', value: count(c.local_only_books) }, { label: 'Globally linked local books', value: count(c.globally_linked_books) }, { label: 'Acquired in range', value: count(c.recent_acquisitions) }]} /></AnalyticsSection>
      <AnalyticsSection title="Circulation" description="Current queues and loans, followed by activity in range." unavailable={!lending.available ? lending.unavailable_reason || 'Canonical circulation is not available.' : null}><Metrics items={[{ label: 'Pending borrow requests', value: count(lending.pending_borrow_requests) }, { label: 'Pending return requests', value: count(lending.pending_return_requests) }, { label: 'Active loans', value: count(lending.active_loans) }, { label: 'Requested in range', value: count(lending.requested_in_range) }, { label: 'Approved in range', value: count(lending.approved_in_range) }, { label: 'Rejected in range', value: count(lending.rejected_in_range) }, { label: 'Returns confirmed in range', value: count(lending.returns_confirmed_in_range) }, { label: 'Renewals in range', value: count(lending.renewals_in_range) }]} /></AnalyticsSection>
      <AnalyticsSection title="Reservations" description="Current queue state and persisted reservation activity in range." unavailable={!res.available ? res.unavailable_reason || 'Canonical reservations are not available.' : null}><Metrics items={[{ label: 'Active reservations', value: count(res.active) }, { label: 'Waiting', value: count(res.waiting) }, { label: 'Ready for approval', value: count(res.ready) }, { label: 'Created in range', value: count(res.created_in_range) }, { label: 'Fulfilled in range', value: count(res.fulfilled_in_range) }, { label: 'Cancelled in range', value: count(res.cancelled_in_range) }, { label: 'Expired in range', value: count(res.expired_in_range) }, { label: 'Average waiting queue depth', value: res.average_queue_depth == null ? 'Unavailable' : res.average_queue_depth.toLocaleString(undefined, { maximumFractionDigits: 2 }) }]} /></AnalyticsSection>
      <AnalyticsSection title="Fees" description="Recorded charges and desk payments. Money is shown in the canonical currency." unavailable={!fees.available ? fees.unavailable_reason || 'Canonical fees are not available.' : null}><Metrics items={[{ label: 'Open fee count', value: count(fees.open_count) }, { label: 'Open balance', value: money(fees.open_balance_minor) }, { label: 'Fees assessed in range', value: count(fees.assessed_in_range) }, { label: 'Assessed amount in range', value: money(fees.assessed_minor) }, { label: 'Payments recorded in range', value: money(fees.payments_minor) }, ...(admin && data.capabilities.financial_detail ? [{ label: 'Waived amount in range', value: money(fees.waived_minor) }, { label: 'Settled amount in range', value: money(fees.settled_minor) }] : [])]} /></AnalyticsSection>
      <AnalyticsSection title="Events" description="Current published schedule and canonical event activity in range."><Metrics items={[{ label: 'Upcoming events', value: count(events.upcoming) }, { label: 'Published in range', value: count(events.published_in_range) }, { label: 'Cancelled in range', value: count(events.cancelled_in_range) }, { label: 'Completed published events', value: count(events.completed) }, { label: 'Draft events', value: count(events.drafts) }]} /></AnalyticsSection>
      <AnalyticsSection title="Membership" description="Active membership totals. Individual reading histories are excluded."><Metrics items={[{ label: 'Active members', value: count(data.membership.active_total) }, ...(admin && data.capabilities.membership_breakdown && data.membership.role_counts ? [{ label: 'Admins', value: count(data.membership.role_counts.ADMIN) }, { label: 'Librarians', value: count(data.membership.role_counts.LIBRARIAN) }, { label: 'General users', value: count(data.membership.role_counts.GENERAL_USER) }] : [])]} /></AnalyticsSection>
    </div>
    <SubjectDistribution subjects={c.subjects} />
    <PopularBooks libraryId={data.library_id} rows={data.popular_books} />
    <ActivityTable data={data} />
    {admin && data.capabilities.outbox_health && data.outbox && <AnalyticsSection title="Notification delivery health" description="Current delivery state for this library. Notification content is excluded."><Metrics items={[{ label: 'Pending deliveries', value: count(data.outbox.pending) }, { label: 'Retry required', value: count(data.outbox.retry_required) }, { label: 'Delivered', value: count(data.outbox.delivered) }, { label: 'Suppressed', value: count(data.outbox.suppressed) }]} /></AnalyticsSection>}
  </>
}

function SubjectDistribution({ subjects }: { subjects: LibraryAnalytics['collection']['subjects'] }) {
  const maximum = Math.max(1, ...subjects.map(item => item.count))
  return <AnalyticsSection title="Subject distribution" description="Up to 20 subjects from active local books. A book can have more than one subject.">{subjects.length ? <table className="analytics-table analytics-subjects"><caption>Active books by local subject</caption><thead><tr><th scope="col">Subject</th><th scope="col">Books</th></tr></thead><tbody>{subjects.map(item => <tr key={item.subject}><th scope="row">{item.subject}<span className="analytics-subject-bar" aria-hidden="true"><span style={{ width: `${item.count / maximum * 100}%` }} /></span></th><td>{count(item.count)}</td></tr>)}</tbody></table> : <p>No subject data for active local books.</p>}</AnalyticsSection>
}
function PopularBooks({ rows, libraryId }: { rows: LibraryAnalytics['popular_books']; libraryId: string }) {
  return <AnalyticsSection title="Popular books" description="Up to 10 local books ranked from canonical loans, approved requests and reservations in range. No member ranking.">{rows.length ? <table className="analytics-table"><caption>Book activity in the selected range</caption><thead><tr><th scope="col">Local book</th><th scope="col">Activity</th></tr></thead><tbody>{rows.map(row => <tr key={row.library_book_id}><th scope="row"><LibraryBookTitleLink libraryId={libraryId} bookId={row.library_book_id} staff title={row.title} />{row.authors.length > 0 && <span className="analytics-table-note">{row.authors.join('; ')}</span>}</th><td><span>{count(row.loans)} loans</span><span>{count(row.approved_requests)} approved requests</span><span>{count(row.reservations)} reservations</span></td></tr>)}</tbody></table> : <p>No canonical book activity in this range.</p>}</AnalyticsSection>
}
const series: { key: Exclude<keyof AnalyticsTrend, 'date'>; label: string; money?: boolean; source?: 'circulation' | 'reservations' | 'fees' }[] = [
  { key: 'acquisitions', label: 'Acquisitions' }, { key: 'borrow_requests', label: 'Borrow requests', source: 'circulation' }, { key: 'loans_issued', label: 'Loans issued', source: 'circulation' }, { key: 'returns_confirmed', label: 'Returns confirmed', source: 'circulation' }, { key: 'renewals', label: 'Renewals', source: 'circulation' }, { key: 'reservations', label: 'Reservations created', source: 'reservations' }, { key: 'events_published', label: 'Events published' }, { key: 'fees_assessed_minor', label: 'Fees assessed', money: true, source: 'fees' }, { key: 'payments_minor', label: 'Payments recorded', money: true, source: 'fees' },
]
function ActivityTable({ data }: { data: LibraryAnalytics }) {
  const [metric, setMetric] = useState<Exclude<keyof AnalyticsTrend, 'date'>>('loans_issued'), selected = series.find(item => item.key === metric)!
  const available = !selected.source || data[selected.source].available
  return <AnalyticsSection title="Activity over time" description={`Persisted operations grouped by UTC ${data.range.bucket === 'month' ? 'month' : 'day'}. The table provides the complete values for each displayed bucket.`}>
    <label className="analytics-series-selector" htmlFor="analytics-series">Activity metric<LuminarSelect id="analytics-series" value={metric} onChange={event => setMetric(event.target.value as Exclude<keyof AnalyticsTrend, 'date'>)}>{series.map(item => <option key={item.key} value={item.key}>{item.label}</option>)}</LuminarSelect></label>
    {data.range.trend_window_limited && <p>The all-time totals cover all canonical records; the trend table is limited to recent buckets.</p>}
    {!available ? <p>Unavailable · Canonical records for this activity are not available.</p> : data.trends.length ? <div className="analytics-trend-scroll" tabIndex={0} role="region" aria-label={`${selected.label} activity table`}><table className="analytics-table"><caption>{selected.label} by UTC {data.range.bucket === 'month' ? 'month' : 'day'}</caption><thead><tr><th scope="col">UTC {data.range.bucket === 'month' ? 'month' : 'date'}</th><th scope="col">{selected.label}</th></tr></thead><tbody>{data.trends.map(row => { const value = row[metric]; return <tr key={row.date}><th scope="row">{row.date}</th><td>{selected.money ? analyticsMoney(typeof value === 'string' ? value : null, data.fees.currency, data.fees.minor_units_per_major) : count(typeof value === 'number' ? value : null)}</td></tr> })}</tbody></table></div> : <p>No canonical activity to display in this range.</p>}
    <p className="analytics-privacy-note">Analytics contains operational aggregates only. Use <Link to={staffPath(data.library_id, 'activity')}>Operational Activity</Link> for authorized library workflows.</p>
  </AnalyticsSection>
}
