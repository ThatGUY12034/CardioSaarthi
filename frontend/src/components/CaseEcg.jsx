import { useEffect, useState } from "react";
import axiosClient from "../api/axiosClient";
import EcgImage from "./EcgImage";

/**
 * A real recording, wherever an ECG is shown.
 *
 * <p>Everywhere in the app that displayed an ECG was drawing a synthetic trace:
 * a smooth repeating squiggle that looks like an ECG and is not one. A student
 * asked to measure a PR interval off a drawing learns to read the drawing.
 * These are the images the measurement engine rendered from real recordings at
 * 25 mm/s and 10 mm/mV, which is what the platform's measurements were taken
 * from and what a paper trace actually looks like.
 *
 * <p>With a caseId, that case is shown. Without one -- on the pages that are
 * still illustrative rather than driven by a real session -- it borrows the
 * first case a reviewer has approved, resolved once per page load and shared
 * between every instance rather than fetched six times.
 */

/**
 * Resolved once and reused. Six components mounting at once would otherwise
 * each ask the server which case to use.
 */
let pendingDefault = null;

async function resolveDefaultCase() {
  if (!pendingDefault) {
    pendingDefault = axiosClient
      .get("/study/cases", { params: { limit: 1 } })
      .then((response) => response.data?.[0]?.caseId ?? null)
      .catch(() => null);
  }
  return pendingDefault;
}

export default function CaseEcg({ caseId, kind = "clean", height = 200, label, className = "" }) {
  // Only the borrowed case needs state. A caseId that was passed in is already
  // known, and copying it into state would mean setting state during render.
  const [borrowed, setBorrowed] = useState({ resolved: false, caseId: null });

  useEffect(() => {
    if (caseId) {
      return undefined;
    }
    let cancelled = false;
    resolveDefaultCase().then((found) => {
      if (!cancelled) setBorrowed({ resolved: true, caseId: found });
    });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  const resolved = caseId ?? borrowed.caseId;
  const unavailable = !caseId && borrowed.resolved && borrowed.caseId === null;

  return (
    <figure className={`m-0 ${className}`}>
      {unavailable ? (
        // Said plainly rather than filled with a drawing. An approved case is
        // the only thing that may be shown, and if there is none yet that is
        // worth knowing.
        <div
          className="flex items-center justify-center bg-brand-bg2 text-xs text-brand-muted rounded"
          style={{ height }}
        >
          No approved recording available yet
        </div>
      ) : resolved === null ? (
        <div className="flex items-center justify-center bg-brand-bg2 rounded" style={{ height }}>
          <div className="w-6 h-6 border-2 border-brand-primary border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <EcgImage caseId={resolved} kind={kind} height={height} className="rounded" />
      )}
      {label && (
        <figcaption className="text-[11px] text-brand-muted mt-2">{label}</figcaption>
      )}
    </figure>
  );
}
