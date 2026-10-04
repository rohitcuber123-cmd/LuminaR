import { Navigate } from "react-router-dom";
import { useAuthStore } from "../store/useAuthStore";

/**
 * @deprecated ReaderDashboard has been superseded by My Library (/profile).
 * This component provides safe backward compatibility by redirecting to the appropriate role home.
 */
export function ReaderDashboard() {
  const user = useAuthStore((s) => s.user);
  const dest =
    user?.role === "ADMIN"
      ? "/admin"
      : user?.role === "LIBRARIAN"
        ? "/librarian"
        : "/profile";
  return <Navigate to={dest} replace />;
}
