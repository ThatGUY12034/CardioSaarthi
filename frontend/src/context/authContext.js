import { createContext } from "react";

/**
 * The context object on its own, away from the component that provides it.
 *
 * <p>Three things used to live in one file: this, the provider and the hook.
 * React Fast Refresh can only swap a module that exports components and
 * nothing else, so every edit to the auth file replaced the context with a new
 * object while the mounted tree still held the old one, and the application
 * fell over with "useAuth must be used inside AuthProvider" until somebody
 * reloaded by hand. Splitting them is the fix the lint rule was asking for.
 */
export const AuthContext = createContext(null);
