import { useProductContext } from '../hooks/useProductContext'
import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { coreRequest } from '../lib/api'
import { PageHeading, StatePanel } from '../components/WorkspaceUI'
import { date } from '../components/StaffUI'

/** Personal history is compatibility data, never a second borrowing implementation. */
export function LegacyProfilePage() {
  const context=useProductContext()
  const [data, setData] = useState<{ issues: Record<string, unknown>[]; reservations: Record<string, unknown>[]; fines: Record<string, unknown>[]; activities: Record<string, unknown>[] } | null>(null)
  const [error, setError] = useState(''), [revision, setRevision] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    void Promise.all([coreRequest<{ issues: Record<string, unknown>[] }>('/issues/my', { signal: controller.signal }),
      coreRequest<{ reservations: Record<string, unknown>[] }>('/reservations/my', { signal: controller.signal }),
      coreRequest<{ fines: Record<string, unknown>[] }>('/fines/my', { signal: controller.signal }),
      coreRequest<{ activities: Record<string, unknown>[] }>('/activity/my', { signal: controller.signal })])
      .then(([issues, reservations, fines, activities]) => { if (!controller.signal.aborted) { setData({ ...issues, ...reservations, ...fines, ...activities }); setError('') } })
      .catch(e => { if (!controller.signal.aborted) setError(e.message) })
    return () => controller.abort()
  }, [revision])
  return <div className="global-page institutions"><PageHeading title="Account history" description="Read-only records from the former circulation system. Current library activity belongs in My Library." actions={<Link className="ui-button ui-secondary" to={context.personalPath('/account/libraries?group=patron')}>Open a member library</Link>} />{error ? <StatePanel kind="error" title="Unable to load account history" action={<button onClick={() => setRevision(v => v + 1)}>Retry</button>}>{error}</StatePanel> : !data ? <StatePanel kind="loading" title="Loading account history…" /> : Object.entries(data).map(([kind, rows]) => <section className="ui-card" key={kind}><h2>{kind === 'issues' ? 'Historical loans' : kind === 'fines' ? 'Historical fees' : kind === 'activities' ? 'Historical activity' : 'Historical reservations'}</h2>{!rows.length ? <p>No historical records.</p> : <div className="ui-table-wrap" tabIndex={0}><table className="ui-table"><thead><tr><th>Book / Activity</th><th>Status</th><th>Date</th></tr></thead><tbody>{rows.map((row, index) => <tr key={index}><td>{String(row.title || row.description || row.work_id || 'Historical record')}</td><td>{String(row.status || row.activity_type || '—')}</td><td>{date(String(row.issued_at || row.reserved_at || row.created_at || row.activity_date || ''))}</td></tr>)}</tbody></table></div>}</section>)}</div>
}
export function ProfilePage() { return <Navigate to="/my-library" replace /> }
