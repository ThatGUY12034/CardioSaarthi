import { useEffect, useState } from "react";
import { fetchEcgImage } from "../api/reviewApi";

/**
 * A real rendered ECG, fetched from the API.
 *
 * Not a drawn approximation. This is the image the measurement engine produced
 * at 25 mm/s and 10 mm/mV, which is what a student is asked to read measurements
 * off, so a reviewer has to be looking at exactly that.
 *
 * Fetched as a blob because the image endpoint is authenticated and a plain img
 * src sends no Authorization header. The object URL is revoked on unmount and
 * whenever the case changes; without that, working through a queue of cases
 * leaks a full-size PNG per case for the life of the tab.
 *
 * The loaded image is stored together with the case it belongs to, and whether
 * to show a spinner is derived from comparing the two. Resetting state at the
 * top of the effect instead would set state synchronously during render, and
 * would briefly show the previous case's ECG under the new case's heading.
 */
export default function EcgImage({ caseId, kind = "clean", height = 200, className = "" }) {
  const [loaded, setLoaded] = useState({ caseId: null, kind: null, url: null, error: null });

  useEffect(() => {
    let cancelled = false;
    let created = null;

    (async () => {
      try {
        created = await fetchEcgImage(caseId, kind);
        if (cancelled) {
          URL.revokeObjectURL(created);
          created = null;
          return;
        }
        setLoaded({ caseId, kind, url: created, error: null });
      } catch {
        if (!cancelled) {
          setLoaded({ caseId, kind, url: null, error: "ECG image unavailable" });
        }
      }
    })();

    return () => {
      cancelled = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [caseId, kind]);

  const current = loaded.caseId === caseId && loaded.kind === kind ? loaded : null;

  if (current?.error) {
    return (
      <div
        className={`flex items-center justify-center bg-brand-bg2 text-xs text-brand-muted ${className}`}
        style={{ height }}
      >
        {current.error}
      </div>
    );
  }

  if (!current?.url) {
    return (
      <div
        className={`flex items-center justify-center bg-brand-bg2 ${className}`}
        style={{ height }}
      >
        <div className="w-6 h-6 border-2 border-brand-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <img
      src={current.url}
      alt={`12-lead ECG for case ${caseId}`}
      // White background: the render is a standards-compliant trace on ECG
      // paper, and showing it on the dark theme would invert what a clinician
      // expects to see.
      className={`w-full object-contain bg-white ${className}`}
      style={{ height }}
    />
  );
}
