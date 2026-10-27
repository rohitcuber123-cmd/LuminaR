import { LuminarSelect } from '../components/LuminarSelect'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { Modal } from '../components/StaffUI'
import { institutionApi, type Library, type LibraryContext, type Page, type Invitation } from '../lib/institutions'
import { activeLibrary, useInstitutionStore } from '../store/useInstitutionStore'
import { isLibraryStaff, libraryWorkspaceHome, membershipLabel } from '../lib/libraryWorkspace'
import { PageHeading } from '../components/WorkspaceUI'
import { scrollToContentAnchor } from '../lib/paginationScroll'
import { useAuthStore } from '../store/useAuthStore'
import './Staff.css'
import './Institutions.css'

const message = (error: unknown) => error instanceof Error ? error.message : 'Unable to complete this action.'

export function CodeFields({ code, confirm, onCode, onConfirm }: { code: string; confirm: string; onCode: (value: string) => void; onConfirm: (value: string) => void }) {
  return <><label>New Access Code<input type="password" autoComplete="new-password" minLength={8} maxLength={128} required value={code} onChange={e => onCode(e.target.value)} /></label>
    <label>Confirm Access Code<input type="password" autoComplete="new-password" minLength={8} maxLength={128} required value={confirm} onChange={e => onConfirm(e.target.value)} /></label></>
}

export function RegisterLibraryPage() {
  const navigate = useNavigate()
  const [type, setType] = useState('PUBLIC')
  const [code, setCode] = useState(''), [confirm, setConfirm] = useState('')
  const [error, setError] = useState(''), [busy, setBusy] = useState(false)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError('')
    if (type === 'PRIVATE_CODE' && code !== confirm) { setError('Access codes do not match.'); return }
    const fields = new FormData(event.currentTarget)
    setBusy(true)
    try {
      const result = await institutionApi<LibraryContext>('/libraries/register', 'POST', {
        name: fields.get('name'), slug: fields.get('slug'), description: fields.get('description') || null,
        access_mode: type, library_type: type === 'PUBLIC' ? 'PUBLIC_LIBRARY' : 'PRIVATE_INSTITUTION',
        ...(type === 'PRIVATE_CODE' ? { access_code: code } : {}),
        contact_email: fields.get('contact_email') || null, phone: fields.get('phone') || null,
        address: { line1: fields.get('line1') || null, city: fields.get('city') || null, region: fields.get('region') || null, country: fields.get('country') || null },
      })
      setCode(''); setConfirm('')
      await useInstitutionStore.getState().refresh()
      await useInstitutionStore.getState().select(result.library.library_id)
      navigate(libraryWorkspaceHome(activeLibrary(useInstitutionStore.getState())))
    } catch (reason) { setError(message(reason)) } finally { setBusy(false) }
  }
  return <div className="global-page institutions"><PageHeading eyebrow="Libraries" title="Register Your Library" description="Create a library for your community or institution. You become its Owner and Admin." />
    {error && <p className="institution-error" role="alert">{error}</p>}
    <form className="institution-form" onSubmit={submit}>
      <label>Library Name<input name="name" required minLength={2} maxLength={200} /></label>
      <label>Library Slug<input name="slug" required minLength={3} maxLength={80} pattern="[a-zA-Z0-9]+(-[a-zA-Z0-9]+)*" placeholder="central-library" /><small>Use letters, numbers, and hyphens. This appears in your library profile.</small></label>
      <label>Description<textarea name="description" maxLength={2000} /></label>
      <fieldset><legend>Library Access</legend>
        <label className="access-choice"><input type="radio" name="access" aria-label="Public Library" checked={type === 'PUBLIC'} onChange={() => { setType('PUBLIC'); setCode(''); setConfirm('') }} />Public Library<small>Anyone with a LuminaR account can join this library.</small></label>
        <label className="access-choice"><input type="radio" name="access" aria-label="Private Institution" checked={type === 'PRIVATE_CODE'} onChange={() => setType('PRIVATE_CODE')} />Private Institution<small>Members require an institution access code before joining.</small></label>
        {type === 'PRIVATE_CODE' && <><p>Create a separate institution code of 8–128 characters. Passphrases are welcome.</p><CodeFields code={code} confirm={confirm} onCode={setCode} onConfirm={setConfirm} /></>}
      </fieldset>
      <label>Public Contact Email<input type="email" name="contact_email" /></label><label>Phone<input name="phone" maxLength={40} /></label>
      <label>Address<input name="line1" maxLength={200} /></label><div className="institution-grid"><label>City<input name="city" maxLength={100} /></label><label>Region<input name="region" maxLength={100} /></label><label>Country<input name="country" maxLength={100} /></label></div>
      <button disabled={busy}>{busy ? 'Registering…' : 'Register Library'}</button>
    </form></div>
}

