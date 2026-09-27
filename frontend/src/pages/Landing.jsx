import { Link } from "react-router-dom";
import AnimatedHeart from "../components/AnimatedHeart";

export default function Landing() {
  return (
    <div className="min-h-screen bg-transparent">
      {/* NAVBAR */}
      <nav className="flex items-center justify-between px-8 py-5 backdrop-blur-md bg-transparent">
        <div className="flex items-center gap-2.5">
          <span className="text-red-500 text-2xl drop-shadow-[0_0_10px_rgba(239,68,68,0.8)]">❤</span>
          <span className="font-bold text-lg tracking-tight">
            ECG<span className="text-gradient">.learn</span>
          </span>
        </div>
        <div className="hidden md:flex gap-8 text-sm text-brand-muted">
          <a href="#" className="hover:text-white transition-colors">Home</a>
          <a href="#" className="hover:text-white transition-colors">About</a>
          <a href="#" className="hover:text-white transition-colors">Features</a>
        </div>
        <Link to="/choose-role" className="btn-primary text-sm">
          Get Started →
        </Link>
      </nav>

      {/* HERO */}
      <div className="grid md:grid-cols-2 gap-8 px-8 md:px-20 py-14 items-center">
        <div className="animate-fade-in-up">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-xs text-blue-300 mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
            AI-Powered ECG Learning Platform
          </div>

          <h1 className="text-5xl md:text-6xl font-extrabold leading-[1.05] tracking-tight">
            Learn. Practice.<br />
            <span className="text-gradient">Understand ECG.</span>
          </h1>

          <p className="text-brand-muted mt-6 max-w-lg text-[15px] leading-relaxed">
            A platform for students, faculty and patients to learn, analyze and
            understand ECGs — simpler, smarter, together.
          </p>

          <div className="flex gap-3 mt-9">
            <Link to="/choose-role" className="btn-primary">
              Get Started →
            </Link>
            <button className="btn-ghost">Learn More</button>
          </div>
        </div>

        <div className="animate-fade-in delay-200">
          <AnimatedHeart />
        </div>
      </div>

      {/* FEATURE STRIP */}
      <div className="grid md:grid-cols-3 gap-6 px-8 md:px-20 pb-20 mt-4">
        {[
          { icon: "📘", title: "Learn", desc: "Interactive cases & explanations", color: "from-blue-500/20 to-blue-500/5", text: "text-blue-400" },
          { icon: "📊", title: "Track", desc: "Monitor progress & performance", color: "from-cyan-500/20 to-cyan-500/5", text: "text-cyan-400" },
          { icon: "🏆", title: "Improve", desc: "Build confidence with real-world ECGs", color: "from-emerald-500/20 to-emerald-500/5", text: "text-emerald-400" },
        ].map((f, i) => (
          <div
            key={f.title}
            className={`card p-6 animate-fade-in-up delay-${(i + 1) * 100} hover:-translate-y-1 transition-transform`}
          >
            <div
              className={`w-12 h-12 rounded-xl bg-gradient-to-br ${f.color} flex items-center justify-center text-2xl ${f.text} mb-4`}
            >
              {f.icon}
            </div>
            <h3 className="font-semibold text-lg">{f.title}</h3>
            <p className="text-sm text-brand-muted mt-1">{f.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}