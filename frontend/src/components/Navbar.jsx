import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Navbar({ onMenuClick }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  const initials = user?.name
    ? user.name.split(" ").map((n) => n[0]).slice(0, 2).join("").toUpperCase()
    : "?";

  return (
    <header className="h-16 sticky top-0 z-40 backdrop-blur-xl bg-[#070d1f]/80 border-b border-white/5 px-4 sm:px-6 flex items-center justify-between gap-3">
      <div className="flex items-center gap-2">
        {/* Only below the breakpoint, where the rail is a drawer. On a desktop
            the navigation is already on screen and a button to reveal it would
            be a control that does nothing. */}
        {onMenuClick && (
          <button
            type="button"
            onClick={onMenuClick}
            aria-label="Open navigation menu"
            className="md:hidden p-2 -ml-2 rounded-lg text-brand-muted hover:text-white hover:bg-white/5 transition"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>
        )}

        <Link to="/" className="flex items-center gap-2.5 group">
        <span className="text-red-500 text-2xl drop-shadow-[0_0_10px_rgba(239,68,68,0.8)] group-hover:scale-110 transition-transform">
          ❤
        </span>
          <span className="font-bold text-lg tracking-tight">
            Cardio<span className="text-gradient">Saarthi</span>
          </span>
        </Link>
      </div>

      {user && (
        <div className="flex items-center gap-4">
          <div className="text-right hidden sm:block">
            <p className="text-sm font-semibold leading-tight">{user.name}</p>
            <p className="text-[11px] text-brand-muted uppercase tracking-wider">
              {user.role.toLowerCase()}
            </p>
          </div>
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center text-xs font-bold text-white shadow-lg shadow-blue-500/30">
            {initials}
          </div>
          <button
            onClick={handleLogout}
            className="btn-ghost text-xs !py-2 !px-3"
          >
            Logout
          </button>
        </div>
      )}
    </header>
  );
}