export function ExploreLibrariesPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState(''), [search, setSearch] = useState(''), [kind, setKind] = useState('all'), [page, setPage] = useState(0)
  const [data, setData] = useState<Page<Library>>({ results: [] }), [loading, setLoading] = useState(true)
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [revision, setRevision] = useState(0)
  const [joining, setJoining] = useState<Library | null>(null), [code, setCode] = useState(''), [joinError, setJoinError] = useState('')
  const activeId = useInstitutionStore(s => s.activeId)
  useEffect(() => {
    const controller = new AbortController(); let alive = true
    async function load() {
      setLoading(true); setError(''); setData({ results: [] })
      await institutionApi<Page<Library>>(`/libraries?kind=${kind}&search=${encodeURIComponent(search)}&offset=${page * 20}&limit=20`, 'GET', undefined, controller.signal)
      .then(result => { if (alive) setData(result) }).catch(reason => { if (alive) setError(message(reason)) }).finally(() => { if (alive) setLoading(false) })
    }
    void load()
    return () => { alive = false; controller.abort() }
  }, [kind, search, page, revision, activeId])
  async function enter(library: Library, accessCode?: string) {
    setBusy(true); setJoinError(''); setError('')
    try {
      if (!library.membership) await institutionApi<LibraryContext>(`/libraries/${library.library_id}/join`, 'POST', accessCode === undefined ? {} : { access_code: accessCode })
      await useInstitutionStore.getState().refresh()
      await useInstitutionStore.getState().select(library.library_id)
      setJoining(null); setCode(''); navigate(libraryWorkspaceHome(activeLibrary(useInstitutionStore.getState())))
    } catch (reason) { if (joining) setJoinError(message(reason)); else setError(message(reason)) } finally { setBusy(false) }
  }
  return <div className="global-page institutions"><PageHeading eyebrow="Libraries" title="Explore Libraries" description="Find a public library or join your institution." actions={<><Link className="ui-button ui-secondary" to="/account/libraries">My libraries</Link><Link className="ui-button" to="/libraries/register">Register Your Library</Link></>} />
    <form className="institution-toolbar" onSubmit={e => { e.preventDefault(); setPage(0); setSearch(query.trim()) }}><input aria-label="Search libraries" placeholder="Name, slug, city, or region" maxLength={100} value={query} onChange={e => setQuery(e.target.value)} />
      <LuminarSelect aria-label="Library filter" value={kind} onChange={e => { setKind(e.target.value); setPage(0) }}><option value="all">All Libraries</option><option value="public">Public</option><option value="private">Private Institutions</option><option value="mine">My Libraries</option></LuminarSelect><button>Search</button></form>
    {error && <p className="institution-error" role="alert">{error} <button onClick={() => setRevision(r => r + 1)}>Retry</button></p>}
    {loading ? <p role="status">Loading libraries…</p> : <><p>{data.total ?? 0} libraries found</p><div className="institution-grid">{data.results.map(library => <article className="institution-card" key={library.library_id}>
      <span className="institution-badge">{library.access_mode === 'PUBLIC' ? 'PUBLIC' : 'PRIVATE'}</span><h2>{library.name}</h2><p>{library.description || 'Welcome to this library.'}</p>
      <p>{[library.address?.city, library.address?.region].filter(Boolean).join(', ')}</p>
      {library.membership && <p>{library.membership.status} · {membershipLabel(library)}</p>}
      <button disabled={busy || (!!library.membership && library.membership.status !== 'ACTIVE')} onClick={() => {
        if (!library.membership && library.access_mode === 'PRIVATE_CODE') { setJoining(library); setCode(''); setJoinError('') }
        else void enter(library)
      }}>{library.membership?.status === 'ACTIVE' ? isLibraryStaff(library) ? 'Open Staff Workspace' : 'Open Library' : library.membership ? 'Contact library staff' : library.access_mode === 'PUBLIC' ? 'Join Library' : 'Enter Access Code'}</button>
    </article>)}</div><div className="institution-actions"><button className="secondary" disabled={page === 0 || loading} onClick={() => { setPage(p => p - 1); requestAnimationFrame(() => scrollToContentAnchor('.institution-grid, .institutions')) }}>Previous</button><span>Page {page + 1}</span><button className="secondary" disabled={!data.has_more || loading} onClick={() => { setPage(p => p + 1); requestAnimationFrame(() => scrollToContentAnchor('.institution-grid, .institutions')) }}>Next</button></div></>}
    {joining && <Modal title={`Join ${joining.name}`} busy={busy} onClose={() => { setJoining(null); setCode('') }}><div className="institutions"><p>Enter your institution access code to join as a member.</p>
      <form className="institution-form" onSubmit={e => { e.preventDefault(); void enter(joining, code) }}><label>Institution Access Code<input autoFocus type="password" autoComplete="off" maxLength={128} required value={code} onChange={e => setCode(e.target.value)} /></label>
        {joinError && <p role="alert" className="institution-error">{joinError}</p>}<button disabled={busy}>{busy ? 'Joining…' : 'Join Library'}</button></form></div></Modal>}
  </div>
}

