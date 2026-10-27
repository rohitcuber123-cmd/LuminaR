import { useEffect, useState } from 'react'
import { Link, Navigate, useLocation, useParams } from 'react-router-dom'
import { platformAdmin, usePlatformStore } from '../store/usePlatformStore'
import { useAuthStore } from '../store/useAuthStore'
import { activeLibrary, patronLibrary, staffLibrary, useInstitutionStore } from '../store/useInstitutionStore'
import { isLibraryStaff, libraryRole, libraryWorkspaceHome, patronPath, staffPath, type LibraryWorkspace } from '../lib/libraryWorkspace'
import { StatePanel } from './WorkspaceUI'

/** Resolve the URL's tenant through the server before mounting any tenant view. */
export function WorkspaceRoute({ staff = false, children }: { staff?: boolean; children: React.ReactNode }) {
  const { libraryId = '' } = useParams(), token = useAuthStore(s => s.token)
  const state = useInstitutionStore(), library = state.libraries.find(l => l.library_id === libraryId)
  const { session, loading, select } = state
  const [checked, setChecked] = useState(''), [error, setError] = useState(''), [attempt, setAttempt] = useState(0)
  useEffect(() => {
    if (!token || session !== token || loading) return
    let alive = true
    const key = `${token}:${libraryId}`
    void select(libraryId).then(row => { if (alive && row) { setChecked(key); setError('') } }).catch(reason => { if (alive) setError(reason instanceof Error ? reason.message : 'Unable to open this library.') })
    return () => { alive = false }
  }, [libraryId, token, session, loading, select, attempt])
  if (error) return <div className="global-page institutions"><StatePanel title="Unable to open this library" kind="error" action={<><button onClick={() => { setError(''); setAttempt(v => v + 1) }}>Retry</button><Link to="/account/libraries">My libraries</Link></>}>{error}</StatePanel></div>
  if (token && state.session===token && !loading && checked===`${token}:${libraryId}` && !library)
    return <div className="global-page institutions"><StatePanel title="Unable to open this library" kind="error" action={<Link to="/account/libraries">My libraries</Link>}>Current membership is required.</StatePanel></div>
  if (!token || state.session !== token || checked !== `${token}:${libraryId}` || !library || state.activeId !== libraryId) return <div className="global-page institutions"><StatePanel title="Loading library permissions…" kind="loading">Checking your current membership.</StatePanel></div>
  if (!libraryRole(library)) return <Navigate to="/account/libraries" replace />
  if (staff !== isLibraryStaff(library)) return <Navigate to={libraryWorkspaceHome(library)} replace />
  return <>{children}</>
}
export function AdminLibraryRoute({ children }: { children: React.ReactNode }) {
  const library = useInstitutionStore(activeLibrary)
  return libraryRole(library) === 'ADMIN' ? <>{children}</> : <Navigate to={libraryWorkspaceHome(library)} replace />
}
export function LegacyWorkspaceRedirect({ mode, section = '' }: { mode?: LibraryWorkspace; section?: string }) {
  const state = useInstitutionStore(), token = useAuthStore(s => s.token)
  if (state.session !== token || state.loading) return <StatePanel title="Loading library permissions…" kind="loading" />
  const desired = mode === 'PATRON' ? patronLibrary(state) : mode === 'STAFF' ? staffLibrary(state) : activeLibrary(state)
  const candidates = state.libraries.filter(l => mode === 'PATRON' ? libraryRole(l) === 'GENERAL_USER' : mode === 'STAFF' ? isLibraryStaff(l) : !!libraryRole(l))
  const library = desired || (candidates.length === 1 ? candidates[0] : null)
  if (library) return <Navigate to={isLibraryStaff(library) ? staffPath(library.library_id, section) : patronPath(library.library_id, section === 'inventory' ? 'catalogue' : section)} replace />
  return <Navigate to="/account/libraries" replace />
}
export function AccountLanding() {
  const state = useInstitutionStore(), token = useAuthStore(s => s.token), platform = usePlatformStore()
  const location=useLocation(),requested=new URLSearchParams(location.search).get('return_to') || ''
  if (state.session !== token || state.loading) return <StatePanel title="Loading your libraries…" kind="loading" />
  const libraries = state.libraries.filter(l => !!libraryRole(l))
  const route=requested.match(/^\/(staff\/)?libraries\/([0-9a-f-]{36})(?:[/?#]|$)/i)
  const current=route && libraries.find(l=>l.library_id===route[2])
  if(current) return <Navigate to={!!route[1]===isLibraryStaff(current) ? requested : libraryWorkspaceHome(current)} replace />
  if (!libraries.length && (platform.session !== token || platform.loading)) return <StatePanel title="Checking platform permissions…" kind="loading" />
  if (!libraries.length && platformAdmin(platform, token)) return <Navigate to="/platform" replace />
  return <Navigate to={libraries.length === 1 ? libraryWorkspaceHome(libraries[0]) : libraries.length ? '/account/libraries' : '/'} replace />
}
