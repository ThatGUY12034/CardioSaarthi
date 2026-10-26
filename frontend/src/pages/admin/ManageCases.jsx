import { useEffect, useState } from "react";
import Layout from "../../components/Layout";
import { EmptyState, ErrorState, SkeletonRows } from "../../components/States";
import { getCoverage, getOverview } from "../../api/adminApi";
import { errorMessage } from "../../api/studyApi";

/**
 * Where the case bank is thin.
 *
 * <p>Ordered by what is scarcest rather than alphabetically, because the only
 * question this page answers is which condition to source or review next. A
 * condition with a target the dataset cannot supply at all is marked as such:
 * ventricular tachycardia and both electrolyte disturbances are absent from
 * PTB-XL, which is a decision for faculty and not a backlog to work through.
 */
export default function ManageCases() {
  const [coverage, setCoverage] = useState(null);
  const [overview, setOverview] = useState(null);
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getCoverage(), getOverview()])
      .then(([c, o]) => {
        if (cancelled) return;
        setCoverage(c);
        setOverview(o);
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e, "Could not load case coverage."));
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (error) {
    return (
      <Layout role="ADMIN">
        <h1 className="page-title">Case Bank</h1>
        <div className="mt-8">
          <ErrorState message={error} onRetry={() => setReloadKey((n) => n + 1)} />
        </div>
      </Layout>
    );
  }

  return (
    <Layout role="ADMIN">
      <h1 className="page-title">Case Bank</h1>
      <p className="page-subtitle">
        Syllabus coverage by condition, scarcest first.
      </p>

      {overview && (
        <p className="text-sm text-brand-muted mt-4">
          {overview.casesApproved} approved of {overview.casesTotal} measured.{" "}
          {overview.casesPending} are queued for review.
        </p>
      )}

      {coverage === null ? (
        <SkeletonRows className="mt-6" count={8} />
      ) : coverage.length === 0 ? (
        <EmptyState className="mt-6" title="No conditions configured" />
      ) : (
        <div className="card mt-6 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[640px]">
              <thead className="bg-brand-cardLight text-brand-muted text-xs uppercase">
                <tr>
                  <th className="text-left px-5 py-3 font-medium">Condition</th>
                  <th className="text-left px-5 py-3 font-medium">Approved</th>
                  <th className="text-left px-5 py-3 font-medium">Queued</th>
                  <th className="text-left px-5 py-3 font-medium">Target</th>
                  <th className="text-left px-5 py-3 font-medium w-48">Progress</th>
                </tr>
              </thead>
              <tbody>
                {coverage.map((c) => {
                  const pct =
                    c.target > 0 ? Math.min(100, Math.round((c.approved / c.target) * 100)) : 0;
                  // Nothing measured and nothing queued means the dataset does
                  // not contain it, which no amount of reviewing will fix.
                  const unavailable = c.approved === 0 && c.pending === 0;
                  return (
                    <tr key={c.code} className="border-t border-white/5">
                      <td className="px-5 py-4">
                        <span className="font-medium">{c.label}</span>
                        {unavailable && (
                          <span className="ml-2 text-[11px] px-2 py-0.5 rounded-full bg-brand-danger/20 text-brand-danger">
                            not in dataset
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-4 tabular">{c.approved}</td>
                      <td className="px-5 py-4 tabular text-brand-muted">{c.pending}</td>
                      <td className="px-5 py-4 tabular text-brand-muted">{c.target}</td>
                      <td className="px-5 py-4">
                        <div className="h-2 bg-white/5 rounded overflow-hidden">
                          <div
                            className={`h-full rounded ${
                              pct >= 100
                                ? "bg-brand-success"
                                : pct > 0
                                  ? "bg-brand-warning"
                                  : "bg-brand-danger/50"
                            }`}
                            style={{ width: `${Math.max(pct, unavailable ? 0 : 2)}%` }}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <p className="text-xs text-brand-muted mt-4">
        Conditions marked “not in dataset” cannot be sourced from PTB-XL at all. That needs a
        sourcing decision from faculty rather than more review time.
      </p>
    </Layout>
  );
}
