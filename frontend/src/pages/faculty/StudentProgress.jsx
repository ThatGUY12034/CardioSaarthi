import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import Layout from "../../components/Layout";
import CaseEcg from "../../components/CaseEcg";

/**
 * One student's completed cases, read like a book.
 *
 * <p>Two facing pages per case: the recording on the left, what the platform
 * computed on the right. The pairing is the point -- a reviewer looking at a
 * student's score should see the trace that score was earned against, not a
 * number on its own.
 *
 * <p>The cases here are illustrative, like the cohort table that leads to this
 * page, and the interface says so. The nine parameters are laid out in the
 * order of the interpretation sequence, which is the order the student answered
 * them in.
 */

const STUDENTS = {
  1: { name: "Aarav Patel", collegeId: "TE23CS001", avg: 92, streak: 7, band: "High" },
  2: { name: "Sneha Iyer", collegeId: "TE23CS015", avg: 88, streak: 5, band: "High" },
  3: { name: "Rohan Shah", collegeId: "TE23CS022", avg: 85, streak: 4, band: "High" },
  4: { name: "Isha Desai", collegeId: "TE23CS034", avg: 87, streak: 6, band: "High" },
  5: { name: "Vivaan Kulkarni", collegeId: "TE23CS008", avg: 90, streak: 8, band: "High" },
  6: { name: "Aditya Nair", collegeId: "TE23CS041", avg: 78, streak: 3, band: "Medium" },
  7: { name: "Meera Joshi", collegeId: "TE23CS047", avg: 75, streak: 2, band: "Medium" },
  8: { name: "Riya Deshmukh", collegeId: "TE23CS012", avg: 74, streak: 3, band: "Medium" },
  9: { name: "Arjun Pillai", collegeId: "TE23CS029", avg: 72, streak: 2, band: "Medium" },
  10: { name: "Nikita Rane", collegeId: "TE23CS036", avg: 71, streak: 4, band: "Medium" },
  11: { name: "Sahil Qureshi", collegeId: "TE23CS044", avg: 70, streak: 1, band: "Medium" },
  12: { name: "Tanvi Bhosale", collegeId: "TE23CS019", avg: 68, streak: 2, band: "Medium" },
  13: { name: "Omkar Sawant", collegeId: "TE23CS051", avg: 66, streak: 1, band: "Medium" },
  14: { name: "Kabir Menon", collegeId: "TE23CS052", avg: 58, streak: 1, band: "Low" },
  15: { name: "Ananya Rao", collegeId: "TE23CS060", avg: 54, streak: 0, band: "Low" },
  16: { name: "Zoya Shaikh", collegeId: "TE23CS063", avg: 51, streak: 0, band: "Low" },
  17: { name: "Harsh Gupta", collegeId: "TE23CS068", avg: 47, streak: 1, band: "Low" },
};

const CASES = [
  {
    number: 3,
    title: "Atrial Fibrillation",
    score: 85,
    findings: [
      ["Heart Rate", "120 bpm (Irregular)"],
      ["Rhythm", "Irregularly irregular"],
      ["P Waves", "Absent"],
      ["QRS", "Narrow"],
      ["ST Segment", "Normal"],
      ["T Waves", "Normal"],
    ],
  },
  {
    number: 4,
    title: "Sinus Bradycardia",
    score: 92,
    findings: [
      ["Heart Rate", "48 bpm"],
      ["Rhythm", "Regular"],
      ["P Waves", "Present, one per QRS"],
      ["QRS", "Narrow"],
      ["ST Segment", "Normal"],
      ["T Waves", "Upright"],
    ],
  },
  {
    number: 5,
    title: "First-degree AV block",
    score: 78,
    findings: [
      ["Heart Rate", "72 bpm"],
      ["Rhythm", "Regular"],
      ["PR Interval", "248 ms (prolonged)"],
      ["QRS", "Narrow"],
      ["ST Segment", "Normal"],
      ["T Waves", "Upright"],
    ],
  },
];

const BAND_STYLE = {
  High: "bg-brand-success/20 text-brand-success",
  Medium: "bg-brand-warning/20 text-brand-warning",
  Low: "bg-brand-danger/20 text-brand-danger",
};

