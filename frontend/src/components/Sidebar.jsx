import { useEffect, useRef } from "react";
import { NavLink, useLocation } from "react-router-dom";

const studentLinks = [
  { to: "/student/dashboard", label: "Dashboard", icon: "◈" },
  { to: "/student/cases", label: "Practice Cases", icon: "◇" },
  { to: "/student/progress", label: "Progress", icon: "◇" },
  { to: "/student/leaderboard", label: "Leaderboard", icon: "◇" },
];

const facultyLinks = [
  { to: "/faculty/dashboard", label: "Dashboard", icon: "◈" },
  { to: "/faculty/students", label: "Students", icon: "◇" },
  { to: "/faculty/review", label: "Review Queue", icon: "◇" },
  { to: "/faculty/approvals", label: "Case Approval", icon: "◇" },
];

const patientLinks = [
  { to: "/patient/dashboard", label: "Dashboard", icon: "◈" },
  { to: "/patient/upload", label: "Upload Report", icon: "◇" },
  { to: "/patient/glossary", label: "Learn", icon: "◇" },
];

const adminLinks = [
  { to: "/admin/dashboard", label: "Dashboard", icon: "◈" },
  { to: "/admin/users", label: "Users", icon: "◇" },
  { to: "/admin/cases", label: "Cases", icon: "◇" },
];

const linkMap = {
  STUDENT: studentLinks,
  FACULTY: facultyLinks,
  PATIENT: patientLinks,
  ADMIN: adminLinks,
};

/**
 * The navigation, as a rail on a desktop and a drawer on a phone.
 *
 * <p>It used to be `hidden md:flex`, which on a phone meant no navigation at
 * all: a student could reach whatever page they landed on and could not leave
 * it. Below the breakpoint the same links now open over the page.
 */
export default function Sidebar({ role, open = false, onClose }) {
  const links = linkMap[role] || [];
  const location = useLocation();
  const panel = useRef(null);

  // Following a link should close the drawer. Without this the destination
  // renders underneath a menu that is still covering it.
  useEffect(() => {
    if (open) onClose?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  // Escape closes it, as it does every other overlay on the web.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKey);
    // Focus moves into the drawer so the keyboard follows the eye.
    panel.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      {/* The scrim. Tapping outside a drawer is how a drawer is dismissed. */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        ref={panel}
        tabIndex={-1}
        aria-label="Main navigation"
        aria-hidden={!open ? undefined : false}
        className={`w-64 shrink-0 flex-col border-r border-white/5 bg-[#0a1128]/95 md:bg-[#0a1128]/60 backdrop-blur-xl
          fixed inset-y-0 left-0 z-40 transition-transform duration-200 md:transition-none
          ${open ? "flex translate-x-0" : "hidden -translate-x-full"}
          md:static md:flex md:translate-x-0`}
      >
      <div className="p-5">
        <p className="text-[10px] uppercase tracking-[0.15em] text-brand-muted font-semibold px-3 mb-3">
          Menu
        </p>
        <nav className="space-y-1">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              className={({ isActive }) =>
                `group relative flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? "bg-gradient-to-r from-blue-500/15 to-cyan-500/5 text-white border border-blue-500/30 shadow-lg shadow-blue-500/10"
                    : "text-brand-muted hover:text-white hover:bg-white/5 border border-transparent"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 rounded-r-full bg-gradient-to-b from-blue-400 to-cyan-400 shadow-[0_0_10px_#60a5fa]" />
                  )}
                  <span
                    className={`text-base transition-colors ${
                      isActive ? "text-cyan-400" : "text-brand-muted group-hover:text-blue-400"
                    }`}
                  >
                    {l.icon}
                  </span>
                  <span>{l.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="mt-auto p-5">
        <div className="card card-glow p-4">
          <p className="text-xs font-semibold text-white">Need help?</p>
          <p className="text-[11px] text-brand-muted mt-1 leading-relaxed">
            Contact your faculty or check the user guide.
          </p>
        </div>
      </div>
      </aside>
    </>
  );
}