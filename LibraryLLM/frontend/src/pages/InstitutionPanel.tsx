import { LuminarSelect } from '../components/LuminarSelect'
import { membershipLabel } from '../lib/libraryWorkspace'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Modal } from '../components/StaffUI'
import { StaffActivityTable, type StaffActivity } from '../components/StaffActivityTable'
import { PageHeading, StatePanel } from '../components/WorkspaceUI'
import { institutionApi, invitationLink, type AccessSettings, type Invitation, type LibraryRole, type MemberRow, type Page } from '../lib/institutions'
import { activeLibrary, useInstitutionStore } from '../store/useInstitutionStore'
import { scrollToContentAnchor } from '../lib/paginationScroll'
import { CodeFields } from './Institutions'
import './Institutions.css'

type AuditRow = StaffActivity

type InstitutionSection = 'all' | 'settings' | 'members' | 'audit'
export function InstitutionPanel({ section = 'all' }: { section?: InstitutionSection }) {
  const current = useInstitutionStore(activeLibrary)
  if (current?.membership?.status !== 'ACTIVE' || !['ADMIN', 'LIBRARIAN'].includes(current.membership.role)) return <div className="institutions"><h2>Institution / Library</h2><p>Select a library where you have active staff membership.</p><Link to="/libraries">Explore Libraries</Link></div>
  return <InstitutionDetails key={`${current.library_id}:${current.membership.role}:${section}`} libraryId={current.library_id} section={section} />
}

