import { useEffect, useState } from "react";
import Layout from "../../components/Layout";
import { ErrorState, SkeletonRows } from "../../components/States";
import { getGlossary } from "../../api/patientApi";
import { errorMessage } from "../../api/studyApi";

/**
 * The words, defined.
 *
 * <p>Served from the database rather than written into this file, so a
 * clinician correcting a definition changes a row and not a deployment. An
 * unapproved definition is marked as such rather than quietly shown.
 */
export default function Glossary() {
  const [terms, setTerms] = useState(null);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getGlossary()
      .then((data) => {
        if (!cancelled) setTerms(data);
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e, "Could not load the glossary."));
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  return (
    <Layout role="PATIENT">
      <h1 className="page-title">ECG Terminology</h1>
      <p className="page-subtitle">The words on your report, in ordinary language.</p>

      {error ? (
        <div className="mt-8">
          <ErrorState message={error} onRetry={() => setReloadKey((n) => n + 1)} />
        </div>
      ) : terms === null ? (
        <SkeletonRows className="mt-8" count={6} />
      ) : (
        <div className="mt-8 space-y-3 max-w-3xl">
          {terms.map((t, i) => (
            <div key={t.term} className="card overflow-hidden">
              <button
                onClick={() => setOpen(open === i ? null : i)}
                aria-expanded={open === i}
                className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-white/5"
              >
                <span className="font-medium">{t.term}</span>
                <span className="text-brand-accent text-xl" aria-hidden="true">
                  {open === i ? "−" : "+"}
                </span>
              </button>
              {open === i && (
                <div className="px-5 pb-5">
                  <p className="text-sm text-brand-muted leading-relaxed">{t.plainText}</p>
                  {!t.approved && (
                    <p className="text-[11px] text-brand-warning mt-3">
                      This definition is awaiting clinical sign-off.
                    </p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
}
