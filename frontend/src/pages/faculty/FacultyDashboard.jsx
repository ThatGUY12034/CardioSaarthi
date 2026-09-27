import { useEffect, useState } from "react";
import Layout from "../../components/Layout";
import { InlineError, Skeleton } from "../../components/States";
import StatCard from "../../components/StatCard";
import { errorMessage, getConditions, getStats } from "../../api/reviewApi";

/**
 * What the platform actually knows, with nothing invented.
 *
 * Every figure here is read from the API. Where there is no data yet -- no
 * student has used the platform, no reviewer has corrected anything -- the panel
 * says so rather than showing a plausible number. A dashboard that displays a
 * class average before any class exists is the one thing a reviewer will catch.
 */
export default function FacultyDashboard() {
  const [stats, setStats] = useState(null);
  const [conditions, setConditions] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([getStats(), getConditions()])
      .then(([loadedStats, loadedConditions]) => {
        setStats(loadedStats);
        setConditions(loadedConditions);
      })
      .catch((exception) => setError(errorMessage(exception, "Could not load the dashboard.")));
  }, []);

  const outcomes = stats?.outcomes;
  const available = conditions.filter((condition) => condition.available);
  const unavailable = conditions.filter((condition) => !condition.available);

  const targetTotal = available.reduce((sum, condition) => sum + condition.targetCases, 0);
  const approvedTotal = available.reduce((sum, condition) => sum + condition.approved, 0);
  const coverage = targetTotal ? Math.round((approvedTotal / targetTotal) * 100) : 0;

  const emptiest = [...available].sort((a, b) => b.shortfall - a.shortfall).slice(0, 6);

  return (
    <Layout role="FACULTY">
      <h1 className="text-3xl font-bold">Faculty Dashboard</h1>
      <p className="text-brand-muted mt-1">
        Case bank status and review progress. Every number here is read from the platform.
      </p>

      {error && <div className="mt-6"><InlineError message={error} /></div>}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mt-8">
        <StatCard
          icon="📝"
          label="Awaiting review"
          value={outcomes ? outcomes.pendingRemaining : "—"}
          sublabel="not servable to students"
          color="yellow"
        />
        <StatCard
          icon="✅"
          label="Approved cases"
          value={approvedTotal || "0"}
          sublabel={`${coverage}% of the syllabus target`}
          color="green"
        />
        <StatCard
          icon="🩺"
          label="Reviews recorded"
          value={outcomes ? outcomes.nReviews : "—"}
          sublabel={
            outcomes?.nReviews
              ? `${outcomes.usablePct}% usable`
              : "no faculty review yet"
          }
          color="blue"
        />
        <StatCard
          icon="⏱"
          label="Median per case"
          value={
            outcomes?.medianSecondsPerCase ? `${Math.round(outcomes.medianSecondsPerCase)}s` : "—"
          }
          sublabel="measured, not estimated"
          color="cyan"
        />
      </div>

      <div className="grid md:grid-cols-2 gap-6 mt-8">
        {/* where the bank is thinnest */}
        <div className="card p-6">
          <h3 className="font-semibold">Furthest from target</h3>
          <p className="text-xs text-brand-muted mt-1">
            The review queue puts these first, so a reviewer's hour fills the emptiest part of the
            bank.
          </p>
          <ul className="space-y-2 text-sm mt-4">
            {emptiest.map((condition) => (
              <li key={condition.code} className="flex justify-between gap-3">
                <span>{condition.label}</span>
                <span className="text-brand-muted whitespace-nowrap">
                  {condition.approved} / {condition.targetCases}
                  <span className="text-brand-warning ml-2">−{condition.shortfall}</span>
                </span>
              </li>
            ))}
            {emptiest.length === 0 &&
              Array.from({ length: 4 }).map((_, index) => (
                <li key={index}>
                  <Skeleton className="h-4 w-full" />
                </li>
              ))}
          </ul>
        </div>

        {/* the engine's report card */}
        <div className="card p-6">
          <h3 className="font-semibold">Measurement agreement</h3>
          <p className="text-xs text-brand-muted mt-1">
            How far the engine was from a reviewer, per measure. Bias and scatter are separate: two
            corrections of +20 ms and −20 ms are 20 ms of error and zero bias.
          </p>
          {stats?.agreement?.length ? (
            <table className="w-full text-sm mt-4">
              <thead className="text-xs text-brand-muted text-left">
                <tr>
                  <th className="pb-2">Measure</th>
                  <th className="pb-2 text-right">n</th>
                  <th className="pb-2 text-right">MAE</th>
                  <th className="pb-2 text-right">Bias</th>
                </tr>
              </thead>
              <tbody>
                {stats.agreement.map((row) => (
                  <tr key={row.name} className="border-t border-white/5">
                    <td className="py-1">{row.name.replace(/_/g, " ")}</td>
                    <td className="py-1 text-right font-mono">{row.nCorrections}</td>
                    <td className="py-1 text-right font-mono">{row.mae}</td>
                    <td className="py-1 text-right font-mono">{row.bias}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-brand-muted mt-4">
              Nothing to report yet. This table fills as reviewers correct measurements, and those
              corrections are what validate the measurement engine.
            </p>
          )}
        </div>
      </div>

      {/* the gaps that need a decision, not a fix */}
      {unavailable.length > 0 && (
        <div className="card p-6 mt-6">
          <h3 className="font-semibold">Not available in the dataset</h3>
          <p className="text-xs text-brand-muted mt-1">
            On the syllabus and absent from PTB-XL. These need a faculty decision: drop them from
            the committed scope, or find a second source.
          </p>
          <ul className="grid sm:grid-cols-3 gap-3 mt-4 text-sm">
            {unavailable.map((condition) => (
              <li key={condition.code} className="rounded border border-brand-warning/30 px-3 py-2">
                <span className="block">{condition.label}</span>
                <span className="text-xs text-brand-warning">0 records</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Layout>
  );
}