export function PendingInvitationsPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<Page<Invitation>>({ results: [] }), [page, setPage] = useState(0), [revision, setRevision] = useState(0)
  const [error, setError] = useState(''), [busy, setBusy] = useState(false)
  useEffect(() => { let alive = true; institutionApi<Page<Invitation>>(`/me/invitations?offset=${page * 20}`).then(r => { if (alive) setData(r) }).catch(e => { if (alive) setError(message(e)) }); return () => { alive = false } }, [page, revision])
  async function respond(row: Invitation, action: string) {
    setBusy(true); setError('')
    try {
      const result = await institutionApi<LibraryContext>(`/invitations/${row.invitation_id}/${action}`, 'POST', {})
      await useInstitutionStore.getState().refresh(); setRevision(r => r + 1)
      if (action === 'accept') {
        const library = await useInstitutionStore.getState().select(result.library?.library_id || row.library_id)
        if (library) navigate(libraryWorkspaceHome(library))
      }
    }
    catch (reason) { setError(message(reason)) } finally { setBusy(false) }
  }
  return <div className="global-page institutions"><PageHeading eyebrow="My account" title="Pending Invitations" description="Accept a staff invitation using the account with the invited email address." />{error && <p role="alert" className="institution-error">{error}</p>}
    <div className="institution-grid">{data.results.map(row => <article className="institution-card" key={row.invitation_id}><h2>{row.library_name}</h2><p>{row.role} · {row.email_normalized}</p><p>Expires {new Date(row.expires_at).toLocaleString()}</p>
      {row.requires_token ? <p>Open the invitation link supplied by library staff.</p> : <div className="institution-actions"><button disabled={busy} onClick={() => void respond(row, 'accept')}>Accept</button><button className="secondary" disabled={busy} onClick={() => void respond(row, 'decline')}>Decline</button></div>}
    </article>)}</div>{!data.results.length && <p>No pending invitations.</p>}<div className="institution-actions"><button disabled={page === 0} onClick={() => { setPage(p => p - 1); requestAnimationFrame(() => scrollToContentAnchor('.institution-grid, .institutions')) }}>Previous</button><button disabled={(page + 1) * 20 >= (data.total ?? 0)} onClick={() => { setPage(p => p + 1); requestAnimationFrame(() => scrollToContentAnchor('.institution-grid, .institutions')) }}>Next</button></div><p><Link to="/libraries">Explore Libraries</Link></p></div>
}

export function InvitationPage() {
  const { invitationId } = useParams(), location = useLocation(), navigate = useNavigate()
  const authenticated = useAuthStore(s => s.isAuthenticated)
  const [token, setToken] = useState(() => new URLSearchParams(location.hash.slice(1)).get('token'))
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [done, setDone] = useState(false)
  useEffect(() => { window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search) }, [])
  async function respond(action: string) {
    setBusy(true); setError('')
    try {
      const result = await institutionApi<LibraryContext>(`/invitations/${invitationId}/${action}`, 'POST', { ...(token ? { token } : {}) })
      setToken(null); setDone(true); await useInstitutionStore.getState().refresh()
      if (action === 'accept') {
        const library = await useInstitutionStore.getState().select(result.library.library_id)
        if (library) navigate(libraryWorkspaceHome(library))
      }
    } catch (reason) { setError(message(reason)) } finally { setBusy(false) }
  }
  return <div className="global-page institutions"><PageHeading eyebrow="My account" title="Library Staff Invitation" description="Sign in with the invited, verified email address to accept this invitation." />
    {error && <p role="alert" className="institution-error">{error}</p>}{done ? <p>Invitation declined.</p> : authenticated ? <div className="institution-actions"><button disabled={busy} onClick={() => void respond('accept')}>Accept Invitation</button><button disabled={busy} className="secondary" onClick={() => void respond('decline')}>Decline</button></div> : <><Link to="/login" state={{ from: { pathname: location.pathname, hash: token ? '#token=' + encodeURIComponent(token) : '' } }}>Sign in to accept</Link><p>Need an account? <Link to="/signup">Create an account</Link>, verify your email, then reopen the invitation link.</p></>}
  </div>
}
