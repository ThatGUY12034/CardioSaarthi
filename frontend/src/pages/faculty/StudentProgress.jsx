import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Layout from "../../components/Layout";
import EcgImage from "../../components/EcgImage";
import { EmptyState, ErrorState, InlineError, SkeletonCard } from "../../components/States";
import { addRemark, getStudent } from "../../api/cohortApi";
import { errorMessage } from "../../api/studyApi";

/**
 * One student's work, and the place a teacher answers it.
 *
 * <p>Every mistake is shown with the named error, what the student said and
 * what the recording showed, so a teacher can see what happened without opening
 * the case. A remark is left on the attempt itself rather than on the student,
 * because advice about a specific trace is advice somebody can act on.
 */

const accuracyTone = (pct) =>
  pct === null || pct === undefined
    ? "bg-white/10"
    : pct >= 80
      ? "bg-brand-success"
      : pct >= 60
        ? "bg-brand-warning"
        : "bg-brand-danger";

/** Answers are stored as the structured value the grader received. */
function readAnswer(raw) {
  if (!raw) return "—";
  try {
    const a = JSON.parse(raw);
    if (a.notPresent) return "not measurable";
    if (a.value !== null && a.value !== undefined) return String(a.value);
    if (a.category) return String(a.category).toLowerCase().replace(/_/g, " ");
    if (Array.isArray(a.leads) && a.leads.length) return a.leads.join(", ");
    if (Array.isArray(a.leads)) return "no leads";
    return "—";
  } catch {
    return String(raw);
  }
}

function readExpected(raw) {
  if (!raw) return "—";
  try {
    const value = JSON.parse(raw);
    if (Array.isArray(value)) return value.length ? value.join(", ") : "none";
    return String(value).replace(/^"|"$/g, "").toLowerCase().replace(/_/g, " ");
  } catch {
    return String(raw);
  }
}

function RemarkBox({ mistake, onSaved }) {
  const [open, setOpen] = useState(false);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const save = async () => {
    if (!body.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await addRemark(mistake.sessionStepId, body.trim());
      setBody("");
      setOpen(false);
      onSaved();
    } catch (e) {
      setError(errorMessage(e, "That remark was not saved."));
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="btn-ghost text-xs !py-1.5 !px-3 mt-3">
        {mistake.remarkCount > 0
          ? `Add another remark (${mistake.remarkCount})`
          : "Leave a remark"}
      </button>
    );
  }

  return (
    <div className="mt-3">
      <label className="sr-only" htmlFor={`remark-${mistake.sessionStepId}`}>
        Your remark on this attempt
      </label>
      <textarea
        id={`remark-${mistake.sessionStepId}`}
        rows={3}
        value={body}
        onChange={(event) => setBody(event.target.value)}
        maxLength={2000}
        placeholder="What should they do differently on this trace?"
        className="w-full bg-brand-bg2 border border-white/10 rounded-lg px-3 py-2 text-sm"
      />
      {error && <div className="mt-2"><InlineError message={error} /></div>}
      <div className="flex gap-2 mt-2">
        <button onClick={save} disabled={busy || !body.trim()} className="btn-primary text-xs !py-1.5 !px-3">
          {busy ? "Saving…" : "Send to student"}
        </button>
        <button onClick={() => setOpen(false)} className="btn-ghost text-xs !py-1.5 !px-3">
          Cancel
        </button>
      </div>
      <p className="text-[11px] text-brand-muted mt-2">
        A remark cannot be edited once sent. It is a record of what was said.
      </p>
    </div>
  );
}

