import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import Layout from "../../components/Layout";
import EcgImage from "../../components/EcgImage";
import { errorMessage, getSummary } from "../../api/studyApi";

/**
 * How the case went.
 *
 * <p>Scored on first-attempt answers out of the steps that could be marked,
 * which is a smaller number than nine: the T-wave step has no computed answer
 * yet, and a step the engine was unsure of is not marked either. Dividing by
 * nine regardless would quietly penalise a student for a gap in the platform.
 *
 * <p>The annotated ECG is shown here and only here. During the case it would
 * mark the boundaries the student is being asked to find.
 */
export default function CaseResult() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const sessionId = location.state?.sessionId;

  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);

  // Derived, not set in the effect: reaching this page without a finished
  // session is a fact about the navigation, known before any render.
  const missingSession = !sessionId;

  useEffect(() => {
    if (!sessionId) {
      return undefined;
    }
    let cancelled = false;
    getSummary(sessionId)
      .then((loaded) => {
        if (!cancelled) setSummary(loaded);
      })
      .catch((exception) => {
        if (!cancelled) setError(errorMessage(exception, "Could not load the results."));
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // One row per step: the first attempt is what counts, later ones are shown
  // underneath so a student can see where the reasoning turned around.
  const firstAttempts = summary?.steps.filter((step) => step.attempt === 1) ?? [];
  const graded = firstAttempts.filter((step) => step.errorLabel !== "NOT_GRADED");
  const score = summary && graded.length
    ? Math.round((summary.correctFirstTime / graded.length) * 100)
    : null;

  return (
    <Layout role="STUDENT">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <button
            onClick={() => navigate("/student/cases")}
            className="text-xs text-brand-muted hover:text-white"
          >
            ← Back to cases
          </button>
          <h1 className="text-2xl font-bold mt-1">Recording {id} — results</h1>
        </div>
        {score !== null && (
          <div className="text-right">
            <p className="text-xs text-brand-muted">Right first time</p>
            <p
              className={`text-4xl font-bold ${
                score >= 80
                  ? "text-brand-success"
                  : score >= 50
                    ? "text-brand-warning"
                    : "text-brand-danger"
              }`}
            >
              {score}%
            </p>
            <p className="text-[11px] text-brand-muted">
              {summary.correctFirstTime} of {graded.length} marked steps
            </p>
          </div>
        )}
      </div>

      {(error || missingSession) && (
        <div className="mt-6 rounded border border-brand-danger/40 bg-brand-danger/10 px-4 py-3 text-sm text-brand-danger">
          {error || "This page needs a finished case. Start one from the case list."}
        </div>
      )}

      {summary && (
        <div className="grid lg:grid-cols-[1fr_22rem] gap-6 mt-8">
          <div className="space-y-2">
            {firstAttempts.map((step) => {
              const retries = summary.steps.filter(
                (other) => other.step === step.step && other.attempt > 1,
              );
              return (
                <div key={step.step} className="card p-4">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="font-medium text-sm">
                      {step.step}. {step.label}
                    </span>
                    <span
                      className={`text-xs ${
                        step.correct ? "text-brand-success" : "text-brand-warning"
                      }`}
                    >
                      {step.correct ? "correct" : (step.errorLabel || "not marked")
                        .replace(/_/g, " ")
                        .toLowerCase()}
                    </span>
                  </div>
                  {step.feedback && (
                    <p className="text-xs text-brand-muted mt-2">{step.feedback}</p>
                  )}
                  {retries.map((retry) => (
                    <p key={retry.attempt} className="text-xs text-brand-muted mt-2 pl-3 border-l border-white/10">
                      Attempt {retry.attempt}: {retry.correct ? "correct" : "still not right"}
                      {retry.feedback ? ` — ${retry.feedback}` : ""}
                    </p>
                  ))}
                </div>
              );
            })}
          </div>

          <div className="space-y-4">
            <div className="card overflow-hidden">
              <EcgImage
                caseId={Number(id)}
                kind="annotated"
                height={260}
                label={`Recording ${id}, annotated`}
              />
              <p className="px-4 py-3 text-[11px] text-brand-muted">
                The same recording with the boundaries the engine measured from. Shown now rather
                than during the case, where it would mark the points you were asked to find.
              </p>
            </div>
            <button onClick={() => navigate("/student/cases")} className="btn-primary text-sm w-full">
              Another case
            </button>
          </div>
        </div>
      )}
    </Layout>
  );
}
