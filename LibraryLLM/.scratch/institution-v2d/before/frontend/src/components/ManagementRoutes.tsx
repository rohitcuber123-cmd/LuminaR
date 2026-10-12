import { Link, Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '../store/useAuthStore'
import { platformAdmin, usePlatformStore } from '../store/usePlatformStore'
import { useInstitutionStore } from '../store/useInstitutionStore'
import { isLibraryStaff, libraryWorkspaceHome } from '../lib/libraryWorkspace'
import { StatePanel } from './WorkspaceUI'

export function PlatformRoute({ children }: { children?: React.ReactNode }) {
  const token = useAuthStore(s => s.token), state = usePlatformStore()
  if (!token) return <Navigate to="/login" replace />
  if (state.session !== token || state.loading) return <StatePanel kind="loading" title="Checking platform permissions…" />
  if (state.error) return <StatePanel kind="error" title="Unable to check platform permissions" action={<button onClick={() => void state.refresh()}>Retry</button>}>{state.error}</StatePanel>
  if (!platformAdmin(state, token)) return <StatePanel kind="error" title="Platform access required" action={<Link to="/account/libraries">My libraries</Link>}>This console requires an explicitly approved platform assignment.</StatePanel>
  return children ? <>{children}</> : <Outlet />
}

/** Compatibility URLs never use remembered contexts or choose from several memberships. */
export function ManagementRedirect({ admin = false }: { admin?: boolean }) {
  const token = useAuthStore(s => s.token), institutions = useInstitutionStore(), platform = usePlatformStore()
  if (institutions.session !== token || institutions.loading || admin && (platform.session !== token || platform.loading)) return <StatePanel kind="loading" title="Checking management access…" />
  if (admin && platformAdmin(platform, token)) return <Navigate to="/platform" replace />
  const memberships = institutions.libraries.filter(isLibraryStaff)
  if (memberships.length === 1) return <Navigate to={libraryWorkspaceHome(memberships[0])} replace />
  if (memberships.length > 1) return <Navigate to="/account/libraries?group=staff" replace />
  return <div className="global-page institutions"><StatePanel kind="error" title="Staff membership required" action={<Link to="/account/libraries">My libraries</Link>}>Your account has no active staff membership. Legacy account roles do not grant library access.</StatePanel></div>
}