export default function StudentProgress() {
  const { id } = useParams();
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getStudent(id)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e, "Could not load this student."));
      });
    return () => {
      cancelled = true;
    };
  }, [id, reloadKey]);

  if (error) {
    return (
      <Layout role="FACULTY">
        <Link to="/faculty/students" className="text-sm text-brand-accent hover:underline">
          ← Back to students
        </Link>
        <div className="mt-8">
          <ErrorState message={error} onRetry={() => setReloadKey((n) => n + 1)} />
        </div>
      </Layout>
    );
  }

  if (!detail) {
    return (
      <Layout role="FACULTY">
        <div className="space-y-4 mt-4">
          <SkeletonCard lines={2} />
          <SkeletonCard lines={4} />
        </div>
      </Layout>
    );
  }

  const s = detail.student;

  return (
    <Layout role="FACULTY">
      <Link to="/faculty/students" className="text-sm text-brand-accent hover:underline">
        ← Back to students
      </Link>

      <h1 className="page-title mt-3">{s.fullName}</h1>
      <p className="page-subtitle">
        {s.collegeId}
        {s.cohort ? ` · ${s.cohort}` : ""}
      </p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mt-6">
        <div className="card p-4">
          <p className="text-xs text-brand-muted">Cases completed</p>
          <p className="text-2xl font-bold tabular mt-1">{s.casesCompleted}</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-brand-muted">Average score</p>
          <p className="text-2xl font-bold tabular mt-1">
            {s.averageScorePct === null ? "—" : `${s.averageScorePct}%`}
          </p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-brand-muted">Mistakes recorded</p>
          <p className="text-2xl font-bold tabular mt-1">{s.mistakes}</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-brand-muted">Learning gain</p>
          {s.learningGainPct === null ? (
            <p className="text-sm text-brand-muted mt-2">Needs four cases</p>
          ) : (
            <p
              className={`text-2xl font-bold tabular mt-1 ${
                s.learningGainPct > 0 ? "text-brand-success" : "text-brand-danger"
              }`}
            >
              {s.learningGainPct > 0 ? "+" : ""}
              {s.learningGainPct}%
            </p>
          )}
        </div>
      </div>

      {detail.earlyAccuracyPct !== null && (
        <p className="text-xs text-brand-muted mt-3">
          First-attempt accuracy went from {detail.earlyAccuracyPct}% across their earlier
          cases to {detail.lateAccuracyPct}% across their later ones.
        </p>
      )}

      <div className="card p-6 mt-6">
        <h2 className="font-semibold">Strength by concept</h2>
        <p className="text-xs text-brand-muted mt-1">
          Correct on the first attempt. The same figure the student sees.
        </p>
        <ul className="mt-5 space-y-3">
          {detail.concepts.map((c) => (
            <li key={c.step}>
              <div className="flex items-baseline justify-between text-sm">
                <span>
                  <span className="text-brand-muted mr-2">{c.step}.</span>
                  {c.label}
                </span>
                <span className="tabular text-brand-muted">
                  {c.firstAttemptAccuracyPct === null
                    ? "not practised"
                    : `${c.firstAttemptAccuracyPct}% (${c.firstAttemptCorrect}/${c.firstAttempts})`}
                </span>
              </div>
              <div className="h-2 bg-white/5 rounded mt-1.5 overflow-hidden">
                <div
                  className={`h-full rounded ${accuracyTone(c.firstAttemptAccuracyPct)}`}
                  style={{ width: `${c.firstAttemptAccuracyPct ?? 0}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      </div>

      <h2 className="font-semibold mt-8">Where it went wrong</h2>
      <p className="text-xs text-brand-muted mt-1">
        Most recent first. Leave a remark on any of these and the student sees it on their
        own pages.
      </p>

      {detail.mistakes.length === 0 ? (
        <EmptyState
          className="mt-4"
          icon={"✓"}
          title="No mistakes recorded"
          description="This student has not answered a step incorrectly yet."
        />
      ) : (
        <div className="space-y-4 mt-4">
          {detail.mistakes.map((m) => (
            <article key={m.sessionStepId} className="card p-5">
              <div className="grid md:grid-cols-[160px_1fr] gap-5">
                <div>
                  <EcgImage caseId={m.caseId} kind="clean" height={100} zoomable={false} />
                  <p className="text-[11px] text-brand-muted mt-2">
                    Recording {m.sourceEcgId ?? m.caseId}
                  </p>
                </div>
                <div>
                  <div className="flex items-baseline justify-between gap-3 flex-wrap">
                    <h3 className="font-semibold text-sm">
                      <span className="text-brand-muted mr-2">Step {m.step}</span>
                      {m.stepLabel}
                    </h3>
                    <span className="text-[11px] text-brand-muted">
                      attempt {m.attempt}
                    </span>
                  </div>

                  <p className="text-sm mt-2">
                    <span className="text-brand-danger">Said {readAnswer(m.answer)}</span>
                    <span className="text-brand-muted"> · recording showed </span>
                    <span className="text-brand-success">{readExpected(m.expected)}</span>
                  </p>

                  {m.errorDescription && (
                    <p className="text-sm text-brand-muted mt-2 leading-relaxed">
                      {m.errorDescription}
                    </p>
                  )}

                  <RemarkBox mistake={m} onSaved={() => setReloadKey((n) => n + 1)} />
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </Layout>
  );
}
