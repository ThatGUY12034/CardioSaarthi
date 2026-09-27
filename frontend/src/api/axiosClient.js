import axios from "axios";

/**
 * A session the demonstration holds without a server.
 *
 * <p>Demo mode issues a token the API has never seen and would reject. That is
 * the point of it: the patient area has no backend yet, so its pages have to be
 * shown from the client alone. Without this the first background request 401s,
 * the interceptor below tears the session down, and the page the demonstrator
 * just opened bounces back to role selection mid-sentence.
 */
export const DEMO_TOKEN_PREFIX = "demo-token-";

export function isDemoSession() {
  try {
    return (localStorage.getItem("cs_token") || "").startsWith(DEMO_TOKEN_PREFIX);
  } catch {
    // Private windows and blocked site data both throw here rather than
    // returning null, and a page that cannot read storage is not a demo.
    return false;
  }
}

const axiosClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8080/api",
  headers: { "Content-Type": "application/json" },
});

axiosClient.interceptors.request.use((config) => {
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
    if (err.response?.status === 401 && !isDemoSession()) {
      localStorage.removeItem("cs_token");
      localStorage.removeItem("cs_user");
      window.location.href = "/";
    }
    return Promise.reject(err);
  }
);

export default axiosClient;
