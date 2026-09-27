import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { role } = useParams();
  const navigate = useNavigate();
  const { login, mockLogin } = useAuth();
  const [mode, setMode] = useState("college");
  const [form, setForm] = useState({ collegeId: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const roleLabel = role.charAt(0).toUpperCase() + role.slice(1);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const credentials =
        mode === "college"
          ? { collegeId: form.collegeId, password: form.password, mode: "college" }
          : { email: form.email, password: form.password, mode: "email" };
      const user = await login(role, credentials);
      navigate(`/${user.role.toLowerCase()}/dashboard`);
    } catch (err) {
      setError(err.response?.data?.message || "Login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleDemo = () => {
  try {
    const demoUser = mockLogin(role);
    // Explicit routing per role (more reliable than string manipulation)
    const routes = {
      STUDENT: "/student/dashboard",
      FACULTY: "/faculty/dashboard",
      PATIENT: "/patient/dashboard",
      ADMIN: "/admin/dashboard",
    };
    const target = routes[demoUser.role] || "/student/dashboard";
    navigate(target, { replace: true });
  } catch (err) {
    console.error("Demo login failed:", err);
    setError("Demo mode failed. Please try again.");
  }
};

  return (
    <div className="min-h-screen grid md:grid-cols-2">
      {/* LEFT — decorative */}
      <div className="hidden md:flex items-center justify-center relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-900/20 via-transparent to-cyan-900/10" />
        <div className="absolute w-[400px] h-[400px] rounded-full bg-blue-500/10 blur-[100px]" />
        <div className="relative text-[260px] opacity-40 animate-float drop-shadow-[0_0_60px_rgba(239,68,68,0.5)]">
          🫀
        </div>
        <svg
          className="absolute bottom-16 w-full h-24 pointer-events-none"
          viewBox="0 0 1000 100"
          fill="none"
        >
          <path
            d="M0 50 L200 50 L220 20 L240 80 L260 30 L280 60 L300 50 L1000 50"
            stroke="#22d3ee"
            strokeWidth="1.5"
            className="drop-shadow-[0_0_8px_rgba(34,211,238,0.8)]"
          />
        </svg>
      </div>

      {/* RIGHT — form */}
      <div className="flex items-center justify-center p-8">
        <div className="w-full max-w-md animate-fade-in-up">
          <div className="flex items-center gap-2 mb-10">
            <span className="text-red-500 text-2xl drop-shadow-[0_0_10px_rgba(239,68,68,0.8)]">❤</span>
            <span className="font-bold text-lg tracking-tight">
              Cardio<span className="text-gradient">Saarthi</span>
            </span>
          </div>

          <h2 className="text-3xl font-extrabold tracking-tight">{roleLabel} Login</h2>
          <p className="text-brand-muted mt-2 text-sm">
            {role === "student" && "Your journey to better ECG interpretation starts here."}
            {role === "faculty" && "Review cases, monitor students, and manage content."}
            {role === "patient" && "Understand your ECG report in simple language."}
          </p>

          {/* Tabs */}
          <div className="flex bg-brand-card/60 border border-white/5 rounded-lg p-1 mt-8 backdrop-blur">
            {["college", "email"].map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={`flex-1 py-2 rounded-md text-sm font-medium transition-all ${
                  mode === m
                    ? "bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/30"
                    : "text-brand-muted hover:text-white"
                }`}
              >
                {m === "college" ? "College Login" : "Email Login"}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            {mode === "college" ? (
              <div>
                <label className="text-xs text-brand-muted font-medium">College ID</label>
                <input
                  className="input-field mt-1.5"
                  placeholder="e.g. TE18/2023/C5001"
                  value={form.collegeId}
                  onChange={(e) => setForm({ ...form, collegeId: e.target.value })}
                  required
                />
              </div>
            ) : (
              <div>
                <label className="text-xs text-brand-muted font-medium">College Email</label>
                <input
                  type="email"
                  className="input-field mt-1.5"
                  placeholder="you@college.edu"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  required
                />
              </div>
            )}

            <div>
              <label className="text-xs text-brand-muted font-medium">Password</label>
              <input
                type="password"
                className="input-field mt-1.5"
                placeholder="••••••••"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                required
              />
            </div>

            {error && (
              <p className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading ? "Logging in..." : "Login"}
            </button>

            <button type="button" onClick={handleDemo} className="btn-ghost w-full text-sm">
              Skip — Enter Demo Mode
            </button>
          </form>

          <p className="text-xs text-brand-muted text-center mt-6">
            Don't have an account? Contact your faculty.
          </p>
        </div>
      </div>
    </div>
  );
}