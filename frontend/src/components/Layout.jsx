import Navbar from "./Navbar";
import Sidebar from "./Sidebar";

export default function Layout({ role, children }) {
  return (
    <div className="min-h-screen bg-transparent">
      <Navbar />
      <div className="flex">
        <Sidebar role={role} />
        <main className="flex-1 p-6 md:p-8 overflow-x-hidden animate-fade-in">
          <div className="max-w-7xl mx-auto">{children}</div>
        </main>
      </div>
    </div>
  );
}