const colorMap = {
  blue:   { bg: "from-blue-500/20 to-blue-500/5",   text: "text-blue-400",   shadow: "shadow-blue-500/20" },
  green:  { bg: "from-emerald-500/20 to-emerald-500/5", text: "text-emerald-400", shadow: "shadow-emerald-500/20" },
  yellow: { bg: "from-amber-500/20 to-amber-500/5",  text: "text-amber-400",  shadow: "shadow-amber-500/20" },
  cyan:   { bg: "from-cyan-500/20 to-cyan-500/5",    text: "text-cyan-400",   shadow: "shadow-cyan-500/20" },
  red:    { bg: "from-red-500/20 to-red-500/5",      text: "text-red-400",    shadow: "shadow-red-500/20" },
};

export default function StatCard({ icon, label, value, sublabel, color = "blue" }) {
  const c = colorMap[color] || colorMap.blue;
  return (
    <div className="card p-5 relative overflow-hidden group hover:-translate-y-1 transition-transform">
      {/* Background glow */}
      <div
        className={`absolute -top-8 -right-8 w-24 h-24 rounded-full bg-gradient-to-br ${c.bg} blur-2xl opacity-0 group-hover:opacity-100 transition-opacity`}
      />
      <div className="relative flex items-start justify-between">
        <div>
          <p className="text-[11px] uppercase tracking-wider text-brand-muted font-semibold">
            {label}
          </p>
          <p className="text-3xl font-extrabold mt-2 tracking-tight">{value}</p>
          {sublabel && (
            <p className="text-[11px] text-brand-muted mt-1">{sublabel}</p>
          )}
        </div>
        <div
          className={`w-10 h-10 rounded-lg bg-gradient-to-br ${c.bg} flex items-center justify-center text-lg ${c.text} shadow-lg ${c.shadow}`}
        >
          {icon}
        </div>
      </div>
    </div>
  );
}