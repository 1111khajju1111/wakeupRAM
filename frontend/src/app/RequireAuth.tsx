import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../store/AuthContext";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();

  if (status === "loading") {
    return (
      <div className="app-loading" role="status">
        Loading
      </div>
    );
  }

  if (status === "unauthenticated") {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