function InstitutionDetails({ libraryId, section }: { libraryId: string; section: InstitutionSection }) {
  const showSettings = section === 'all' || section === 'settings', showMembers = section === 'all' || section === 'members', showAudit = section === 'all' || section === 'audit'
  const current = useInstitutionStore(activeLibrary)!
  const admin = current.membership?.role === 'ADMIN', owner = !!current.membership?.is_owner
  const [settings, setSettings] = useState<AccessSettings | null>(null)
  const [members, setMembers] = useState<Page<MemberRow>>({ results: [] }), [invitations, setInvitations] = useState<Page<Invitation>>({ results: [] }), [events, setEvents] = useState<Page<AuditRow>>({ results: [] })
  const [page, setPage] = useState(0), [invitePage, setInvitePage] = useState(0), [auditPage, setAuditPage] = useState(0), [revision, setRevision] = useState(0)
  const [error, setError] = useState(''), [success, setSuccess] = useState(''), [busy, setBusy] = useState(false), [loading, setLoading] = useState(true)
  const [email, setEmail] = useState(''), [role, setRole] = useState<LibraryRole>('LIBRARIAN')
  const [dialog, setDialog] = useState<'code' | 'access' | null>(null), [mode, setMode] = useState(current.access_mode)
  const [code, setCode] = useState(''), [confirm, setConfirm] = useState(''), [link, setLink] = useState('')
  const [action, setAction] = useState<{ row: MemberRow; status: string } | null>(null)
  const [profile, setProfile] = useState({ name: current.name, description: current.description || '', contact_email: current.contact_email || '', phone: current.phone || '', city: current.address?.city || '', region: current.address?.region || '', country: current.address?.country || '' })
  const base = `/libraries/${libraryId}`
  useEffect(() => {
    let alive = true; const controller = new AbortController();
    async function load() {
      setLoading(true); setError('')
      try {
        const result = await Promise.all([
          institutionApi<AccessSettings>(`${base}/access`, 'GET', undefined, controller.signal),
          admin && showMembers ? institutionApi<Page<MemberRow>>(`${base}/memberships?offset=${page * 20}`, 'GET', undefined, controller.signal) : null,
          admin && showMembers ? institutionApi<Page<Invitation>>(`${base}/invitations?offset=${invitePage * 20}`, 'GET', undefined, controller.signal) : null,
          admin && showAudit ? institutionApi<Page<AuditRow>>(`${base}/audit?offset=${auditPage * 20}`, 'GET', undefined, controller.signal) : null,
        ])
        if (!alive) return
        setSettings(result[0] as AccessSettings)
        if (admin && showMembers) { setMembers(result[1] as Page<MemberRow>); setInvitations(result[2] as Page<Invitation>) }
        if (admin && showAudit) setEvents(result[3] as Page<AuditRow>)
      } catch (reason) { if (alive) setError(reason instanceof Error ? reason.message : 'Unable to load library settings.') }
      finally { if (alive) setLoading(false) }
    }
    void load(); return () => { alive = false; controller.abort() }
  }, [base, admin, showMembers, showAudit, page, invitePage, auditPage, revision])
  async function run(work: () => Promise<unknown>, text: string) {
    setBusy(true); setError(''); setSuccess('')
    try { await work(); setSuccess(text); setRevision(r => r + 1); await useInstitutionStore.getState().refresh(); return true }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to complete this action.'); return false }
    finally { setBusy(false) }
  }
  const close = () => { setDialog(null); setCode(''); setConfirm('') }
  const canManage = (row: MemberRow) => !row.is_owner && (owner || row.role !== 'ADMIN')
  const pages = (value: Page<unknown>, index: number, setter: (value: number) => void) => <div className="institution-actions"><button className="secondary" disabled={busy || loading || index === 0} onClick={() => { setter(index - 1); requestAnimationFrame(() => scrollToContentAnchor('.institution-table-wrap, .institutions')) }}>Previous</button><span>Page {index + 1}</span><button className="secondary" disabled={busy || loading || (index + 1) * 20 >= (value.total ?? 0)} onClick={() => { setter(index + 1); requestAnimationFrame(() => scrollToContentAnchor('.institution-table-wrap, .institutions')) }}>Next</button></div>
  return <div className="institutions">{section === 'all' ? <h2>Institution / Library · {current.name}</h2> : <PageHeading title={section === 'settings' ? 'Library Settings' : section === 'members' ? 'Members & Staff' : 'Audit / Activity'} description={section === 'settings' ? 'Manage the library profile and access settings.' : section === 'members' ? 'Manage membership and invite library staff.' : 'Admin-only security, membership and administrative audit. Day-to-day library work appears in Operational Activity.'} />}{section === 'all' && <p className="ui-badge">{membershipLabel(current)}</p>}
    {error && <StatePanel kind="error" title="Unable to complete this library action" action={<button onClick={() => setRevision(r => r + 1)}>Retry</button>}>{error}</StatePanel>}{success && <p role="status" className="institution-success">{success}</p>}
    {loading && <StatePanel kind="loading" title="Loading library settings…" />}
    {showSettings && <section className="institution-card"><h2>Access Control</h2><p>Type: {current.access_mode === 'PUBLIC' ? 'Public Library' : 'Private Institution'}</p>
      {current.access_mode === 'PRIVATE_CODE' && <><p>Access Code: {settings?.access_code_set ? 'SET' : 'Loading…'}</p><p>Last changed: {settings?.access_code_changed_at ? new Date(settings.access_code_changed_at).toLocaleString() : '—'} · Changed by: {settings?.access_code_changed_by ? `User #${settings.access_code_changed_by}` : '—'}</p><button disabled={busy || loading} onClick={() => { close(); setDialog('code') }}>Change Access Code</button></>}
      {admin && <p><button className="secondary" disabled={busy || loading} onClick={() => { close(); setMode(current.access_mode === 'PUBLIC' ? 'PRIVATE_CODE' : 'PUBLIC'); setDialog('access') }}>{current.access_mode === 'PUBLIC' ? 'Change to Private Institution' : 'Change to Public Library'}</button></p>}
    </section>}
    {admin && <>{showSettings && <section className="institution-card"><h2>Library Profile</h2><form className="institution-form" onSubmit={e => { e.preventDefault(); void run(() => institutionApi(base, 'PATCH', { name: profile.name, description: profile.description || null, contact_email: profile.contact_email || null, phone: profile.phone || null, address: { ...current.address, city: profile.city, region: profile.region, country: profile.country } }), 'Library profile updated.') }}>
      {(['name', 'description', 'contact_email', 'phone', 'city', 'region', 'country'] as const).map(key => <label key={key}>{{ name: 'Name', description: 'Description', contact_email: 'Contact email', phone: 'Phone', city: 'City', region: 'Region', country: 'Country' }[key]}<input type={key === 'contact_email' ? 'email' : 'text'} required={key === 'name'} maxLength={key === 'description' ? 2000 : key === 'phone' ? 40 : key === 'name' ? 200 : 100} value={profile[key]} onChange={e => setProfile(old => ({ ...old, [key]: e.target.value }))} /></label>)}<button disabled={busy || loading}>Save Library Profile</button></form></section>}
      {showMembers && <><section className="institution-card"><h2>Add Staff</h2><p>Invite staff by email. They choose their own password when creating an account.</p><form className="institution-form" onSubmit={e => { e.preventDefault(); void run(async () => {
        const result = await institutionApi<{ invitation: Invitation; invite_token: string }>(`${base}/invitations`, 'POST', { email, role })
        setLink(invitationLink(result.invitation.invitation_id, result.invite_token)); setEmail('')
      }, 'Staff invitation created.') }}><label>Staff Email<input type="email" required value={email} onChange={e => setEmail(e.target.value)} /></label><label>Staff Role<LuminarSelect value={role} onChange={e => setRole(e.target.value as LibraryRole)}><option value="LIBRARIAN">Librarian</option>{owner && <option value="ADMIN">Admin</option>}</LuminarSelect></label><button disabled={busy || loading}>Add Staff</button></form></section>
      <section><h2>Members & Staff</h2><div className="institution-table-wrap" tabIndex={0} aria-label="Library members"><table><thead><tr>{['Name / Email', 'Role', 'Status', 'Joined', 'Actions'].map(h => <th key={h}>{h}</th>)}</tr></thead><tbody>{members.results.map(row => <tr key={row.membership_id}><td>{row.name}<br />{row.email}{row.is_owner && <p className="institution-badge">Owner</p>}</td><td>{canManage(row) ? <LuminarSelect aria-label={`Role for ${row.email}`} value={row.role} disabled={busy || loading} onChange={e => void run(() => institutionApi(`${base}/memberships/${row.membership_id}`, 'PATCH', { role: e.target.value }), 'Member role updated.')}><option value="GENERAL_USER">Member</option><option value="LIBRARIAN">Librarian</option>{owner && <option value="ADMIN">Admin</option>}</LuminarSelect> : row.role}</td><td>{row.status}</td><td>{new Date(row.joined_at).toLocaleDateString()}</td><td>{canManage(row) && <div className="institution-actions">{row.status === 'ACTIVE' ? <button className="secondary" disabled={busy} onClick={() => setAction({ row, status: 'SUSPENDED' })}>Suspend</button> : <button className="secondary" disabled={busy} onClick={() => setAction({ row, status: 'ACTIVE' })}>Reactivate</button>}{row.status !== 'REMOVED' && <button className="secondary" disabled={busy} onClick={() => setAction({ row, status: 'REMOVED' })}>Remove</button>}</div>}</td></tr>)}</tbody></table></div>{pages(members, page, setPage)}</section>
      <section><h2>Staff Invitations</h2><div className="institution-table-wrap" tabIndex={0} aria-label="Staff invitations"><table><thead><tr>{['Email', 'Role', 'Invited By', 'Expires', 'Status', 'Actions'].map(h => <th key={h}>{h}</th>)}</tr></thead><tbody>{invitations.results.map(row => <tr key={row.invitation_id}><td>{row.email_normalized}</td><td>{row.role}</td><td>User #{row.invited_by_user_id}</td><td>{new Date(row.expires_at).toLocaleString()}</td><td>{row.status}</td><td>{row.status === 'PENDING' && (owner || row.role === 'LIBRARIAN') && <button className="secondary" disabled={busy} onClick={() => void run(() => institutionApi(`${base}/invitations/${row.invitation_id}/revoke`, 'POST'), 'Invitation revoked.')}>Revoke</button>}</td></tr>)}</tbody></table></div>{pages(invitations, invitePage, setInvitePage)}</section></>}
      {showAudit && <section><h2>Library Audit</h2><StaffActivityTable data={events} page={auditPage} onPageChange={setAuditPage} /></section>}
    </>}
    {dialog && <Modal title={dialog === 'code' ? 'Change Access Code' : 'Change Library Access'} busy={busy} onClose={close}><div className="institutions"><p>Existing members will remain members. New users will {dialog === 'access' && mode === 'PUBLIC' ? 'be able to join without a code.' : 'need the new code.'}</p>
      <form className="institution-form" onSubmit={e => { e.preventDefault(); if ((dialog === 'code' || mode === 'PRIVATE_CODE') && code !== confirm) { setError('Access codes do not match.'); return }
        void run(() => dialog === 'code' ? institutionApi(`${base}/access-code`, 'PUT', { access_code: code }) : institutionApi(`${base}/access`, 'PUT', { access_mode: mode, ...(mode === 'PRIVATE_CODE' ? { access_code: code } : {}) }), 'Access settings updated.').then(ok => { if (ok) close() })
      }}>{(dialog === 'code' || mode === 'PRIVATE_CODE') && <CodeFields code={code} confirm={confirm} onCode={setCode} onConfirm={setConfirm} />}{error && <p role="alert" className="institution-error">{error}</p>}<button disabled={busy}>Confirm Change</button></form></div></Modal>}
    {link && <Modal title="Copy Invite Link" onClose={() => setLink('')}><div className="institutions"><p>Copy this link now and share it with the invited staff member. It is shown only once.</p><label>Invite Link<input aria-label="Invite Link" readOnly value={link} onFocus={e => e.target.select()} /></label><p><button onClick={() => { void navigator.clipboard.writeText(link).then(() => setSuccess('Invite link copied.')).catch(() => setError('Select and copy the invite link manually.')) }}>Copy Invite Link</button></p></div></Modal>}
    {action && <Modal title={`${action.status === 'ACTIVE' ? 'Reactivate' : action.status === 'REMOVED' ? 'Remove' : 'Suspend'} Library Membership`} busy={busy} onClose={() => setAction(null)}><div className="institutions"><p>Update membership for {action.row.email}? The global account stays available.</p><button disabled={busy} onClick={() => { void run(() => institutionApi(`${base}/memberships/${action.row.membership_id}`, 'PATCH', { status: action.status }), 'Membership updated.').then(ok => { if (ok) setAction(null) }) }}>Confirm</button></div></Modal>}
  </div>
}
