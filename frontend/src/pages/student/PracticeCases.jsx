import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import ECGWaveform from "../../components/ECGWaveform";
import { useState } from "react";

const MOCK_CASES = [
  { id: 1, title: "Case 1 - Normal Sinus Rhythm", difficulty: "Easy", category: "Rhythm" },
  { id: 2, title: "Case 2 - Atrial Fibrillation", difficulty: "Medium", category: "Rhythm" },
  { id: 3, title: "Case 3 - Atrial Fibrillation", difficulty: "Medium", category: "Rhythm" },
  { id: 4, title: "Case 4 - Anterior STEMI", difficulty: "Hard", category: "Ischemia" },
  { id: 5, title: "Case 5 - Complete Heart Block", difficulty: "Hard", category: "Conduction" },
  { id: 6, title: "Case 6 - Sinus Bradycardia", difficulty: "Medium", category: "Rhythm" },
];

const diffColor = {
  Easy: "text-brand-success bg-brand-success/10",
  Medium: "text-brand-warning bg-brand-warning/10",
  Hard: "text-brand-danger bg-brand-danger/10",
};

export default function PracticeCases() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState("All");

  const filtered =
    filter === "All" ? MOCK_CASES : MOCK_CASES.filter((c) => c.difficulty === filter);

  return (
    <Layout role="STUDENT">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold">Practice Cases</h1>
          <p className="text-brand-muted mt-1">Choose a case to begin interpretation</p>
        </div>
        <div className="flex gap-2">
          {["All", "Easy", "Medium", "Hard"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-2 rounded-lg text-sm ${
                filter === f
                  ? "bg-brand-primary text-white"
                  : "bg-brand-card text-brand-muted hover:bg-brand-cardLight"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mt-8">
        {filtered.map((c) => (
          <div key={c.id} className="card overflow-hidden hover:border-brand-primary/50 transition-colors">
            <ECGWaveform height={140} />
            <div className="p-5">
              <div className="flex items-center justify-between">
                <span className={`text-xs px-2 py-1 rounded ${diffColor[c.difficulty]}`}>
                  {c.difficulty}
                </span>
                <span className="text-xs text-brand-muted">{c.category}</span>
              </div>
              <h3 className="font-semibold mt-3">{c.title}</h3>
              <button
                onClick={() => navigate(`/student/cases/${c.id}`)}
                className="btn-primary w-full mt-5 text-sm"
              >
                Start Case
              </button>
            </div>
          </div>
        ))}
      </div>
    </Layout>
  );
}