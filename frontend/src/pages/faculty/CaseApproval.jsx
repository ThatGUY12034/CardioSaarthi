import Layout from "../../components/Layout";
import ECGWaveform from "../../components/ECGWaveform";

const PENDING = [
  { id: 1, title: "Case 18 — Ventricular Tachycardia", difficulty: "Hard" },
  { id: 2, title: "Case 19 — 2nd Degree AV Block", difficulty: "Hard" },
  { id: 3, title: "Case 20 — Atrial Flutter", difficulty: "Medium" },
];

export default function CaseApproval() {
  return (
    <Layout role="FACULTY">
      <h1 className="text-3xl font-bold">Case Approval</h1>
      <p className="text-brand-muted mt-1">Review and approve new ECG cases before publishing</p>

      <div className="grid md:grid-cols-3 gap-6 mt-8">
        {PENDING.map((c) => (
          <div key={c.id} className="card overflow-hidden">
            <ECGWaveform height={140} />
            <div className="p-5">
              <h3 className="font-semibold">{c.title}</h3>
              <p className="text-xs text-brand-muted mt-1">{c.difficulty}</p>
              <div className="flex gap-2 mt-4">
                <button className="btn-primary flex-1 text-xs">Approve</button>
                <button className="btn-ghost flex-1 text-xs">Reject</button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </Layout>
  );
}