import { useEffect, useState } from "react";
import Layout from "../../components/Layout";
import StatCard from "../../components/StatCard";
import { EmptyState, ErrorState, SkeletonCard } from "../../components/States";
import {
  errorMessage,
  getConceptStrength,
  getProgress,
  getRecentSessions,
} from "../../api/studyApi";

/**
 * What this student actually knows, from their own attempt record.
 *
 * <p>This page used to draw a rising line through six invented scores. Every
 * number here now comes from the runtime: the per-concept accuracy is first
 * attempts only, because a retry after a hint measures whether a student can
 * take a hint rather than whether they knew the answer.
 */

const BAR = (pct) =>
  pct === null || pct === undefined
    ? "bg-white/10"
    : pct >= 80
      ? "bg-brand-success"
      : pct >= 60
        ? "bg-brand-warning"
        : "bg-brand-danger";

export default function Progress() {
  const [state, setState] = useState({ loading: true, error: null });
  const [progress, setProgress] = useState(null);
  const [concepts, setConcepts] = useState([]);
  const [sessions, setSessions] = useState([]);

  // A reload key rather than a function called from the effect body: the
  // effect must not set state synchronously, and retrying is an event.
  const [reloadKey, setReloadKey] = useState(0);
  const load = () => setReloadKey((n) => n + 1);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getProgress(), getConceptStrength(), getRecentSessions(12)])
      .then(([p, c, s]) => {
        if (cancelled) return;
        setProgress(p);
        setConcepts(c);
        setSessions(s);
        setState({ loading: false, error: null });
      })
      .catch((e) => {
        if (!cancelled) {
          setState({ loading: false, error: errorMessage(e, "Could not load your progress.") });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (state.error) {
    return (
      <Layout role="STUDENT">
        <h1 className="page-title">Your Progress</h1>
        <div className="mt-8">
          <ErrorState message={state.error} onRetry={load} />
        </div>
      </Layout>
    );
  }

  const scored = sessions.filter((s) => s.scorePct !== null).slice().reverse();

  return (
    <Layout role="STUDENT">
      <h1 className="page-title">Your Progress</h1>
      <p className="page-subtitle">
        Measured from every answer you have submitted, not estimated.
      </p>

      {state.loading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mt-8">
          {[0, 1, 2, 3].map((i) => (
            <SkeletonCard key={i} lines={1} />
          ))}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mt-8">
            <StatCard icon="🎯" label="Cases completed" value={progress.casesCompleted} />
            <StatCard
              icon="📈"
              label="Average score"
              value={progress.averageScorePct === null ? "—" : `${progress.averageScorePct}%`}
              color="brand-accent"
            />
            <StatCard
              icon="🏅"
              label="Best score"
              value={progress.bestScorePct === null ? "—" : `${progress.bestScorePct}%`}
              color="brand-success"
            />
            <StatCard
              icon="🔥"
              label="Current streak"
              value={`${progress.currentStreakDays} days`}
              color="brand-warning"
            />
          </div>

          <div className="grid lg:grid-cols-2 gap-6 mt-8">
            {/* Per-concept strength. The nine steps, worst first where known. */}
            <div className="card p-6">
              <h2 className="font-semibold">Strength by concept</h2>
              <p className="text-xs text-brand-muted mt-1">
                Correct on the first attempt. A concept you have not met yet shows no bar.
              </p>
              <ul className="mt-5 space-y-3">
                {concepts.map((c) => (
                  <li key={c.concept}>
                    <div className="flex items-baseline justify-between text-sm">
                      <span>
                        <span className="text-brand-muted mr-2">{c.step}.</span>
                        {c.label}
                      </span>
                      <span className="tabular text-brand-muted">
                        {c.firstAttemptAccuracyPct === null
                          ? "not practised"
                          : `${c.firstAttemptAccuracyPct}%  (${c.firstAttemptCorrect}/${c.firstAttempts})`}
                      </span>
                    </div>
                    <div className="h-2 bg-white/5 rounded mt-1.5 overflow-hidden">
                      <div
                        className={`h-full rounded ${BAR(c.firstAttemptAccuracyPct)}`}
                        style={{ width: `${c.firstAttemptAccuracyPct ?? 0}%` }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            {/* Score over time, drawn from real sessions rather than a curve. */}
            <div className="card p-6">
              <h2 className="font-semibold">Score over time</h2>
              <p className="text-xs text-brand-muted mt-1">
                Each case is scored over the steps that were marked, not out of nine.
              </p>
              {scored.length === 0 ? (
                <p className="text-sm text-brand-muted mt-6">
                  Finish a case and your scores appear here.
                </p>
              ) : (
                <div className="mt-6 flex items-end gap-2 h-44">
                  {scored.map((s) => (
                    <div key={s.sessionId} className="flex-1 flex flex-col items-center gap-1">
                      <span className="text-[10px] text-brand-muted tabular">{s.scorePct}%</span>
                      <div
                        className={`w-full rounded-t ${BAR(s.scorePct)}`}
                        style={{ height: `${Math.max(4, s.scorePct)}%` }}
                        title={`Recording ${s.sourceEcgId ?? s.caseId}: ${s.scorePct}% over ${s.stepsMarked} marked steps`}
                      />
                      <span className="text-[9px] text-brand-muted truncate w-full text-center">
                        {s.sourceEcgId ?? s.caseId}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="card mt-6 overflow-hidden">
            <h2 className="font-semibold px-6 pt-5">Recent sessions</h2>
            {sessions.length === 0 ? (
              <div className="p-6">
                <EmptyState
                  title="No sessions yet"
                  description="Open a case from Practice Cases to begin. Your record builds from what you answer."
                />
              </div>
            ) : (
              <div className="overflow-x-auto mt-3">
                <table className="w-full text-sm min-w-[560px]">
                  <thead className="bg-brand-cardLight text-brand-muted text-xs uppercase">
                    <tr>
                      <th className="text-left px-5 py-3 font-medium">Recording</th>
                      <th className="text-left px-5 py-3 font-medium">Mode</th>
                      <th className="text-left px-5 py-3 font-medium">Steps marked</th>
                      <th className="text-left px-5 py-3 font-medium">Score</th>
                      <th className="text-left px-5 py-3 font-medium">State</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sessions.map((s) => (
                      <tr key={s.sessionId} className="border-t border-white/5">
                        <td className="px-5 py-3">{s.sourceEcgId ?? s.caseId}</td>
                        <td className="px-5 py-3 text-brand-muted">
                          {s.mode.toLowerCase().replace(/_/g, " ")}
                        </td>
                        <td className="px-5 py-3 tabular">{s.stepsMarked} of 9</td>
                        <td className="px-5 py-3 tabular">
                          {s.scorePct === null ? "—" : `${s.scorePct}%`}
                        </td>
                        <td className="px-5 py-3 text-brand-muted">
                          {s.state === "CASE_COMPLETE" ? "finished" : "in progress"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </Layout>
  );
}
