import { useEffect, useState } from "react";
import Layout from "../../components/Layout";
import { EmptyState, ErrorState, SkeletonRows } from "../../components/States";
import { errorMessage, getLeaderboard } from "../../api/studyApi";

/**
 * Positions, without names.
 *
 * <p>This page used to list five invented classmates by name and score. A real
 * cohort ranking that names people publishes a student's weakness to everyone
 * they sit next to, and the bottom of a leaderboard is exactly the person least
 * helped by it being public.
 *
 * <p>So the server returns positions and marks which row is the caller's. A
 * student can see where they stand without anyone learning where anyone else
 * does.
 */
export default function Leaderboard() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);

  const [reloadKey, setReloadKey] = useState(0);
  const load = () => setReloadKey((n) => n + 1);

  useEffect(() => {
    let cancelled = false;
    getLeaderboard(15)
      .then((data) => {
        if (!cancelled) setRows(data);
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e, "Could not load the leaderboard."));
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  return (
    <Layout role="STUDENT">
      <h1 className="page-title">Cohort Standing</h1>
      <p className="page-subtitle">
        Where you sit against the rest of the cohort. Positions only — no names.
      </p>

      {error ? (
        <div className="mt-8">
          <ErrorState message={error} onRetry={load} />
        </div>
      ) : rows === null ? (
        <SkeletonRows className="mt-8" count={6} />
      ) : rows.length === 0 ? (
        <EmptyState
          className="mt-8"
          title="Nobody has finished a case yet"
          description="Positions appear once students complete sessions. Finish a case and you will be the first."
        />
      ) : (
        <div className="card mt-8 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[520px]">
              <thead className="bg-brand-cardLight text-brand-muted text-xs uppercase">
                <tr>
                  <th className="text-left px-5 py-3 font-medium">Position</th>
                  <th className="text-left px-5 py-3 font-medium">Student</th>
                  <th className="text-left px-5 py-3 font-medium">Cases completed</th>
                  <th className="text-left px-5 py-3 font-medium">Average score</th>
                  <th className="text-left px-5 py-3 font-medium">Streak</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, index) => (
                  <tr
                    key={`${r.position}-${index}`}
                    className={`border-t border-white/5 ${
                      r.isYou ? "bg-brand-primary/10" : ""
                    }`}
                  >
                    <td className="px-5 py-4 tabular font-medium">#{r.position}</td>
                    <td className="px-5 py-4">
                      {r.isYou ? (
                        <span className="text-brand-accent font-semibold">You</span>
                      ) : (
                        <span className="text-brand-muted">A student in your cohort</span>
                      )}
                    </td>
                    <td className="px-5 py-4 tabular">{r.casesCompleted}</td>
                    <td className="px-5 py-4 tabular">
                      {r.averageScorePct === null ? "—" : `${r.averageScorePct}%`}
                    </td>
                    <td className="px-5 py-4 tabular">{r.currentStreakDays} days</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <p className="text-xs text-brand-muted mt-4">
        Ranked by average score, then by cases completed. Each case is scored over the steps
        the platform was able to mark.
      </p>
    </Layout>
  );
}
