import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";

/**
 * The cohort at a glance, and the way into one student's work.
 *
 * <p>The rows are illustrative. Real cohort analytics need sessions from real
 * students, and there are none yet -- what the platform can compute today is a
 * single student's own progress, which the student pages already show from the
 * runtime. Rather than invent a number and present it as measured, this page is
 * marked as sample data in the interface itself, so nobody in a room has to ask.
 */

const STUDENTS = [
  { id: 1, name: "Aarav Patel", collegeId: "TE23CS001", college: "Terna Engg. College", avg: 92, streak: 7, band: "High" },
  { id: 2, name: "Sneha Iyer", collegeId: "TE23CS015", college: "Terna Engg. College", avg: 88, streak: 5, band: "High" },
  { id: 3, name: "Rohan Shah", collegeId: "TE23CS022", college: "Terna Engg. College", avg: 85, streak: 4, band: "High" },
  { id: 4, name: "Isha Desai", collegeId: "TE23CS034", college: "Terna Engg. College", avg: 87, streak: 6, band: "High" },
  { id: 5, name: "Vivaan Kulkarni", collegeId: "TE23CS008", college: "Terna Engg. College", avg: 90, streak: 8, band: "High" },
  { id: 6, name: "Aditya Nair", collegeId: "TE23CS041", college: "Terna Engg. College", avg: 78, streak: 3, band: "Medium" },
  { id: 7, name: "Meera Joshi", collegeId: "TE23CS047", college: "Terna Engg. College", avg: 75, streak: 2, band: "Medium" },
  { id: 8, name: "Riya Deshmukh", collegeId: "TE23CS012", college: "Terna Engg. College", avg: 74, streak: 3, band: "Medium" },
  { id: 9, name: "Arjun Pillai", collegeId: "TE23CS029", college: "Terna Engg. College", avg: 72, streak: 2, band: "Medium" },
  { id: 10, name: "Nikita Rane", collegeId: "TE23CS036", college: "Terna Engg. College", avg: 71, streak: 4, band: "Medium" },
  { id: 11, name: "Sahil Qureshi", collegeId: "TE23CS044", college: "Terna Engg. College", avg: 70, streak: 1, band: "Medium" },
  { id: 12, name: "Tanvi Bhosale", collegeId: "TE23CS019", college: "Terna Engg. College", avg: 68, streak: 2, band: "Medium" },
  { id: 13, name: "Omkar Sawant", collegeId: "TE23CS051", college: "Terna Engg. College", avg: 66, streak: 1, band: "Medium" },
  { id: 14, name: "Kabir Menon", collegeId: "TE23CS052", college: "Terna Engg. College", avg: 58, streak: 1, band: "Low" },
  { id: 15, name: "Ananya Rao", collegeId: "TE23CS060", college: "Terna Engg. College", avg: 54, streak: 0, band: "Low" },
  { id: 16, name: "Zoya Shaikh", collegeId: "TE23CS063", college: "Terna Engg. College", avg: 51, streak: 0, band: "Low" },
  { id: 17, name: "Harsh Gupta", collegeId: "TE23CS068", college: "Terna Engg. College", avg: 47, streak: 1, band: "Low" },
];

const BAND_STYLE = {
  High: "bg-brand-success/20 text-brand-success",
  Medium: "bg-brand-warning/20 text-brand-warning",
  Low: "bg-brand-danger/20 text-brand-danger",
};

/** Initials rather than a photograph: the platform holds no student pictures. */
function Avatar({ name, band }) {
  const initials = name
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("");
  const tint = {
    High: "bg-brand-success/20 text-brand-success",
    Medium: "bg-brand-warning/20 text-brand-warning",
    Low: "bg-brand-danger/20 text-brand-danger",
  }[band];
  return (
    <span
      className={`w-8 h-8 shrink-0 rounded-full grid place-items-center text-[11px] font-semibold ${tint}`}
      aria-hidden="true"
    >
      {initials}
    </span>
  );
}

