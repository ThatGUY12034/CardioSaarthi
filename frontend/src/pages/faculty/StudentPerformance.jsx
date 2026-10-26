import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import { EmptyState, ErrorState, SkeletonRows } from "../../components/States";
import { getCohortErrors, getDifficulty, getStudents } from "../../api/cohortApi";
import { errorMessage } from "../../api/studyApi";

/**
 * The class, from the attempt record.
 *
 * <p>This page showed seventeen invented students until now. Every figure on it
 * is the same arithmetic the student sees on their own pages, because a teacher
 * and a student getting different numbers for the same thing is worse than
 * either of them having no number.
 *
 * <p>Two things a teacher actually wants are here rather than buried: which
 * concept each student is weakest at, so the list itself suggests what to say,
 * and what the class as a whole finds hard, which is what to teach next.
 */

function timeAgo(iso) {
  if (!iso) return "never";
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days} days ago`;
  return new Date(iso).toLocaleDateString();
}

const accuracyTone = (pct) =>
  pct === null || pct === undefined
    ? "text-brand-muted"
    : pct >= 80
      ? "text-brand-success"
      : pct >= 60
        ? "text-brand-warning"
        : "text-brand-danger";

export default function StudentPerformance() {
  const navigate = useNavigate();
  const [students, setStudents] = useState(null);
  const [difficulty, setDifficulty] = useState([]);
  const [errors, setErrors] = useState([]);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getStudents(), getDifficulty(), getCohortErrors(8)])
      .then(([s, d, e]) => {
        if (cancelled) return;
        setStudents(s);
        setDifficulty(d);
        setErrors(e);
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e, "Could not load the class."));
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const rows = useMemo(() => {
    if (!students) return null;
    const needle = query.trim().toLowerCase();
    if (!needle) return students;
    return students.filter(
      (s) =>
        s.fullName.toLowerCase().includes(needle) ||
        (s.collegeId || "").toLowerCase().includes(needle)
    );
  }, [students, query]);

  if (error) {
    return (
      <Layout role="FACULTY">
        <h1 className="page-title">Student Performance</h1>
        <div className="mt-8">
          <ErrorState message={error} onRetry={() => setReloadKey((n) => n + 1)} />
        </div>
      </Layout>
    );
  }

  const hardest = difficulty
    .filter((d) => d.attempts > 0)
    .slice()
    .sort((a, b) => (a.firstAttemptAccuracyPct ?? 101) - (b.firstAttemptAccuracyPct ?? 101));

  return (
    <Layout role="FACULTY">
      <h1 className="page-title">Student Performance</h1>
      <p className="page-subtitle">
        From what your students have actually answered. Click a student to see their mistakes
        and leave a remark.
      </p>

      {/* What to teach next lesson, which is the question a class view exists to answer. */}
      {hardest.length > 0 && (
        <div className="grid lg:grid-cols-2 gap-6 mt-8">
          <div className="card p-5">
            <h2 className="font-semibold text-sm">Hardest steps for this class</h2>
            <p className="text-[11px] text-brand-muted mt-1">
              Correct on the first attempt, across every student.
            </p>
            <ul className="mt-4 space-y-2">
              {hardest.slice(0, 5).map((d) => (
                <li key={d.step} className="flex items-center justify-between gap-3 text-sm">
                  <span>
                    <span className="text-brand-muted mr-2">{d.step}.</span>
                    {d.label}
                  </span>
                  <span className={`tabular ${accuracyTone(d.firstAttemptAccuracyPct)}`}>
                    {d.firstAttemptAccuracyPct === null
                      ? "—"
                      : `${d.firstAttemptAccuracyPct}%`}
                    <span className="text-brand-muted ml-2">({d.attempts} attempts)</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="card p-5">
            <h2 className="font-semibold text-sm">Most common mistakes</h2>
            <p className="text-[11px] text-brand-muted mt-1">
              Named errors, not a count of wrong answers.
            </p>
            {errors.length === 0 ? (
              <p className="text-sm text-brand-muted mt-4">
                No mistakes recorded yet.
              </p>
            ) : (
              <ul className="mt-4 space-y-2">
                {errors.slice(0, 5).map((e) => (
                  <li key={e.code} className="text-sm">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="text-brand-muted text-xs">{e.stepLabel}</span>
                      <span className="tabular text-xs text-brand-muted">
                        {e.occurrences}× · {e.studentsAffected} student
                        {e.studentsAffected === 1 ? "" : "s"}
                      </span>
                    </div>
                    <p className="leading-snug">{e.description}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      <div className="flex items-center gap-3 mt-8">
        <label className="flex-1 max-w-sm">
          <span className="sr-only">Search students</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by name or college ID…"
            className="w-full bg-brand-bg2 rounded-lg px-3 py-2 text-sm"
          />
        </label>
      </div>

      {rows === null ? (
        <SkeletonRows className="mt-4" count={5} />
      ) : rows.length === 0 ? (
        <EmptyState
          className="mt-4"
          title="No students yet"
          description="Students appear here once they have been enrolled and have started a case. Enrolment is on the administration pages."
        />
      ) : (
        <div className="card mt-4 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[860px]">
              <thead className="bg-brand-cardLight text-brand-muted text-xs uppercase">
                <tr>
                  <th className="text-left px-5 py-3 font-medium">Student</th>
                  <th className="text-left px-5 py-3 font-medium">Completed</th>
                  <th className="text-left px-5 py-3 font-medium">Average</th>
                  <th className="text-left px-5 py-3 font-medium">Weakest</th>
                  <th className="text-left px-5 py-3 font-medium">Mistakes</th>
                  <th className="text-left px-5 py-3 font-medium">Gain</th>
                  <th className="text-left px-5 py-3 font-medium">Last active</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr
                    key={s.studentId}
                    onClick={() => navigate(`/faculty/students/${s.studentId}`)}
                    className="border-t border-white/5 hover:bg-white/5 cursor-pointer"
                  >
                    <td className="px-5 py-4">
                      <span className="font-medium">{s.fullName}</span>
                      <span className="block text-xs text-brand-muted">{s.collegeId}</span>
                    </td>
                    <td className="px-5 py-4 tabular">{s.casesCompleted}</td>
                    <td className={`px-5 py-4 tabular ${accuracyTone(s.averageScorePct)}`}>
                      {s.averageScorePct === null ? "—" : `${s.averageScorePct}%`}
                    </td>
                    <td className="px-5 py-4 text-brand-muted">{s.weakestConcept || "—"}</td>
                    <td className="px-5 py-4 tabular">
                      {s.mistakes}
                      {s.remarks > 0 && (
                        <span className="text-xs text-brand-accent ml-2">
                          {s.remarks} remark{s.remarks === 1 ? "" : "s"}
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-4 tabular">
                      {s.learningGainPct === null ? (
                        <span className="text-brand-muted text-xs">not enough yet</span>
                      ) : (
                        <span
                          className={
                            s.learningGainPct > 0 ? "text-brand-success" : "text-brand-danger"
                          }
                        >
                          {s.learningGainPct > 0 ? "+" : ""}
                          {s.learningGainPct}%
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-4 text-brand-muted text-xs">
                      {timeAgo(s.lastActiveAt)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <p className="text-xs text-brand-muted mt-4">
        Gain compares first-attempt accuracy across a student's earlier and later sessions. It
        needs at least four completed cases before it means anything, and says so until then.
      </p>
    </Layout>
  );
}
