import Layout from "../../components/Layout";
import ECGWaveform from "../../components/ECGWaveform";

const QUEUE = [
  {
    id: 101,
    case: "Case 12 — Complete Heart Block",
    reason: "Low P-wave confidence (74%)",
    systemNote: "P wave found but could not be delimited confidently on some beats.",
    submittedBy: "Auto-engine",
  },
  {
    id: 102,
    case: "AI Explanation — Anterior STEMI",
    reason: "Low RAG retrieval confidence",
    systemNote: "No verified source found for ST elevation pattern.",
    submittedBy: "AI Tutor",
  },
];

export default function ReviewQueue() {
  return (
    <Layout role="FACULTY">
      <h1 className="text-3xl font-bold">Review Queue</h1>
      <p className="text-brand-muted mt-1">
        Cases and AI explanations requiring faculty approval before student exposure
      </p>

      <div className="grid md:grid-cols-2 gap-6 mt-8">
        {QUEUE.map((item) => (
          <div key={item.id} className="card p-5">
            <ECGWaveform height={140} label={item.case} />
            <div className="mt-4">
              <span className="text-xs px-2 py-1 rounded bg-brand-warning/20 text-brand-warning">
                {item.reason}
              </span>
              <p className="text-xs text-brand-muted mt-3 italic">"{item.systemNote}"</p>
              <p className="text-xs text-brand-muted mt-2">Flagged by: {item.submittedBy}</p>
            </div>
            <div className="flex gap-2 mt-5">
              <button className="btn-primary flex-1 text-sm">Approve</button>
              <button className="btn-ghost flex-1 text-sm">Reject</button>
              <button className="btn-ghost flex-1 text-sm">Edit</button>
            </div>
          </div>
        ))}
      </div>
    </Layout>
  );
}