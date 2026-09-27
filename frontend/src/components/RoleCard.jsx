import { useNavigate } from "react-router-dom";

export default function RoleCard({ icon, title, subtitle, role, gradient, accentColor }) {
  const navigate = useNavigate();
  return (
    <button
      onClick={() => navigate(`/login/${role.toLowerCase()}`)}
      className={`group relative overflow-hidden rounded-2xl p-8 text-left transition-all hover:-translate-y-2 backdrop-blur-md ${gradient}`}
    >
      {/* Glow on hover */}
      <div className="absolute -top-16 -right-16 w-40 h-40 rounded-full bg-white/5 blur-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

      <div className={`relative text-5xl mb-8 ${accentColor} drop-shadow-[0_0_15px_currentColor]`}>
        {icon}
      </div>
      <h3 className="relative text-xl font-bold text-white">{title}</h3>
      <p className="relative text-sm text-white/60 mt-1.5">{subtitle}</p>

      <div
        className={`relative mt-7 w-11 h-11 rounded-full bg-white/10 flex items-center justify-center text-white group-hover:bg-white/20 group-hover:translate-x-1 transition-all ${accentColor}`}
      >
        →
      </div>
    </button>
  );
}