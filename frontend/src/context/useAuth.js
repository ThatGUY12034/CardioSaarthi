import { useContext } from "react";
import { AuthContext } from "./authContext";

/** Whoever is signed in, and the two ways to change that. */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
