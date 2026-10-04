import {
  Navigate,
  Outlet,
  useLocation,
} from 'react-router-dom'

import {
  useAuthStore,
  type UserRole,
} from '../store/useAuthStore'


interface ProtectedRouteProps {

  allowedRoles?: UserRole[]

  children?: React.ReactNode
}


export default function ProtectedRoute({
  allowedRoles,
  children,
}: ProtectedRouteProps) {

  const location =
    useLocation()


  const {
    isAuthenticated,
    user,
  } =
    useAuthStore()


  // ==========================================================
  // NOT LOGGED IN
  // ==========================================================

  if (!isAuthenticated) {

    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: location,
        }}
      />
    )
  }


  // ==========================================================
  // ROLE CHECK
  // ==========================================================

  if (
    allowedRoles &&
    allowedRoles.length > 0
  ) {

    const role =
      user?.role


    if (
      !role ||
      !allowedRoles.includes(role)
    ) {

      return (
        <Navigate
          to="/"
          replace
        />
      )
    }
  }


  // ==========================================================
  // RENDER
  // ==========================================================

  if (children) {

    return <>{children}</>
  }


  return <Outlet />
}