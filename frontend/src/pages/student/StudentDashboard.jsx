import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../../components/Navbar";
import Sidebar from "../../components/Sidebar";
import StatCard from "../../components/StatCard";
import CaseEcg from "../../components/CaseEcg";
import { getPractisableCases } from "../../api/studyApi";
import { useAuth } from "../../context/AuthContext";

// Illustrative until the runtime serves a student's own history back. A fixed
// list is a constant, not state -- nothing ever sets it.
const RECENT = [
  { id: 5, title: "Completed Case 5", time: "2 hours ago", icon: "✅" },
  { id: 4, title: "Score 80% in Case 4", time: "1 day ago", icon: "🎯" },
  { id: 1, title: "Started Case 6", time: "1 day ago", icon: "▶" },
];

export default function StudentDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  // totalCases is counted from the bank. The other three need a history of
  // finished sessions, which the runtime records but does not yet serve back,
  // so they are marked in the interface rather than quietly invented.
  const [stats, setStats] = useState({ totalCases: null, completed: 5, streak: 3, avgScore: 78 });
  const [continueCase, setContinueCase] = useState(null);


  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const cases = await getPractisableCases(50);
        if (cancelled) return;
        setStats((current) => ({ ...current, totalCases: cases.length }));
        // A real case, because this button starts a real session. It used to
        // point at case 6, which does not exist in the bank -- the most
        // prominent button on the first screen a student sees led to an error.
        const next = cases[0];
        if (next) {
          setContinueCase({
            id: next.caseId,
            // Not the diagnosis. Naming it here would answer step 2 before the
            // student has opened the case.
            title: `Recording ${next.sourceEcgId ?? next.caseId}`,
            subtitle: next.age ? `${next.sex}, ${Math.round(next.age)} years` : "Ready to read",
          });
        }
      } catch {
        // The dashboard is still readable without it; the cases page reports
        // the failure properly.
      }
    })();
    return () => {
      cancelled = true;
    };
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
            <StatCard icon="🩺" label="Total Cases" value={stats.totalCases ?? "—"} />
            <StatCard icon="✅" label="Completed" value={stats.completed} color="brand-success" />
            <StatCard icon="🔥" label="Current Streak" value={`${stats.streak} days`} color="brand-warning" />
            <StatCard icon="📊" label="Average Score" value={`${stats.avgScore}%`} color="brand-accent" />
          </div>

          <p className="text-xs text-brand-muted mt-3">
            Total cases is live from the approved bank. Completed, streak and average
            score are illustrative until finished sessions are served back.
          </p>

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
                    {/* The patient, not a difficulty rating. The bank has no
                        difficulty grade, and inventing one would be a claim
                        about how hard a recording is to read. */}
                    <p className="text-xs text-brand-muted mt-1">{continueCase.subtitle}</p>
                  </div>
                </div>
              )}
              <button
                onClick={() => navigate(`/student/cases/${continueCase.id}`)}
                disabled={!continueCase}
                className="btn-primary w-full mt-5 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Continue →
              </button>
            </div>

            <div className="card p-6">
              <h3 className="font-semibold mb-4">Recent Activity</h3>
              <ul className="space-y-3">
                {RECENT.map((r) => (
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