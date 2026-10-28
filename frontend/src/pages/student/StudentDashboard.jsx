import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import RemarksPanel from "../../components/RemarksPanel";
import StatCard from "../../components/StatCard";
import CaseEcg from "../../components/CaseEcg";
import { SkeletonCard } from "../../components/States";
import {
  getNextConcepts,
  getPractisableCases,
  getProgress,
  getRecentSessions,
} from "../../api/studyApi";
import { useAuth } from "../../context/useAuth";

/**
 * The first screen a student sees, and now the first one telling the truth.
 *
 * <p>Completed, streak and average score were constants written into this file.
 * They are read from the runtime, which has been recording the real thing since
 * the session orchestrator was built.
 *
 * <p>The dashboard also now says what to practise next and why. That answer
 * comes from the scheduler, not from the order cases happen to sit in.
 */

function timeAgo(iso) {
  if (!iso) return "";
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 90) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

export default function StudentDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [progress, setProgress] = useState(null);
  const [continueCase, setContinueCase] = useState(null);
  const [recent, setRecent] = useState([]);
  const [next, setNext] = useState([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [p, cases, sessions, concepts] = await Promise.all([
          getProgress(),
          getPractisableCases(50),
          getRecentSessions(4),
          getNextConcepts(3),
        ]);
        if (cancelled) return;
        setProgress(p);
        setRecent(sessions);
        setNext(concepts);

        // Resume an unfinished case if there is one; otherwise offer a new one.
        const open = sessions.find((s) => s.state !== "CASE_COMPLETE");
        const fresh = cases[0];
        const chosen = open
          ? { id: open.caseId, label: open.sourceEcgId ?? open.caseId, resuming: true }
          : fresh
            ? { id: fresh.caseId, label: fresh.sourceEcgId ?? fresh.caseId, resuming: false,
                subtitle: fresh.age ? `${fresh.sex}, ${Math.round(fresh.age)} years` : null }
            : null;
        setContinueCase(chosen);
      } catch {
        // The dashboard stays readable without its numbers; the pages that own
        // each one report their own failure properly.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const show = (value, suffix = "") =>
    value === null || value === undefined ? "—" : `${value}${suffix}`;

  return (
    <Layout role="STUDENT">
      <h1 className="page-title">
        Good to see you, {user?.name?.split(" ")[0] || "there"}
      </h1>
      <p className="page-subtitle">Keep learning, one beat at a time.</p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mt-8">
        <StatCard icon="🩺" label="Cases available" value={show(progress?.casesAvailable)} />
        <StatCard
          icon="✅"
          label="Completed"
          value={show(progress?.casesCompleted)}
          color="brand-success"
        />
        <StatCard
          icon="🔥"
          label="Current streak"
          value={progress ? `${progress.currentStreakDays} days` : "—"}
          color="brand-warning"
        />
        <StatCard
          icon="📊"
          label="Average score"
          value={show(progress?.averageScorePct, "%")}
          color="brand-accent"
        />
      </div>

      <div className="grid md:grid-cols-2 gap-6 mt-8">
        <div className="card p-6">
          <h2 className="font-semibold mb-4">
            {continueCase?.resuming ? "Pick up where you left off" : "Start a case"}
          </h2>
          {continueCase ? (
            <>
              <div className="flex gap-4 items-center">
                <div className="w-28 shrink-0">
                  <CaseEcg caseId={continueCase.id} height={80} />
                </div>
                <div className="flex-1">
                  <p className="font-medium">Recording {continueCase.label}</p>
                  {continueCase.subtitle && (
                    <p className="text-xs text-brand-muted mt-1">{continueCase.subtitle}</p>
                  )}
                  {continueCase.resuming && (
                    <p className="text-xs text-brand-warning mt-1">Session in progress</p>
                  )}
                </div>
              </div>
              <button
                onClick={() => navigate(`/student/cases/${continueCase.id}`)}
                className="btn-primary w-full mt-5"
              >
                {continueCase.resuming ? "Resume →" : "Begin →"}
              </button>
            </>
          ) : (
            <SkeletonCard lines={2} className="!p-0 !bg-transparent !border-0" />
          )}
        </div>

        {/* The scheduler's answer, with its reason. A student told to practise
            a concept is owed the reason it was chosen. */}
        <div className="card p-6">
          <h2 className="font-semibold mb-1">Practise next</h2>
          <p className="text-xs text-brand-muted mb-4">
            Chosen from your own record, weakest concept first.
          </p>
          {next.length === 0 ? (
            <p className="text-sm text-brand-muted">
              Finish a case and this fills in with the concepts you find hardest.
            </p>
          ) : (
            <ul className="space-y-3">
              {next.map((c) => (
                <li key={c.concept} className="flex items-start gap-3">
                  <span className="w-6 h-6 shrink-0 rounded-full bg-brand-primary/20 text-brand-accent grid place-items-center text-[11px] font-semibold">
                    {c.step}
                  </span>
                  <div className="flex-1">
                    <p className="text-sm font-medium">{c.label}</p>
                    <p className="text-xs text-brand-muted">{c.reason}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <button
            onClick={() => navigate("/student/progress")}
            className="btn-ghost w-full mt-5 text-sm"
          >
            See full progress
          </button>
        </div>
      </div>

      {/* What a teacher said, before what the student did: a remark they have
          not read is the only thing here that can still change the next case. */}
      <RemarksPanel limit={6} />

      <div className="card p-6 mt-6">
        <h2 className="font-semibold mb-4">Recent activity</h2>
        {recent.length === 0 ? (
          <p className="text-sm text-brand-muted">
            Nothing yet. Your sessions appear here as you work through cases.
          </p>
        ) : (
          <ul className="space-y-3">
            {recent.map((s) => (
              <li key={s.sessionId} className="flex items-start gap-3 text-sm">
                <span aria-hidden="true">
                  {s.state === "CASE_COMPLETE" ? "✅" : "▶"}
                </span>
                <div className="flex-1">
                  <p>
                    {s.state === "CASE_COMPLETE"
                      ? `Finished recording ${s.sourceEcgId ?? s.caseId}`
                      : `Started recording ${s.sourceEcgId ?? s.caseId}`}
                    {s.scorePct !== null && s.state === "CASE_COMPLETE" && (
                      <span className="text-brand-muted"> — {s.scorePct}% over {s.stepsMarked} marked steps</span>
                    )}
                  </p>
                  <p className="text-xs text-brand-muted">
                    {timeAgo(s.completedAt || s.startedAt)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Layout>
  );
}
