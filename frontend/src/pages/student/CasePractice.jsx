import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import ECGWaveform from "../../components/ECGWaveform";

const STEPS = ["Rate", "Rhythm", "P waves", "PR interval", "QRS complex", "ST segment", "T waves"];

export default function CasePractice() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [timeLeft, setTimeLeft] = useState(600);
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState({});
  const [current, setCurrent] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (timeLeft <= 0) return;
    const t = setInterval(() => setTimeLeft((s) => s - 1), 1000);
    return () => clearInterval(t);
  }, [timeLeft]);

  const formatTime = (s) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  };

  const handleNext = () => {
    setAnswers({ ...answers, [STEPS[step]]: current });
    setCurrent("");
    if (step < STEPS.length - 1) setStep(step + 1);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    const final = { ...answers, [STEPS[step]]: current };
    // TODO: POST to /api/submissions { caseId: id, answers: final }
    setTimeout(() => {
      navigate(`/student/cases/${id}/result`, { state: { answers: final } });
    }, 800);
  };

  return (
    <Layout role="STUDENT">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <button
            onClick={() => navigate("/student/cases")}
            className="text-xs text-brand-muted hover:text-white"
          >
            ← Back to Cases
          </button>
          <h1 className="text-2xl font-bold mt-1">Case {id} - Sinus Bradycardia</h1>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-brand-muted">Time Left: {formatTime(timeLeft)}</span>
          <button onClick={handleSubmit} disabled={submitting} className="btn-primary text-sm">
            {submitting ? "Submitting..." : "Submit"}
          </button>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6 mt-6">
        <div className="lg:col-span-2 card p-5">
          <ECGWaveform height={380} label="12-Lead ECG — 25 mm/s, 10 mm/mV" />
        </div>

        <div className="space-y-5">
          <div className="card p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-sm">Step {step + 1} of {STEPS.length}</h3>
              <span className="text-xs text-brand-accent">{STEPS[step]}</span>
            </div>
            <div className="w-full h-1.5 bg-brand-cardLight rounded-full overflow-hidden mb-4">
              <div
                className="h-full bg-brand-primary transition-all"
                style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
              />
            </div>
            <label className="text-xs text-brand-muted">Your Interpretation</label>
            <textarea
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              placeholder={`Enter your interpretation for ${STEPS[step]}...`}
              className="input-field mt-2 min-h-[100px] resize-none"
            />
            <button
              onClick={handleNext}
              disabled={!current}
              className="btn-primary w-full mt-3 text-sm disabled:opacity-40"
            >
              {step === STEPS.length - 1 ? "Review" : "Next Step →"}
            </button>
          </div>

          <div className="card p-5">
            <h3 className="font-semibold text-sm mb-3">Guiding Points</h3>
            <ul className="text-xs text-brand-muted space-y-2">
              {STEPS.map((s, i) => (
                <li
                  key={s}
                  className={`flex items-center gap-2 ${i === step ? "text-brand-accent" : ""}`}
                >
                  <span>{i < step ? "✓" : i === step ? "▸" : "○"}</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </Layout>
  );
}