export default function StudentProgress() {
  const { id } = useParams();
  const student = STUDENTS[id] || STUDENTS[1];
  const [page, setPage] = useState(0);
  const current = CASES[page];

  const scoreTone =
    current.score >= 85
      ? "text-brand-success"
      : current.score >= 70
        ? "text-brand-warning"
        : "text-brand-danger";

  return (
    <Layout role="FACULTY">
      <Link to="/faculty/students" className="text-sm text-brand-accent hover:underline">
        ← Back to Students
      </Link>

      <h1 className="text-3xl font-bold mt-3">Student Progress</h1>

      <div className="card p-5 mt-6 flex flex-wrap items-center gap-4">
        <span
          className={`w-12 h-12 rounded-full grid place-items-center font-semibold ${BAND_STYLE[student.band]}`}
          aria-hidden="true"
        >
          {student.name
            .split(" ")
            .map((part) => part[0])
            .slice(0, 2)
            .join("")}
        </span>
        <div className="flex-1 min-w-[200px]">
          <h2 className="font-semibold text-lg">{student.name}</h2>
          <p className="text-sm text-brand-muted">
            {student.collegeId} · Terna Engineering College
          </p>
        </div>
        <span className={`text-xs px-3 py-1 rounded-full ${BAND_STYLE[student.band]}`}>
          {student.band} performance
        </span>
        <div className="flex gap-6 text-sm">
          <span>
            <span className="block text-xs text-brand-muted">Avg. score</span>
            <strong>{student.avg}%</strong>
          </span>
          <span>
            <span className="block text-xs text-brand-muted">Streak</span>
            <strong>{student.streak} days</strong>
          </span>
        </div>
      </div>

      {/* The spread. One border down the middle is the whole illusion. */}
      <div className="card mt-6 overflow-hidden">
        <div className="grid md:grid-cols-2 md:divide-x divide-white/10">
          <div className="p-6">
            <p className="text-xs text-brand-muted uppercase tracking-wide">
              Case {current.number}
            </p>
            <h3 className="font-semibold text-lg mt-1">{current.title}</h3>

            <div className="mt-4">
              <CaseEcg height={200} label={`Recording reviewed in case ${current.number}`} />
            </div>

            <div className="flex items-end justify-between mt-5">
              <span>
                <span className="block text-xs text-brand-muted">Their score</span>
                <strong className={`text-3xl ${scoreTone}`}>{current.score}%</strong>
              </span>
              <button type="button" className="btn-ghost text-sm">
                View details
              </button>
            </div>
          </div>

          <div className="p-6">
            <h3 className="font-semibold text-lg">Case analysis</h3>
            <p className="text-sm text-brand-muted mt-1">
              What the platform computed from the recording.
            </p>

            <dl className="mt-5 space-y-3">
              {current.findings.map(([name, value]) => (
                <div
                  key={name}
                  className="flex items-baseline justify-between gap-4 border-b border-white/5 pb-3"
                >
                  <dt className="text-sm text-brand-muted">{name}</dt>
                  <dd className="text-sm font-medium text-right">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>

        <div className="flex items-center justify-between px-6 py-4 border-t border-white/5">
          <button
            type="button"
            onClick={() => setPage((n) => Math.max(0, n - 1))}
            disabled={page === 0}
            className="btn-ghost text-sm disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ← Previous
          </button>

          <div className="flex gap-2" role="tablist" aria-label="Cases">
            {CASES.map((item, index) => (
              <button
                key={item.number}
                type="button"
                role="tab"
                aria-selected={index === page}
                aria-label={`Case ${item.number}`}
                onClick={() => setPage(index)}
                className={`w-2 h-2 rounded-full transition ${
                  index === page ? "bg-brand-primary w-6" : "bg-white/20 hover:bg-white/40"
                }`}
              />
            ))}
          </div>

          <button
            type="button"
            onClick={() => setPage((n) => Math.min(CASES.length - 1, n + 1))}
            disabled={page === CASES.length - 1}
            className="btn-ghost text-sm disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Next →
          </button>
        </div>
      </div>

      <p className="text-xs text-brand-muted mt-4">
        Sample cases, shown to demonstrate the layout. Real entries appear here once
        students complete sessions against approved cases.
      </p>
    </Layout>
  );
}
