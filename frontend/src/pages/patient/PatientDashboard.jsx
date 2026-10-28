import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Layout from "../../components/Layout";
import EcgImage from "../../components/EcgImage";
import { EmptyState, ErrorState, SkeletonCard } from "../../components/States";
import { getReports } from "../../api/patientApi";
import { errorMessage } from "../../api/studyApi";
import { useAuth } from "../../context/useAuth";

/**
 * The reports issued to this patient.
 *
 * <p>Scoped to the caller on the server. Nothing on this page asks for a
 * patient id, so there is no identifier for a client to tamper with.
 */
export default function PatientDashboard() {
  const { user } = useAuth();
  const [reports, setReports] = useState(null);
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getReports()
      .then((data) => {
        if (!cancelled) setReports(data);
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e, "Could not load your reports."));
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  return (
    <Layout role="PATIENT">
      <h1 className="page-title">
        Hello{user?.name ? `, ${user.name.split(" ")[0]}` : ""}
      </h1>
      <p className="page-subtitle">Your ECG reports, explained in ordinary words.</p>

      {error ? (
        <div className="mt-8">
          <ErrorState message={error} onRetry={() => setReloadKey((n) => n + 1)} />
        </div>
      ) : reports === null ? (
        <div className="mt-8">
          <SkeletonCard lines={3} />
        </div>
      ) : reports.length === 0 ? (
        <EmptyState
          className="mt-8"
          title="No reports yet"
          description="A report appears here once your clinician issues one to you. Nothing is shown until a recording has been reviewed and approved."
        />
      ) : (
        <div className="grid md:grid-cols-2 gap-6 mt-8">
          {reports.map((r) => (
            <div key={r.reportId} className="card overflow-hidden flex flex-col">
              <EcgImage caseId={r.caseId} kind="clean" height={150} zoomable={false} />
              <div className="p-5 flex-1 flex flex-col">
                <h2 className="font-semibold">ECG recording</h2>
                <p className="text-xs text-brand-muted mt-1">Issued {r.issuedOn}</p>
                {r.clinicianNote && (
                  <p className="text-sm text-brand-muted mt-3 line-clamp-2">{r.clinicianNote}</p>
                )}
                <Link
                  to={`/patient/report/${r.reportId}`}
                  className="btn-primary text-sm mt-4 text-center"
                >
                  Read the explanation
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-brand-muted mt-6">
        These pages describe what a recording showed. They do not diagnose, and they are not a
        substitute for speaking to your clinician.
      </p>
    </Layout>
  );
}
