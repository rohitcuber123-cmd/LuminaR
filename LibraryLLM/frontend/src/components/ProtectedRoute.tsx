import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore, type UserRole } from '../store/useAuthStore'
import { activeLibrary, useInstitutionStore } from '../store/useInstitutionStore'
import { libraryRole, libraryWorkspaceHome } from '../lib/libraryWorkspace'
import { StatePanel } from './WorkspaceUI'

export default function ProtectedRoute({ libraryRoles, children }: { libraryRoles?: UserRole[]; children?: React.ReactNode }) {
  const location = useLocation(), { isAuthenticated, token } = useAuthStore(), state = useInstitutionStore()
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location }} />
  if (libraryRoles) {
    if (state.session !== token || state.loading) return <StatePanel kind="loading" title="Checking library permissions…" />
    const library = activeLibrary(state), role = libraryRole(library)
    if (!role) return <Navigate to="/account/libraries" replace />
    if (!libraryRoles.includes(role)) return <Navigate to={libraryWorkspaceHome(library)} replace />
  }
  return children ? <>{children}</> : <Outlet />
}
