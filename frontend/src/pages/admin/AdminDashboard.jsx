import { useEffect, useState } from "react";
import Layout from "../../components/Layout";
import StatCard from "../../components/StatCard";
import { ErrorState, SkeletonCard } from "../../components/States";
import { getOverview } from "../../api/adminApi";
import { errorMessage } from "../../api/studyApi";

/**
 * The state of the installation, counted rather than asserted.
 *
 * <p>This page used to show four numbers written into the component. Every one
 * is now a count from the database, including the one that matters most and is
 * easiest to overstate: how much of the platform's content a human being has
 * actually approved, as against how much a seed script approved so the thing
 * could be demonstrated.
 */
export default function AdminDashboard() {
  const [overview, setOverview] = useState(null);
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getOverview()
      .then((data) => {
        if (!cancelled) setOverview(data);
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e, "Could not load the overview."));
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (error) {
    return (
      <Layout role="ADMIN">
        <h1 className="page-title">Administration</h1>
        <div className="mt-8">
          <ErrorState message={error} onRetry={() => setReloadKey((n) => n + 1)} />
        </div>
      </Layout>
    );
  }

  const o = overview;
  const approvalRate =
    o && o.casesTotal > 0 ? Math.round((o.casesApproved / o.casesTotal) * 100) : null;

  return (
    <Layout role="ADMIN">
      <h1 className="page-title">Administration</h1>
      <p className="page-subtitle">
        Every figure on this page is counted from the database at the moment you loaded it.
      </p>

      {!o ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mt-8">
          {[0, 1, 2, 3].map((i) => (
            <SkeletonCard key={i} lines={1} />
          ))}
        </div>
      ) : (
        <>
          <h2 className="font-semibold mt-8">Case bank</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mt-3">
            <StatCard icon="🗂" label="Measured" value={o.casesTotal} />
            <StatCard icon="✅" label="Approved" value={o.casesApproved} color="brand-success" />
            <StatCard icon="⏳" label="Awaiting review" value={o.casesPending} color="brand-warning" />
            <StatCard icon="🚫" label="Rejected" value={o.casesRejected} color="brand-danger" />
          </div>
          <p className="text-xs text-brand-muted mt-3">
            {approvalRate}% of measured cases are servable. The rest are queued behind faculty
            review, which is the project's critical path rather than a backlog.
          </p>

          <h2 className="font-semibold mt-8">People</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mt-3">
            <StatCard icon="🎓" label="Students" value={o.students} />
            <StatCard icon="🩺" label="Reviewers" value={o.reviewers} />
            <StatCard icon="👤" label="Patients" value={o.patients} />
            <StatCard icon="📈" label="Sessions started" value={o.sessionsStarted} />
          </div>
          <p className="text-xs text-brand-muted mt-3">
            {o.sessionsCompleted} of {o.sessionsStarted} sessions were carried through to the
            end.
          </p>

          <h2 className="font-semibold mt-8">Content</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mt-3">
            <StatCard icon="📚" label="Reference paragraphs" value={o.knowledgeTotal} />
            <StatCard
              icon="✔"
              label="Approved"
              value={o.knowledgeApproved}
              color="brand-success"
            />
            <StatCard icon="📝" label="Case narratives" value={o.narrativesWritten} />
            <StatCard icon="🗄" label="Schema version" value={`V${o.schemaVersion}`} />
          </div>

          {/* The number that is easiest to overstate, stated plainly. */}
          <div className="card p-5 mt-6 border border-brand-warning/30">
            <h3 className="font-semibold text-sm">What a person has actually approved</h3>
            <p className="text-sm text-brand-muted mt-2 leading-relaxed">
              <strong className="text-brand-text">
                {o.knowledgeApprovedByClinician} of {o.knowledgeApproved}
              </strong>{" "}
              approved reference paragraphs were read by a clinician. The remainder were
              approved by the seed account so the tutor could be demonstrated, and are counted
              separately everywhere in this platform. The same distinction applies to the case
              bank: a seeded approval is a fixture, not a decision.
            </p>
          </div>
        </>
      )}
    </Layout>
  );
}
