import Layout from "../../components/Layout";
import CaseEcg from "../../components/CaseEcg";

const KEY_TERMS = [
  { term: "Heart Rate", value: "60–100 bpm (Normal)" },
  { term: "Rhythm", value: "Regular" },
  { term: "QRS Complex", value: "Narrow" },
  { term: "ST Segment", value: "Normal" },
];

export default function ReportExplanation() {
  return (
    <Layout role="PATIENT">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-bold">Your ECG Report</h1>
          <p className="text-brand-muted mt-1">Report Date: 27 Apr 2026</p>
        </div>
        <button className="btn-ghost text-sm">⬇ Download PDF</button>
      </div>

      <div className="grid lg:grid-cols-3 gap-6 mt-8">
        <div className="lg:col-span-2 card p-5">
          <CaseEcg height={300} label="Your ECG" />
        </div>

        <div className="card p-6">
          <h3 className="font-semibold">Simple Explanation</h3>
          <p className="text-sm text-brand-muted mt-3 leading-relaxed">
            Your ECG shows a normal heart rhythm. The heart is beating at a regular
            rate and the electrical activity looks normal.
          </p>
          <span className="inline-block text-xs px-3 py-1 rounded-full bg-brand-success/20 text-brand-success mt-4">
            ● Normal
          </span>
        </div>
      </div>

      <div className="card p-6 mt-6">
        <h3 className="font-semibold mb-4">Key Terms</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {KEY_TERMS.map((t) => (
            <div key={t.term} className="bg-brand-cardLight rounded-lg p-4">
              <p className="text-xs text-brand-muted">{t.term}</p>
              <p className="text-sm font-medium mt-1">{t.value}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="card p-5 mt-6 border-l-4 border-brand-warning">
        <p className="text-xs text-brand-muted">
          ⚠ This is a simplified explanation for educational purposes. Always consult your
          doctor for a complete medical evaluation.
        </p>
      </div>
    </Layout>
  );
}