export default function StudentPerformance() {
  const navigate = useNavigate();
  const [band, setBand] = useState("High");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("name");

  const counts = useMemo(
    () =>
      STUDENTS.reduce((tally, student) => {
        tally[student.band] = (tally[student.band] || 0) + 1;
        return tally;
      }, {}),
    []
  );

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = STUDENTS.filter(
      (student) =>
        student.band === band &&
        (needle === "" ||
          student.name.toLowerCase().includes(needle) ||
          student.collegeId.toLowerCase().includes(needle))
    );
    const ordered = [...filtered];
    // Score and streak descend: the interesting end of each is the top.
    if (sort === "score") ordered.sort((a, b) => b.avg - a.avg);
    else if (sort === "streak") ordered.sort((a, b) => b.streak - a.streak);
    else ordered.sort((a, b) => a.name.localeCompare(b.name));
    return ordered;
  }, [band, query, sort]);

  return (
    <Layout role="FACULTY">
      <h1 className="text-3xl font-bold">Student Performance</h1>
      <p className="text-brand-muted mt-1">Monitor individual and cohort progress</p>

      <div className="mt-6 inline-flex rounded-lg bg-brand-card p-1 gap-1">
        {["High", "Medium", "Low"].map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => setBand(option)}
            className={`px-4 py-2 rounded-md text-sm transition ${
              band === option
                ? "bg-brand-cardLight text-brand-text"
                : "text-brand-muted hover:text-brand-text"
            }`}
          >
            {option} ({counts[option] || 0})
          </button>
        ))}
      </div>

      <div className="card mt-5 overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 px-5 py-4 border-b border-white/5">
          <label className="flex-1 min-w-[200px] relative">
            <span className="sr-only">Search students</span>
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-brand-muted text-sm">
              ⌕
            </span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search students..."
              className="w-full bg-brand-bg2 rounded-lg pl-8 pr-3 py-2 text-sm outline-none focus:ring-1 focus:ring-brand-primary"
            />
          </label>
          <label className="flex items-center gap-2 text-sm text-brand-muted">
            Sort by:
            <select
              value={sort}
              onChange={(event) => setSort(event.target.value)}
              className="bg-brand-bg2 rounded-lg px-3 py-2 text-brand-text outline-none focus:ring-1 focus:ring-brand-primary"
            >
              <option value="name">Name</option>
              <option value="score">Avg. Score</option>
              <option value="streak">Streak</option>
            </select>
          </label>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[720px]">
            <thead className="bg-brand-cardLight text-brand-muted text-xs uppercase">
              <tr>
                <th className="text-left px-5 py-3 font-medium">Name</th>
                <th className="text-left px-5 py-3 font-medium">College ID</th>
                <th className="text-left px-5 py-3 font-medium">College</th>
                <th className="text-left px-5 py-3 font-medium">Avg. Score</th>
                <th className="text-left px-5 py-3 font-medium">Streak</th>
                <th className="text-left px-5 py-3 font-medium">Band</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((student) => (
                <tr
                  key={student.collegeId}
                  onClick={() => navigate(`/faculty/students/${student.id}`)}
                  className="border-t border-white/5 hover:bg-white/5 cursor-pointer"
                >
                  <td className="px-5 py-4">
                    <span className="flex items-center gap-3 font-medium">
                      <Avatar name={student.name} band={student.band} />
                      {student.name}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-brand-muted">{student.collegeId}</td>
                  <td className="px-5 py-4 text-brand-muted">{student.college}</td>
                  <td className="px-5 py-4">{student.avg}%</td>
                  <td className="px-5 py-4">🔥 {student.streak} days</td>
                  <td className="px-5 py-4">
                    <span className={`text-xs px-2 py-1 rounded ${BAND_STYLE[student.band]}`}>
                      {student.band}
                    </span>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-10 text-center text-brand-muted">
                    No student in this band matches “{query}”.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-xs text-brand-muted mt-4">
        Sample cohort. Cohort analytics need sessions from real students; a single
        student's own progress is computed from the runtime and shown on their pages.
      </p>
    </Layout>
  );
}
