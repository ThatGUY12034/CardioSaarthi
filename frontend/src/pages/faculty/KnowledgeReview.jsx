import { useEffect, useState } from "react";
import Layout from "../../components/Layout";
import StatCard from "../../components/StatCard";
import { EmptyState, ErrorState, InlineError, SkeletonRows } from "../../components/States";
import {
  getKnowledgeQueue,
  getKnowledgeStatus,
  reviewChunk,
} from "../../api/tutorApi";
import { errorMessage } from "../../api/studyApi";

/**
 * The gate on what the tutor may say.
 *
 * <p>The corpus is drawn from openly licensed published material, which spares
 * faculty the writing and not the judgement. A paragraph is invisible to the
 * tutor until somebody here approves it.
 *
 * <p>There is no edit control, deliberately. The text is quoted material under
 * a licence that requires attribution, and a paragraph rewritten after import
 * no longer says what its source says while still carrying its citation. A
 * database trigger refuses the change independently of this page.
 */

const CONCEPTS = [
  ["", "All concepts"],
  ["rate", "Rate"],
  ["rhythm", "Rhythm"],
  ["axis", "Axis"],
  ["p_waves", "P waves"],
  ["pr_interval", "PR interval"],
  ["qrs", "QRS"],
  ["st_segment", "ST segment"],
  ["t_waves", "T waves"],
  ["qt_interval", "QT interval"],
];

export default function KnowledgeReview() {
  const [status, setStatus] = useState(null);
  const [chunks, setChunks] = useState(null);
  const [concept, setConcept] = useState("");
  const [error, setError] = useState(null);
  const [flash, setFlash] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getKnowledgeStatus(), getKnowledgeQueue("pending", concept || null, 25)])
      .then(([s, q]) => {
        if (cancelled) return;
        setStatus(s);
        setChunks(q);
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e, "Could not load the review queue."));
      });
    return () => {
      cancelled = true;
    };
  }, [concept, reloadKey]);

  const decide = async (id, action) => {
    let reason = null;
    if (action === "REJECT") {
      // The same rule as rejecting a case: a rejection with no reason is
      // indistinguishable from a paragraph nobody got round to.
      reason = window.prompt("Why is this paragraph not suitable?");
      if (!reason || !reason.trim()) return;
    }
    setBusyId(id);
    setError(null);
    try {
      await reviewChunk(id, action, reason);
      setFlash(action === "APPROVE" ? "Approved. The tutor may now quote it." : "Rejected.");
      setReloadKey((n) => n + 1);
    } catch (e) {
      setError(errorMessage(e, "That decision was not recorded."));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Layout role="FACULTY">
      <h1 className="page-title">Reference Library</h1>
      <p className="page-subtitle">
        What the tutor is allowed to quote. Nothing here reaches a student until you approve it.
      </p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mt-8">
        <StatCard icon="📥" label="Awaiting review" value={status?.pending ?? "—"} color="brand-warning" />
        <StatCard icon="✅" label="Approved" value={status?.approved ?? "—"} color="brand-success" />
        <StatCard icon="🚫" label="Rejected" value={status?.rejected ?? "—"} color="brand-danger" />
        <StatCard icon="📚" label="Sources" value={status?.sources ?? "—"} />
      </div>

      {/* The same distinction the case bank draws. A seeded approval is a
          fixture, not a decision, and the two must never be added together. */}
      {status && status.approved > 0 && (
        <p className="text-xs text-brand-muted mt-3">
          {status.approvedByClinician} of {status.approved} approved paragraphs were read by a
          clinician. The remainder were seeded so the tutor could be demonstrated.
        </p>
      )}

      {flash && (
        <p className="mt-6 rounded-lg border border-brand-success/40 bg-brand-success/10 px-4 py-3 text-sm text-brand-success">
          {flash}
        </p>
      )}
      {error && <div className="mt-6"><InlineError message={error} /></div>}

      <div className="flex items-center gap-3 mt-6">
        <label className="text-sm text-brand-muted" htmlFor="concept-filter">
          Concept
        </label>
        <select
          id="concept-filter"
          value={concept}
          onChange={(event) => setConcept(event.target.value)}
          className="bg-brand-bg2 rounded-lg px-3 py-2 text-sm"
        >
          {CONCEPTS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {chunks === null ? (
        <SkeletonRows className="mt-6" count={5} />
      ) : chunks.length === 0 ? (
        <EmptyState
          className="mt-6"
          icon={"✓"}
          title="Nothing awaiting review"
          description="Every imported paragraph for this filter has been approved or rejected. Run the import script to add more material."
        />
      ) : (
        <div className="space-y-4 mt-6">
          {chunks.map((c) => (
            <article key={c.id} className="card p-5">
              <div className="flex items-baseline justify-between gap-4 flex-wrap">
                <h2 className="font-semibold text-sm">
                  {c.heading || "Untitled section"}
                  {c.concept && (
                    <span className="ml-2 text-[11px] px-2 py-0.5 rounded-full bg-brand-primary/20 text-brand-accent">
                      {c.concept.replace(/_/g, " ")}
                    </span>
                  )}
                </h2>
                <span className="text-[11px] text-brand-muted">{c.sourceLicence}</span>
              </div>

              <p className="text-sm mt-3 leading-relaxed text-brand-muted">{c.body}</p>

              <p className="text-[11px] text-brand-muted mt-3">
                From{" "}
                <a
                  href={c.sourceUrl}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="text-brand-accent hover:underline"
                >
                  {c.sourceTitle}
                </a>{" "}
                · {c.sourcePublisher}
              </p>

              <div className="flex gap-3 mt-4">
                <button
                  onClick={() => decide(c.id, "APPROVE")}
                  disabled={busyId === c.id}
                  className="btn-primary text-sm"
                >
                  Approve
                </button>
                <button
                  onClick={() => decide(c.id, "REJECT")}
                  disabled={busyId === c.id}
                  className="btn-ghost text-sm"
                >
                  Reject
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </Layout>
  );
}
