import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import EcgImage from "../../components/EcgImage";
import { EmptyState, InlineError, SkeletonGrid } from "../../components/States";
import { errorMessage, getPractisableCases } from "../../api/studyApi";

/**
 * The cases a student may practise on.
 *
 * <p>Every one has been approved by a named reviewer. An unapproved case cannot
 * appear here and cannot be started even if its id is typed into the address
 * bar: the server refuses it and a database trigger refuses it again.
 *
 * <p>No difficulty rating is shown. The platform does not have one -- difficulty
 * would have to come from how students actually perform, and no student has used
 * it yet. Inventing three tiers and colouring them would be making it up.
 */

const MODES = [
  {
    value: "BEGINNER_TUTOR",
    label: "Tutor",
    blurb: "A hint on the first wrong answer, then the full explanation.",
  },
  {
    value: "CLINICAL_MENTOR",
    label: "Mentor",
    blurb: "One attempt per step, then the explanation and move on.",
  },
  {
    value: "EXAMINER",
    label: "Examiner",
    blurb: "No feedback until the end of the case.",
  },
];

export default function PracticeCases() {
  const navigate = useNavigate();
  const [cases, setCases] = useState(null);
  const [mode, setMode] = useState("BEGINNER_TUTOR");
  // Off by default, and that is the point. The condition on a card is the
  // answer to step 2: a card reading "atrial fibrillation" tells the student
  // the rhythm before they have looked at the trace. A student who wants to
  // drill one topic can still ask for it; nobody is handed it unasked.
  const [revealTopics, setRevealTopics] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getPractisableCases()
      .then((loaded) => {
        if (!cancelled) setCases(loaded);
      })
      .catch((exception) => {
        if (!cancelled) setError(errorMessage(exception, "Could not load the case list."));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Layout role="STUDENT">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold">Practice Cases</h1>
          <p className="text-brand-muted mt-1">
            Real recordings, each checked by a member of faculty before it reached you.
          </p>
        </div>

        <div>
          <p className="text-xs text-brand-muted mb-2">How much help do you want?</p>
          <div className="flex gap-2">
            {MODES.map((option) => (
              <button
                key={option.value}
                onClick={() => setMode(option.value)}
                title={option.blurb}
                className={`px-4 py-2 rounded-lg text-sm border ${
                  mode === option.value
                    ? "border-brand-primary text-white"
                    : "border-white/10 text-brand-muted"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-brand-muted mt-2 max-w-xs">
            {MODES.find((option) => option.value === mode).blurb}
          </p>

          <label className="flex items-center gap-2 mt-3 text-[11px] text-brand-muted cursor-pointer">
            <input
              type="checkbox"
              checked={revealTopics}
              onChange={(event) => setRevealTopics(event.target.checked)}
              className="accent-brand-primary"
            />
            Show what each case covers (reveals the answer)
          </label>
        </div>
      </div>

      {error && <div className="mt-6"><InlineError message={error} /></div>}

      {cases === null ? (
        <SkeletonGrid className="mt-8" count={6} />
      ) : cases.length === 0 ? (
        <EmptyState
          className="mt-8"
          title="No cases are available yet"
          description="A case becomes available once a member of faculty has reviewed and approved it. Nothing unreviewed can reach you, which is why this list can be empty while the bank is full."
        />
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6 mt-8">
          {cases.map((item) => (
            <div key={item.caseId} className="card overflow-hidden flex flex-col">
              <EcgImage caseId={item.caseId} height={140} zoomable={false} />
              <div className="p-5 flex-1 flex flex-col">
                <h3 className="font-semibold">Recording {item.sourceEcgId}</h3>
                <p className="text-xs text-brand-muted mt-1">
                  {item.sex}
                  {item.age ? `, ${Math.round(item.age)} years` : ""}
                </p>
                {/* Hidden unless asked for. These codes name the condition --
                    "atrial fibrillation" is the answer to step 2 -- so printing
                    them beside the trace answers the question the student is
                    about to be examined on. Choosing what to practise is a real
                    need, so it stays available behind a deliberate click. */}
                {revealTopics && item.conditionCodes.length > 0 && (
                  <p className="text-[11px] text-brand-warning/80 mt-2">
                    {item.conditionCodes.map((code) => code.replace(/_/g, " ")).join(" · ")}
                  </p>
                )}
                <button
                  onClick={() =>
                    navigate(`/student/cases/${item.caseId}`, { state: { mode } })
                  }
                  className="btn-primary text-sm mt-4 w-full"
                >
                  Start
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
}
