import { useState } from "react";
import axiosClient from "../api/axiosClient";
import { AuthContext } from "./authContext";

/**
 * Whoever was signed in when the tab was last closed.
 *
 * Read once, as this state's initial value, rather than in an effect that then
 * calls setState: an effect runs after the first paint, so the guarded routes
 * saw no user, bounced to the role chooser, and only then learned there was a
 * session. Reloading a dashboard threw you out of it.
 */
function signedInLastTime() {
  try {
    const stored = localStorage.getItem("cs_user");
    return stored ? JSON.parse(stored) : null;
  } catch {
    // Unparseable is the same as absent, and keeping it would fail again.
    localStorage.removeItem("cs_user");
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(signedInLastTime);

  /**
   * The only way into the application.
   *
   * There used to be a second one: a "demo mode" that built a user object in
   * the browser and wrote a token the server had never issued. It let anyone
   * reach a faculty dashboard without authenticating, and because the token was
   * not a JWT every request behind it failed, so what it actually showed was an
   * empty console under a fabricated name.
   */
  const login = async (role, credentials) => {
    const { data } = await axiosClient.post(
      `/auth/login/${String(role).toLowerCase()}`,
      credentials
    );
    localStorage.setItem("cs_token", data.token);
    localStorage.setItem("cs_user", JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem("cs_token");
    localStorage.removeItem("cs_user");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
