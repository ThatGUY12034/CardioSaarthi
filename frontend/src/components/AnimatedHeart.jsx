export default function AnimatedHeart() {
  return (
    <div className="relative w-full h-[420px] flex items-center justify-center overflow-hidden">
      {/* Radial glow behind heart */}
      <div className="absolute w-[400px] h-[400px] rounded-full bg-red-500/20 blur-[100px] animate-pulse-glow" />
      <div className="absolute w-[280px] h-[280px] rounded-full bg-blue-500/10 blur-[80px]" />

      {/* The heart */}
      <div className="relative text-[220px] animate-float select-none drop-shadow-[0_0_60px_rgba(239,68,68,0.6)]">
        🫀
      </div>

      {/* Animated ECG line */}
      <svg
        className="absolute bottom-6 left-0 w-full h-32 pointer-events-none"
        viewBox="0 0 1000 120"
        fill="none"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="ecgGrad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#22d3ee" stopOpacity="0" />
            <stop offset="20%" stopColor="#22d3ee" />
            <stop offset="80%" stopColor="#60a5fa" />
            <stop offset="100%" stopColor="#60a5fa" stopOpacity="0" />
          </linearGradient>
          <filter id="ecgGlow">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <path
          d="M0 60 L180 60 L200 60 L210 30 L220 90 L235 15 L250 105 L265 45 L280 60 L320 60
             L500 60 L520 60 L530 30 L540 90 L555 15 L570 105 L585 45 L600 60 L640 60
             L820 60 L840 60 L850 30 L860 90 L875 15 L890 105 L905 45 L920 60 L1000 60"
          stroke="url(#ecgGrad)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          filter="url(#ecgGlow)"
          strokeDasharray="1200"
          style={{ animation: "drawLine 3s ease-out infinite" }}
        />
      </svg>

      {/* Floating particles */}
      <div className="absolute top-8 left-12 w-1.5 h-1.5 rounded-full bg-cyan-400 shadow-[0_0_12px_#22d3ee] animate-float" />
      <div className="absolute top-20 right-16 w-1 h-1 rounded-full bg-blue-400 shadow-[0_0_10px_#60a5fa] animate-float" style={{ animationDelay: "0.5s" }} />
      <div className="absolute bottom-24 left-24 w-1 h-1 rounded-full bg-red-400 shadow-[0_0_10px_#ef4444] animate-float" style={{ animationDelay: "1s" }} />
    </div>
  );
}