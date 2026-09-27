import Layout from "../../components/Layout";
import { useState } from "react";

const TERMS = [
  { q: "What is an ECG?", a: "An ECG (electrocardiogram) is a test that records the electrical activity of your heart. It helps doctors check your heart rhythm and detect problems." },
  { q: "Heart Rate", a: "The number of times your heart beats per minute. A normal resting heart rate is usually between 60 and 100 bpm." },
  { q: "Rhythm", a: "The pattern of your heartbeat. A 'regular' rhythm means the beats are evenly spaced." },
  { q: "P Waves", a: "A small wave on the ECG that shows the upper chambers of the heart (atria) contracting." },
  { q: "QRS Complex", a: "A sharp spike on the ECG that shows the lower chambers (ventricles) contracting." },
  { q: "ST Segment", a: "The flat section between the QRS and T waves. Changes here can indicate heart strain or a heart attack." },
  { q: "T Waves", a: "A wave that follows the QRS complex, showing the ventricles resetting for the next beat." },
];

export default function Glossary() {
  const [open, setOpen] = useState(null);

  return (
    <Layout role="PATIENT">
      <h1 className="text-3xl font-bold">ECG Terminology</h1>
      <p className="text-brand-muted mt-1">Understand the basics of your report</p>

      <div className="mt-8 space-y-3 max-w-3xl">
        {TERMS.map((t, i) => (
          <div key={t.q} className="card overflow-hidden">
            <button
              onClick={() => setOpen(open === i ? null : i)}
              className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-white/5"
            >
              <span className="font-medium">{t.q}</span>
              <span className="text-brand-accent text-xl">{open === i ? "−" : "+"}</span>
            </button>
            {open === i && (
              <div className="px-5 pb-5 text-sm text-brand-muted leading-relaxed">
                {t.a}
              </div>
            )}
          </div>
        ))}
      </div>
    </Layout>
  );
}