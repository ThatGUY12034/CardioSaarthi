import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../../components/Navbar";
import Sidebar from "../../components/Sidebar";
import StatCard from "../../components/StatCard";
import CaseEcg from "../../components/CaseEcg";
import axiosClient from "../../api/axiosClient";
import { useAuth } from "../../context/AuthContext";

export default function StudentDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState({ totalCases: 12, completed: 5, streak: 3, avgScore: 78 });
  const [continueCase, setContinueCase] = useState(null);
  const [recent, setRecent] = useState([]);

  useEffect(() => {
    // Replace with real API: axiosClient.get('/student/dashboard')
    setContinueCase({ id: 6, title: "Case 6 - Sinus Bradycardia", difficulty: "Medium" });
    setRecent([
      { id: 5, title: "Completed Case 5", time: "2 hours ago", icon: "✅" },
      { id: 4, title: "Score 80% in Case 4", time: "1 day ago", icon: "🎯" },
      { id: 1, title: "Started Case 6", time: "1 day ago", icon: "▶" },
    ]);
  }, []);

  return (
    <div className="min-h-screen bg-brand-bg">
      <Navbar />
      <div className="flex">
        <Sidebar role="STUDENT" />
        <main className="flex-1 p-8">
          <h1 className="text-3xl font-bold">Good Morning, {user?.name?.split(" ")[0] || "Saniya"}! 👋</h1>
          <p className="text-brand-muted mt-1">Keep learning, one beat at a time.</p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mt-8">
            <StatCard icon="🩺" label="Total Cases" value={stats.totalCases} />
            <StatCard icon="✅" label="Completed" value={stats.completed} color="brand-success" />
            <StatCard icon="🔥" label="Current Streak" value={`${stats.streak} days`} color="brand-warning" />
            <StatCard icon="📊" label="Average Score" value={`${stats.avgScore}%`} color="brand-accent" />
          </div>

          <div className="grid md:grid-cols-2 gap-6 mt-8">
            <div className="card p-6">
              <h3 className="font-semibold mb-4">Continue Learning</h3>
              {continueCase && (
                <div className="flex gap-4 items-center">
                  <div className="w-28 shrink-0">
                    <CaseEcg height={80} />
                  </div>
                  <div className="flex-1">
                    <p className="font-medium">{continueCase.title}</p>
                    <p className="text-xs text-brand-muted mt-1">Difficulty: {continueCase.difficulty} · 6 min</p>
                  </div>
                </div>
              )}
              <button
                onClick={() => navigate(`/student/cases/${continueCase?.id}`)}
                className="btn-primary w-full mt-5"
              >
                Continue →
              </button>
            </div>

            <div className="card p-6">
              <h3 className="font-semibold mb-4">Recent Activity</h3>
              <ul className="space-y-3">
                {recent.map((r) => (
                  <li key={r.id} className="flex items-start gap-3 text-sm">
                    <span className="text-brand-accent">{r.icon}</span>
                    <div className="flex-1">
                      <p>{r.title}</p>
                      <p className="text-xs text-brand-muted">{r.time}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}