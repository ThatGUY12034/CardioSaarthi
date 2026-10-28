import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/useAuth";

export default function ProtectedRoute({ allowedRoles }) {
  const { user } = useAuth();

  if (!user) return <Navigate to="/choose-role" replace />;
  if (allowedRoles && !allowedRoles.includes(user.role))
    return <Navigate to="/choose-role" replace />;

  return <Outlet />;
}