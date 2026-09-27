import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Loader from "./Loader";

export default function ProtectedRoute({ allowedRoles }) {
  const { user, loading } = useAuth();

  if (loading) return <Loader />;
  if (!user) return <Navigate to="/choose-role" replace />;
  if (allowedRoles && !allowedRoles.includes(user.role))
    return <Navigate to="/choose-role" replace />;

  return <Outlet />;
}