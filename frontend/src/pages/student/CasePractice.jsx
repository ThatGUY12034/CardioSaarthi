import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import Layout from "../../components/Layout";
import EcgImage from "../../components/EcgImage";
import {
  errorMessage,
  finishSession,
  getSteps,
  startSession,
  submitAnswer,
} from "../../api/studyApi";

/**
 * Working a case, one step at a time.
 *
 * <p>The server decides what happens next. This page submits an answer and is
 * told whether it was right, what to say about it, and whether the session moved
 * on -- it does not decide any of that, because the order of the nine steps is
 * dependency-driven and the mode's rules about attempts are the orchestrator's.
 *
 * <p>There is no timer. The old page counted down from ten minutes, which
 * measures haste rather than reading. Time per step is recorded and sent, since
 * how long a step takes is worth knowing, but nothing is failed for being slow.
 */

const LEADS = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"];

function human(value) {
  return String(value).replace(/_/g, " ").toLowerCase();
}

/** The input a step needs, decided by what the server said it accepts. */
function AnswerInput({ step, draft, onChange, disabled }) {
  if (step.answerKind === "NUMERIC") {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="number"
          autoFocus
          disabled={disabled}
          value={draft.value ?? ""}
          onChange={(event) => onChange({ value: event.target.value, notPresent: false })}
          placeholder={step.label}
          className="w-40 bg-brand-bg2 border border-white/10 rounded px-3 py-2 text-lg"
        />
        <span className="text-brand-muted text-sm">{step.unit}</span>
        {step.allowsAbsent && (
          <label className="flex items-center gap-2 text-sm text-brand-muted ml-2">
            <input
              type="checkbox"
              disabled={disabled}
              checked={Boolean(draft.notPresent)}
              onChange={(event) =>
                onChange({ value: "", notPresent: event.target.checked })
              }
            />
            {/* On a rhythm with no P waves this is the correct answer, not a
                way of skipping the step. */}
            Cannot be measured on this recording
          </label>
        )}
      </div>
    );
  }

  if (step.answerKind === "MULTI_CATEGORICAL") {
    const selected = draft.leads ?? [];
    const toggle = (lead) =>
      onChange({
        leads: selected.includes(lead)
          ? selected.filter((item) => item !== lead)
          : [...selected, lead],
        notPresent: false,
      });
    return (
      <div>
        <div className="flex flex-wrap gap-2">
          {LEADS.map((lead) => (
            <button
              key={lead}
              type="button"
              disabled={disabled}
              onClick={() => toggle(lead)}
              className={`px-3 py-1.5 rounded border text-sm ${
                selected.includes(lead)
                  ? "border-brand-primary text-white"
                  : "border-white/10 text-brand-muted"
              }`}
            >
              {lead}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-brand-muted mt-3">
          <input
            type="checkbox"
            disabled={disabled}
            checked={Boolean(draft.notPresent)}
            onChange={(event) => onChange({ leads: [], notPresent: event.target.checked })}
          />
          No lead shows ST deviation
        </label>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {step.options.map((option) => (
        <button
          key={option}
          type="button"
          disabled={disabled}
          onClick={() => onChange({ category: option })}
          className={`px-4 py-2 rounded border text-sm ${
            draft.category === option
              ? "border-brand-primary text-white"
              : "border-white/10 text-brand-muted"
          }`}
        >
          {human(option)}
        </button>
      ))}
    </div>
  );
}

export default function CasePractice() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const mode = location.state?.mode || "BEGINNER_TUTOR";

  const [steps, setSteps] = useState(null);
  const [session, setSession] = useState(null);
  const [draft, setDraft] = useState({});
  const [turn, setTurn] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [interpretation, setInterpretation] = useState("");
  const [startedAt, setStartedAt] = useState(() => Date.now());

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [loadedSteps, started] = await Promise.all([
          getSteps(),
          startSession(Number(id), mode),
        ]);
        if (cancelled) return;
        setSteps(loadedSteps);
        setSession(started);
      } catch (exception) {
        if (!cancelled) setError(errorMessage(exception, "Could not start this case."));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, mode]);

  const currentStep = useMemo(
    () => steps?.find((step) => step.step === session?.currentStep) ?? null,
    [steps, session],
  );

  const answerReady = useMemo(() => {
    if (!currentStep) return false;
    if (draft.notPresent) return true;
    if (currentStep.answerKind === "NUMERIC") return draft.value !== "" && draft.value != null;
    if (currentStep.answerKind === "MULTI_CATEGORICAL") return (draft.leads ?? []).length > 0;
    return Boolean(draft.category);
  }, [currentStep, draft]);

  const onDraft = useCallback((next) => {
    setDraft((current) => ({ ...current, ...next }));
    setTurn(null);
  }, []);

  async function submit() {
    if (!answerReady || !currentStep) return;
    setBusy(true);
    setError(null);
    try {
      const answer = draft.notPresent
        ? { notPresent: true }
        : currentStep.answerKind === "NUMERIC"
          ? { value: Number(draft.value) }
          : currentStep.answerKind === "MULTI_CATEGORICAL"
            ? { leads: draft.leads }
            : { category: draft.category };

      const result = await submitAnswer(
        session.sessionId,
        currentStep.step,
        answer,
        Date.now() - startedAt,
      );
      setTurn(result);

      if (result.advanced) {
        // The server has moved on, so the local view of the session has to as
        // well: what step to show next is its decision, not this page's.
        setSession((current) => ({
          ...current,
          currentStep: result.nextStep ?? current.currentStep,
          state: result.nextStep ? current.state : "AWAITING_FINAL",
        }));
        setDraft({});
        setStartedAt(Date.now());
      }
    } catch (exception) {
      setError(errorMessage(exception, "That answer was not recorded."));
    } finally {
      setBusy(false);
    }
  }

  async function finish() {
    setBusy(true);
    setError(null);
    try {
      await finishSession(session.sessionId, interpretation);
      navigate(`/student/cases/${id}/result`, { state: { sessionId: session.sessionId } });
    } catch (exception) {
      setError(errorMessage(exception, "Could not finish the case."));
    } finally {
      setBusy(false);
    }
  }

  if (error && !session) {
    return (
      <Layout role="STUDENT">
        <div className="card p-8 mt-8">
          <p className="text-brand-danger">{error}</p>
          <button onClick={() => navigate("/student/cases")} className="btn-ghost text-sm mt-4">
            Back to cases
          </button>
        </div>
      </Layout>
    );
  }

  if (!session || !steps) {
    return (
      <Layout role="STUDENT">
        <p className="text-brand-muted mt-8">Opening the case…</p>
      </Layout>
    );
  }

  const done = session.state === "AWAITING_FINAL" || !currentStep;

  return (
    <Layout role="STUDENT">
      <div className="flex items-baseline justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold">Recording {id}</h1>
        <span className="text-sm text-brand-muted">
          {done ? "All nine steps done" : `Step ${session.currentStep} of ${session.totalSteps}`}
          {" · "}
          {human(mode)}
        </span>
      </div>

      {/* Progress through the nine, so the sequence itself is visible. */}
      <div className="flex gap-1 mt-4">
        {steps.map((step) => (
          <div
            key={step.step}
            title={step.label}
            className={`h-1.5 flex-1 rounded ${
              done || step.step < session.currentStep
                ? "bg-brand-primary"
                : step.step === session.currentStep
                  ? "bg-brand-primary/50"
                  : "bg-white/10"
            }`}
          />
        ))}
      </div>

      <div className="grid lg:grid-cols-[1fr_24rem] gap-6 mt-6">
        <div className="card overflow-hidden">
          <EcgImage caseId={Number(id)} height={420} label={`Recording ${id}`} />
          <p className="px-5 py-3 text-[11px] text-brand-muted">
            25 mm/s and 10 mm/mV: one large square is 0.2 s and 0.5 mV. Click the trace to enlarge
            it.
          </p>
        </div>

        <div className="space-y-4">
          {error && (
            <div className="rounded border border-brand-danger/40 bg-brand-danger/10 px-4 py-3 text-sm text-brand-danger">
              {error}
            </div>
          )}

          {done ? (
            <div className="card p-5">
              <h2 className="font-semibold">Your interpretation</h2>
              <p className="text-xs text-brand-muted mt-1">
                In your own words. This is read, not marked.
              </p>
              <textarea
                rows={5}
                value={interpretation}
                onChange={(event) => setInterpretation(event.target.value)}
                placeholder="What does this recording show?"
                className="w-full mt-3 bg-brand-bg2 border border-white/10 rounded px-3 py-2 text-sm"
              />
              <button onClick={finish} disabled={busy} className="btn-primary text-sm mt-4 w-full">
                Finish and see results
              </button>
            </div>
          ) : (
            <div className="card p-5">
              <h2 className="font-semibold">
                {currentStep.step}. {currentStep.label}
              </h2>
              {!currentStep.gradable && (
                <p className="text-xs text-brand-warning mt-2">{currentStep.note}</p>
              )}

              <div className="mt-4">
                <AnswerInput
                  step={currentStep}
                  draft={draft}
                  onChange={onDraft}
                  disabled={busy}
                />
              </div>

              <button
                onClick={submit}
                disabled={!answerReady || busy}
                className="btn-primary text-sm mt-5 w-full"
              >
                Submit
              </button>

              {session.attemptsRemaining > 1 && (
                <p className="text-[11px] text-brand-muted mt-2">
                  {session.attemptsRemaining} attempts on this step
                </p>
              )}
            </div>
          )}

          {turn && (
            <div
              className={`card p-5 border ${
                turn.outcome === "CORRECT"
                  ? "border-brand-success/40"
                  : turn.outcome === "NOT_GRADABLE"
                    ? "border-white/10"
                    : "border-brand-warning/40"
              }`}
            >
              <p
                className={`font-semibold text-sm ${
                  turn.outcome === "CORRECT"
                    ? "text-brand-success"
                    : turn.outcome === "NOT_GRADABLE"
                      ? "text-brand-muted"
                      : "text-brand-warning"
                }`}
              >
                {turn.outcome === "CORRECT"
                  ? "Correct"
                  : turn.outcome === "NOT_GRADABLE"
                    ? "Not marked"
                    : turn.feedbackType === "HINT"
                      ? "Not yet — try again"
                      : "Not correct"}
              </p>
              {turn.feedback && <p className="text-sm mt-2">{turn.feedback}</p>}
              {turn.expected !== null && turn.expected !== undefined && (
                <p className="text-sm text-brand-muted mt-3">
                  The recording shows: <span className="font-mono">{String(turn.expected)}</span>
                </p>
              )}
              {turn.feedbackType === "DEFERRED" && (
                <p className="text-xs text-brand-muted mt-2">
                  Examiner mode: your answers are recorded and shown at the end.
                </p>
              )}
              {!turn.facultyApproved && turn.feedback && (
                // Honest about provenance: the fallback library is drafted and
                // not yet read by a clinician.
                <p className="text-[11px] text-brand-muted mt-3">
                  This explanation is a draft awaiting faculty approval.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
