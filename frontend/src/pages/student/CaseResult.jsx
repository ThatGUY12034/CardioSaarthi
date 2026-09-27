import { useLocation, useNavigate, useParams } from "react-router-dom";
import Layout from "../../components/Layout";
import ECGWaveform from "../../components/ECGWaveform";

const STEP_RESULTS = [
  { name: "Rate", yourAnswer: "110 bpm", correct: "77 bpm", score: 0 },
  { name: "Rhythm", yourAnswer: "Irregular", correct: "Regular", score: 0 },
  { name: "P waves", yourAnswer: "Absent", correct: "Present, upright", score: 0 },
  { name: "PR interval", yourAnswer: "Not measurable", correct: "164 ms", score: 60 },
  { name: "QRS complex", yourAnswer: "Narrow", correct: "180 ms (wide)", score: 40 },
  { name: "ST segment", yourAnswer: "Normal", correct: "Anterior elevation V1–V3", score: 0 },
  { name: "T waves", yourAnswer: "Normal", correct: "Inverted in V1–V3", score: 30 },
];

export default function CaseResult() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const answers = location.state?.answers || {};

  const totalScore = Math.round(
    STEP_RESULTS.reduce((sum, s) => sum + s.score, 0) / STEP_RESULTS.length
  );

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
          <h1 className="text-2xl font-bold mt-1">Case {id} — Results</h1>
        </div>
        <div className="text-right">
          <p className="text-xs text-brand-muted">Your Score</p>
          <p
            className={`text-4xl font-bold ${
              totalScore >= 70
                ? "text-brand-success"
                : totalScore >= 40
                ? "text-brand-warning"
                : "text-brand-danger"
            }`}
          >
            {totalScore}%
          </p>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6 mt-6">
        <div className="lg:col-span-2 card p-5">
          <ECGWaveform height={340} label="Reference ECG" />
        </div>

        <div className="card p-5">
          <h3 className="font-semibold mb-4">Step-wise Feedback</h3>
          <ul className="space-y-3">
            {STEP_RESULTS.map((s) => (
              <li key={s.name} className="border-b border-white/5 pb-3 last:border-0">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{s.name}</span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${
                      s.score >= 70
                        ? "bg-brand-success/20 text-brand-success"
                        : s.score >= 40
                        ? "bg-brand-warning/20 text-brand-warning"
                        : "bg-brand-danger/20 text-brand-danger"
                    }`}
                  >
                    {s.score}%
                  </span>
                </div>
                <div className="text-xs mt-1 space-y-0.5">
                  <p className="text-brand-muted">
                    Your answer: <span className="text-white">{answers[s.name] || s.yourAnswer}</span>
                  </p>
                  <p className="text-brand-muted">
                    Correct: <span className="text-brand-accent">{s.correct}</span>
                  </p>
                </div>
              </li>
            ))}
          </ul>

          <button
            onClick={() => navigate("/student/cases")}
            className="btn-primary w-full mt-6 text-sm"
          >
            Next Case →
          </button>
        </div>
      </div>
    </Layout>
  );
}