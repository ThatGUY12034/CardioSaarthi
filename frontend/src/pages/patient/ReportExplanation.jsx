import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import Layout from "../../components/Layout";
import EcgImage from "../../components/EcgImage";
import { EmptyState, ErrorState, SkeletonCard } from "../../components/States";
import { getReport } from "../../api/patientApi";
import { errorMessage } from "../../api/studyApi";

/**
 * A patient's own recording, explained.
 *
 * <p>Every sentence on this page was selected by a computed measurement from a
 * table a clinician approved. None of it is written here and none of it is
 * generated. A finding with no approved sentence is shown named and
 * unexplained, because hiding it would conceal from the patient that their
 * recording contains something nobody has written an approved sentence for.
 *
 * <p>Nothing on this page is a diagnosis, and it says so.
 */
export default function ReportExplanation() {
  const { id } = useParams();
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getReport(id)
      .then((data) => {
        if (!cancelled) setReport(data);
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e, "Could not load your report."));
      });
    return () => {
      cancelled = true;
    };
  }, [id, reloadKey]);

  if (error) {
    return (
      <Layout role="PATIENT">
        <h1 className="page-title">Your ECG Report</h1>
        <div className="mt-8">
          <ErrorState message={error} onRetry={() => setReloadKey((n) => n + 1)} />
        </div>
      </Layout>
    );
  }

  return (
    <Layout role="PATIENT">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="page-title">Your ECG Report</h1>
          <p className="page-subtitle">
            {report ? `Recorded and issued on ${report.issuedOn}` : "Loading your report"}
          </p>
        </div>
      </div>

      {!report ? (
        <div className="mt-8 space-y-4">
          <SkeletonCard lines={2} />
          <SkeletonCard lines={4} />
        </div>
      ) : (
        <>
          <div className="card overflow-hidden mt-8">
            <EcgImage caseId={report.caseId} kind="clean" height={280} label="Your recording" />
            <p className="px-5 py-3 text-[11px] text-brand-muted">
              This is the actual trace recorded from you. The grid is the standard clinical
              scale your clinician reads it at.
            </p>
          </div>

          {report.clinicianNote && (
            <div className="card p-6 mt-6">
              <h2 className="font-semibold">A note from your clinician</h2>
              <p className="text-sm mt-2 leading-relaxed">{report.clinicianNote}</p>
            </div>
          )}

          <div className="card p-6 mt-6">
            <h2 className="font-semibold">What the recording showed</h2>
            <p className="text-xs text-brand-muted mt-1">
              {report.explainedCount} of {report.totalFindings} findings have a plain-language
              explanation.
            </p>

            <ul className="mt-5 space-y-4">
              {report.findings.map((f) => (
                <li key={f.step} className="border-b border-white/5 pb-4 last:border-0 last:pb-0">
                  <div className="flex items-baseline justify-between gap-4">
                    <h3 className="font-medium text-sm">{f.label}</h3>
                    <span className="text-sm text-brand-muted tabular">{f.measured}</span>
                  </div>

                  {f.explained ? (
                    <>
                      <p
                        className={`text-sm mt-2 font-medium ${
                          f.reassuring ? "text-brand-success" : "text-brand-text"
                        }`}
                      >
                        {f.headline}
                      </p>
                      <p className="text-sm text-brand-muted mt-1 leading-relaxed">
                        {f.plainText}
                      </p>
                    </>
                  ) : (
                    // Named, not explained, and said plainly. Silence here would
                    // read as "nothing to report", which is a different claim.
                    <p className="text-xs text-brand-muted mt-2 italic">
                      No approved plain-language explanation has been written for this finding
                      yet. Your clinician can explain it.
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </div>

          {/* The two things a patient must not take away from this page. */}
          <div className="card p-5 mt-6 border border-brand-warning/30">
            <p className="text-sm">
              <strong>This is not a diagnosis.</strong> It describes what the recording showed,
              in ordinary words. What it means for your health is a conversation with your
              clinician, who has your history as well as this trace.
            </p>
            {!report.clinicianApproved && (
              <p className="text-xs text-brand-warning mt-3">
                Some wording on this page is awaiting clinical sign-off and is shown here for
                demonstration.
              </p>
            )}
          </div>
        </>
      )}
    </Layout>
  );
}
