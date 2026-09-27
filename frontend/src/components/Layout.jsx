import { useState } from "react";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";

/**
 * The shell every signed-in page sits in.
 *
 * <p>Holds the one piece of state the navigation needs: whether the drawer is
 * open. It lives here rather than in the sidebar because the button that opens
 * it is in the header, and two siblings cannot share state between themselves.
 */
export default function Layout({ role, children }) {
  const [navOpen, setNavOpen] = useState(false);

  return (
    <div className="min-h-screen bg-transparent">
      {/* First thing a keyboard reaches on every page. Someone tabbing through
          should not have to walk the whole menu to get to the content. */}
      <a href="#main" className="skip-link">
        Skip to content
      </a>

      <Navbar onMenuClick={() => setNavOpen(true)} />

      <div className="flex">
        <Sidebar role={role} open={navOpen} onClose={() => setNavOpen(false)} />
        <main
          id="main"
          tabIndex={-1}
          className="flex-1 p-4 sm:p-6 md:p-8 overflow-x-hidden animate-fade-in"
        >
          <div className="max-w-7xl mx-auto">{children}</div>
        </main>
      </div>
    </div>
  );
}
