import { useEffect, useState } from "react";
import { getCaseBrief } from "../api/studyApi";

/**
 * The patient around the tracing.
 *
 * <p>An ECG is never read in isolation. A clinician is told who the patient is,
 * why they presented and what else is true of them before the trace is put in
 * front of them, and reading it without that is an exercise the ward does not
 * contain. This is the "clinical case simulation" half of the project, and
 * until now the pipeline wrote one per case and nothing ever showed it.
 *
 * <p>It states no ECG finding and no diagnosis. The narrative validator refuses
 * a scenario that does, which is what lets this sit beside the trace without
 * answering the nine questions the student is about to be asked.
 *
 * <p>The heart rate in the vitals is the measured one, injected from the engine
 * after the scenario was written rather than invented alongside it. Where the
 * stored value says so, this says so too.
 */

function Row({ label, children }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5 border-b border-white/5 last:border-0">
      <dt className="text-xs text-brand-muted shrink-0">{label}</dt>
      <dd className="text-sm text-right">{children}</dd>
    </div>
  );
}

/** "blood_pressure" reads as a column name; "Blood pressure" reads as a label. */
function humanise(key) {
  const spaced = key.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

const VITAL_UNITS = {
  heart_rate_bpm: "bpm",
  respiratory_rate: "/min",
  spo2_percent: "%",
  temperature_c: "°C",
};

export default function CaseBrief({ caseId }) {
  const [brief, setBrief] = useState(undefined);

  useEffect(() => {
    let cancelled = false;
    getCaseBrief(caseId)
      .then((found) => {
        if (!cancelled) setBrief(found);
      })
      .catch(() => {
        // A missing brief must never stop a case being read. The trace and the
        // nine steps are the thing being marked; this is context.
        if (!cancelled) setBrief(null);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  if (brief === undefined) {
    return (
      <div className="card p-5">
        <div className="h-3 w-32 bg-white/10 rounded animate-pulse" />
        <div className="h-3 w-full bg-white/5 rounded mt-3 animate-pulse" />
        <div className="h-3 w-4/5 bg-white/5 rounded mt-2 animate-pulse" />
      </div>
    );
  }

  if (brief === null) {
    return null;
  }

  const vitals = brief.vitals || {};
  const labs = brief.relevant_labs || {};
  const medications = brief.medications || [];
  const measuredRate = vitals.heart_rate_source;

  return (
    <div className="card p-5">
      <h2 className="font-semibold text-sm">Clinical scenario</h2>
      <p className="text-[11px] text-brand-muted mt-1">
        What you would be told before reading this trace.
      </p>

      {brief.presenting_complaint && (
        <p className="text-sm mt-4 leading-relaxed">{brief.presenting_complaint}</p>
      )}

      {brief.history && (
        <div className="mt-4">
          <h3 className="text-xs text-brand-muted uppercase tracking-wide">History</h3>
          <p className="text-sm mt-1 leading-relaxed">{brief.history}</p>
        </div>
      )}

      {brief.examination && (
        <div className="mt-4">
          <h3 className="text-xs text-brand-muted uppercase tracking-wide">On examination</h3>
          <p className="text-sm mt-1 leading-relaxed">{brief.examination}</p>
        </div>
      )}

      {Object.keys(vitals).length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs text-brand-muted uppercase tracking-wide">Vitals</h3>
          <dl className="mt-1">
            {Object.entries(vitals)
              .filter(([key]) => key !== "heart_rate_source")
              .map(([key, value]) => (
                <Row key={key} label={humanise(key)}>
                  {value}
                  {VITAL_UNITS[key] ? ` ${VITAL_UNITS[key]}` : ""}
                </Row>
              ))}
          </dl>
          {measuredRate && (
            // Worth saying out loud: this number is not part of the story. It
            // came off the waveform, which is why it agrees with the trace.
            <p className="text-[11px] text-brand-muted mt-2">
              Heart rate {measuredRate}.
            </p>
          )}
        </div>
      )}

      {medications.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs text-brand-muted uppercase tracking-wide">Medications</h3>
          <ul className="text-sm mt-1 space-y-1">
            {medications.map((drug) => (
              <li key={drug} className="text-brand-muted">
                {drug}
              </li>
            ))}
          </ul>
        </div>
      )}

      {Object.keys(labs).length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs text-brand-muted uppercase tracking-wide">Relevant labs</h3>
          <dl className="mt-1">
            {Object.entries(labs).map(([key, value]) => (
              <Row key={key} label={humanise(key)}>
                {value}
              </Row>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}
