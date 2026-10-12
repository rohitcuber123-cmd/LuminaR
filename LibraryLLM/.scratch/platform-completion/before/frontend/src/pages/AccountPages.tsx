import { useProductContext } from '../hooks/useProductContext'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { platformAdmin, usePlatformStore } from '../store/usePlatformStore'
import { useAuthStore } from '../store/useAuthStore'
import { useInstitutionStore } from '../store/useInstitutionStore'
import { isLibraryStaff, libraryRole, libraryWorkspaceHome, membershipLabel } from '../lib/libraryWorkspace'
import { PageHeading, StatePanel } from '../components/WorkspaceUI'

export function AccountProfilePage() {
  const context=useProductContext()
  const user = useAuthStore(s => s.user), token = useAuthStore(s => s.token), canManagePlatform = platformAdmin(usePlatformStore(), token)
  return <div className="global-page institutions"><PageHeading eyebrow="My account" title="Profile" description="Your LuminaR account connects your member libraries and staff workspaces." /><section className="ui-card"><h2>Account details</h2><dl className="ui-details"><div><dt>Name</dt><dd>{user?.name || user?.full_name || 'Not recorded'}</dd></div><div><dt>Email</dt><dd>{user?.email}</dd></div></dl><div className="ui-actions"><Link className="ui-button" to={context.personalPath('/account/libraries')}>My libraries</Link><Link className="ui-button ui-secondary" to={context.personalPath('/reading-list')}>Reading list</Link><Link to={context.personalPath('/account/history')}>Legacy account history</Link>{canManagePlatform && <Link to="/platform">Platform Console</Link>}</div></section></div>
}
export function MyLibrariesPage() {
  const state = useInstitutionStore(), [query, setQuery] = useState('')
  const token = useAuthStore(s => s.token)
  const libraries = state.session === token ? state.libraries : []
  const refresh = state.refresh
  useEffect(() => { void refresh() }, [refresh])
  const [params, setParams] = useSearchParams()
  const selectedGroup = ['patron', 'staff'].includes(params.get('group') || '') ? params.get('group') : 'all'
  const visible = libraries.filter(l => l.name.toLowerCase().includes(query.trim().toLowerCase()))
  const patrons = visible.filter(l => libraryRole(l) === 'GENERAL_USER'), staff = visible.filter(isLibraryStaff)
  const group = (rows: typeof patrons, title: string, staffMode: boolean) => <section className="ui-library-group"><h2>{title}</h2>{rows.length ? <div className="institution-grid">{rows.map(l => <article className="ui-card" key={l.library_id}><span className="ui-badge">{membershipLabel(l)}</span><h3>{l.name}</h3><p>{l.access_mode === 'PUBLIC' ? 'Public library' : 'Private institution'}{l.address?.city ? ` · ${l.address.city}` : ''}</p><Link className="ui-button" to={libraryWorkspaceHome(l)}>{staffMode ? 'Open Staff Workspace' : 'Open Library'}</Link></article>)}</div> : <StatePanel title={query ? 'No matching libraries' : staffMode ? 'No staff workspaces yet' : 'No member libraries yet'}>{query ? 'Try another library name.' : staffMode ? 'Accept a staff invitation or register your own library.' : 'Explore public libraries or join your institution.'}</StatePanel>}</section>
  return <div className="global-page institutions"><PageHeading eyebrow="My account" title="My libraries" description="Your membership in each library determines the workspace you can open." actions={<><Link className="ui-button ui-secondary" to="/libraries">Explore Libraries</Link><Link className="ui-button" to="/libraries/register">Register a Library</Link></>} /><div className="ui-tabs" aria-label="Library groups">{[{ value: 'all', label: 'All libraries' }, { value: 'patron', label: 'Member libraries' }, { value: 'staff', label: 'Staff workspaces' }].map(item => <button key={item.value} className={selectedGroup === item.value ? '' : 'secondary'} aria-pressed={selectedGroup === item.value} onClick={() => { const next = new URLSearchParams(params); if (item.value === 'all') next.delete('group'); else next.set('group', item.value); setParams(next) }}>{item.label}</button>)}</div><label className="ui-library-search">Find one of your libraries<input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search by library name" /></label>{state.error && <StatePanel kind="error" title="Unable to load memberships" action={<button onClick={() => void state.refresh()}>Retry</button>}>{state.error}</StatePanel>}{state.loading && !state.libraries.length ? <StatePanel kind="loading" title="Loading your libraries…" /> : <>{selectedGroup !== 'staff' && group(patrons, 'Member libraries', false)}{selectedGroup !== 'patron' && group(staff, 'Staff libraries', true)}{selectedGroup === 'all' && visible.filter(l => !libraryRole(l)).map(l => <div className="ui-state" key={l.library_id}><strong>{l.name}</strong><p>{l.membership?.status} membership · Contact library staff to restore access.</p></div>)}</>}</div>
}
