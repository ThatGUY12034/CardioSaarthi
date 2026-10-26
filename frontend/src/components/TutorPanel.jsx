import { useState } from "react";
import { askTutor } from "../api/tutorApi";
import { InlineError } from "./States";

/**
 * Ask about the concept, not about the case.
 *
 * <p>The tutor explains what a PR interval is; it does not read the trace in
 * front of the student. That separation is the whole design: measurements come
 * from the engine and are gated behind faculty approval, and nothing retrieved
 * from a library may contradict them by describing this recording.
 *
 * <p>Every answer shows where it came from. An answer with no citation is a
 * refusal, and a refusal says what to do about it, because "no approved source
 * covers that" is useful and silence is not.
 */
export default function TutorPanel({ concept, label, sessionId }) {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const ask = async (text) => {
    const asked = (text ?? question).trim();
    if (!asked) return;
    setBusy(true);
    setError(null);
    try {
      setAnswer(await askTutor(asked, concept, sessionId));
    } catch {
      setError("The tutor could not be reached. Your answers are unaffected.");
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="btn-ghost text-sm w-full"
      >
        Ask about {label ?? "this step"}
      </button>
    );
  }

  return (
    <div className="card p-5">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-semibold text-sm">Ask about {label ?? "this step"}</h2>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="text-xs text-brand-muted hover:text-brand-text"
        >
          Close
        </button>
      </div>
      <p className="text-[11px] text-brand-muted mt-1">
        Answered from faculty-approved reference material. It explains the concept, not this
        recording.
      </p>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          ask();
        }}
        className="mt-3 flex gap-2"
      >
        <label className="sr-only" htmlFor="tutor-question">
          Your question
        </label>
        <input
          id="tutor-question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          maxLength={300}
          placeholder={`What is ${label?.toLowerCase() ?? "this"}?`}
          className="flex-1 bg-brand-bg2 border border-white/10 rounded-lg px-3 py-2 text-sm"
        />
        <button type="submit" disabled={busy || !question.trim()} className="btn-primary text-sm">
          {busy ? "…" : "Ask"}
        </button>
      </form>

      {error && <div className="mt-3"><InlineError message={error} /></div>}

      {answer && (
        <div className="mt-4">
          {answer.refused ? (
            <p className="text-sm text-brand-muted italic">{answer.text}</p>
          ) : (
            <>
              <p className="text-sm leading-relaxed whitespace-pre-line">{answer.text}</p>
              <div className="mt-4 pt-3 border-t border-white/5">
                <p className="text-[11px] text-brand-muted mb-1">Sources</p>
                <ul className="space-y-1">
                  {answer.citations.map((c) => (
                    <li key={c.id} className="text-[11px] text-brand-muted">
                      <a
                        href={c.sourceUrl}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="text-brand-accent hover:underline"
                      >
                        {c.sourceTitle}
                      </a>
                      {" — "}
                      {c.sourcePublisher}, {c.sourceLicence}
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
