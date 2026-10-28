import axios from "axios";

const axiosClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8080/api",
  headers: { "Content-Type": "application/json" },
});

/**
 * Exchanging credentials is the one request that must not carry a token.
 *
 * <p>Attaching the old one locks the user out: the resource-server filter
 * validates any bearer token it is given before the controller runs, so a
 * stale or demo token makes the login itself 401 and the only way back in is
 * to clear browser storage by hand. A session that has expired, or a browser
 * that once visited demo mode, could not sign in at all.
 */
const CARRIES_NO_TOKEN = /\/auth\/login\//;

axiosClient.interceptors.request.use((config) => {
  if (CARRIES_NO_TOKEN.test(config.url || "")) {
    delete config.headers.Authorization;
    return config;
  }
  const token = localStorage.getItem("cs_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

axiosClient.interceptors.response.use(
  (res) => res,
  (err) => {
    // A real 401 means the session is over and the only honest thing is to end
    // it. A demo session has no session to end, and the caller handles the
    // failure itself.
    if (err.response?.status === 401) {
      localStorage.removeItem("cs_token");
      localStorage.removeItem("cs_user");
      window.location.href = "/";
    }
    return Promise.reject(err);
  }
);

export default axiosClient;
