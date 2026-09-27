import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Layout from "../../components/Layout";
import EcgImage from "../../components/EcgImage";
import {
  errorMessage,
  getCase,
  getQueue,
  getReviewOptions,
  submitReview,
} from "../../api/reviewApi";

/**
 * The faculty review queue, against the real case bank.
 *
 * A reviewer sees the rendered ECG, every computed measurement with its spread
 * and confidence, and the warnings the engine raised about its own output. They
 * approve, correct or reject. Only approved cases are ever served to a student.
 *
 * A correction never overwrites what the engine measured: both numbers are kept,
 * and the difference between them is the evidence that validates the engine.
 *
 * Loaded data is stored together with the key it was loaded for, and "is this
 * still loading" is derived by comparing the two. Clearing state at the top of
 * an effect would set state during render and would show the previous case's
 * numbers under the new case's heading for a frame.
 */

const ORDERS = [
  { value: "BANK_FIRST", label: "Fill the bank first" },
  { value: "LEAST_CONFIDENT", label: "Least confident first" },
  { value: "OLDEST_FIRST", label: "Oldest first" },
];

/** Reads better than the raw enum, without inventing new vocabulary. */
const REASON_LABELS = {
  WRONG_MEASUREMENT: "Wrong measurement",
  POOR_SIGNAL_QUALITY: "Poor signal quality",
  WRONG_DIAGNOSIS_LABEL: "Wrong diagnosis label",
  UNSUITABLE_FOR_TEACHING: "Unsuitable for teaching",
  NARRATIVE_INCONSISTENT: "Narrative inconsistent",
  OTHER: "Other",
};

const MEASURE_LABELS = {
  heart_rate: "Rate",
  pr_interval: "PR interval",
  qrs_duration: "QRS duration",
  qt_interval: "QT interval",
  qtc_bazett: "QTc (Bazett)",
  qtc_fridericia: "QTc (Fridericia)",
  p_duration: "P duration",
};

function statusTone(status) {
  if (status === "OK") return "text-brand-success";
  if (status === "NOT_MEASURABLE") return "text-brand-muted";
  return "text-brand-warning";
}

/** Warnings are the engine's own words. Underscores are not. */
function humanWarning(warning) {
  return warning.replace(/[:_]/g, " ").replace(/\s+/g, " ").trim();
}

export default function ReviewQueue() {
  const [order, setOrder] = useState("BANK_FIRST");
  const [reloads, setReloads] = useState(0);
  const [queue, setQueue] = useState({ key: null, items: [], total: 0 });
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState({ caseId: null, data: null });
  const [options, setOptions] = useState({ rejectionReasons: [] });

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [flash, setFlash] = useState(null);

  const [corrections, setCorrections] = useState({});
  const [rejectionReason, setRejectionReason] = useState("WRONG_MEASUREMENT");
  const [note, setNote] = useState("");

  // Reviewer throughput is the critical path of this project, so how long each
  // case actually takes is measured rather than guessed at.
  const openedAt = useRef(null);

  const queueKey = `${order}:${reloads}`;
  const queueLoading = queue.key !== queueKey;
  const detailLoading = selected !== null && detail.caseId !== selected;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const page = await getQueue({ order, limit: 12 });
        if (cancelled) return;
        setQueue({ key: queueKey, items: page.items, total: page.total });
        setSelected(page.items.length ? page.items[0].caseId : null);
        setCorrections({});
        setNote("");
      } catch (exception) {
        if (!cancelled) setError(errorMessage(exception, "Could not load the review queue."));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [order, queueKey]);

  useEffect(() => {
    let cancelled = false;
    getReviewOptions()
      .then((loaded) => {
        if (!cancelled) setOptions(loaded);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (selected === null) return undefined;
    let cancelled = false;
    openedAt.current = Date.now();
    (async () => {
      try {
        const loaded = await getCase(selected);
        if (!cancelled) setDetail({ caseId: selected, data: loaded });
      } catch (exception) {
        if (!cancelled) setError(errorMessage(exception, "Could not load that case."));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selected]);

  const onSelect = useCallback((caseId) => {
    // Reset in the handler rather than in an effect: it is a response to the
    // reviewer's click, not a consequence of rendering.
    setSelected(caseId);
    setCorrections({});
    setNote("");
    setError(null);
    setFlash(null);
  }, []);

  const secondsSpent = () =>
    openedAt.current ? Math.max(0, Math.round((Date.now() - openedAt.current) / 1000)) : undefined;

  const editedMeasures = useMemo(
    () =>
      Object.entries(corrections)
        .filter(([, raw]) => raw !== "" && raw !== null && raw !== undefined)
        .map(([name, raw]) => ({ name, value: Number(raw) }))
        .filter((correction) => Number.isFinite(correction.value)),
    [corrections],
  );

  async function decide(action) {
    if (selected === null) return;
    setBusy(true);
    setError(null);
    setFlash(null);
    try {
      const outcome = await submitReview(selected, {
        action,
        corrections: action === "EDIT" ? editedMeasures : undefined,
        rejectionReason: action === "REJECT" ? rejectionReason : undefined,
        note: note || undefined,
        durationSeconds: secondsSpent(),
      });
      const recorded = outcome.correctionsRecorded?.length
        ? ` (${outcome.correctionsRecorded.join(", ")} corrected)`
        : "";
      setFlash(
        `Case ${outcome.caseId} ${outcome.reviewStatus}${recorded}. ` +
          `${outcome.pendingRemaining} still pending.`,
      );
      setReloads((count) => count + 1);
    } catch (exception) {
      // The server writes these messages for the person at the screen: a refused
      // correction names the measure and the range that would have been
      // accepted, so it is shown rather than replaced.
      setError(errorMessage(exception, "The review was not recorded."));
    } finally {
      setBusy(false);
    }
  }

  const shown = detail.caseId === selected ? detail.data : null;

  return (
    <Layout role="FACULTY">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Review Queue</h1>
          <p className="text-brand-muted mt-1">
            {queue.total} case{queue.total === 1 ? "" : "s"} awaiting approval. Nothing reaches a
            student until a reviewer approves it.
          </p>
        </div>
        <label className="text-sm">
          <span className="text-brand-muted mr-2">Order</span>
          <select
            value={order}
            onChange={(event) => setOrder(event.target.value)}
            className="bg-brand-bg2 border border-white/10 rounded px-3 py-2 text-sm"
          >
            {ORDERS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {flash && (
        <div className="mt-6 rounded border border-brand-success/40 bg-brand-success/10 px-4 py-3 text-sm text-brand-success">
          {flash}
        </div>
      )}
      {error && (
        <div className="mt-6 rounded border border-brand-danger/40 bg-brand-danger/10 px-4 py-3 text-sm text-brand-danger">
          {error}
        </div>
      )}

      {queueLoading ? (
        <p className="text-brand-muted mt-8">Loading the queue…</p>
      ) : queue.items.length === 0 ? (
        <div className="card p-8 mt-8 text-center">
          <p className="font-semibold">Nothing left to review.</p>
          <p className="text-brand-muted text-sm mt-1">
            Every measured case has been approved, corrected or rejected.
          </p>
        </div>
      ) : (
        <div className="grid lg:grid-cols-[320px_1fr] gap-6 mt-8">
          {/* the queue */}
          <div className="space-y-3 max-h-[70vh] overflow-y-auto pr-1">
            {queue.items.map((item) => (
              <button
                key={item.caseId}
                onClick={() => onSelect(item.caseId)}
                className={`card w-full text-left p-4 transition ${
                  item.caseId === selected ? "ring-2 ring-brand-primary" : ""
                }`}
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-semibold text-sm">ECG {item.sourceEcgId}</span>
                  <span className={`text-xs ${statusTone(item.measurementStatus)}`}>
                    {Math.round(item.overallConfidence * 100)}%
                  </span>
                </div>
                <p className="text-xs text-brand-muted mt-1">
                  {item.conditionCodes.join(", ") || "no condition tagged"}
                </p>
                <p className="text-xs text-brand-muted mt-1">
                  {item.sex}
                  {item.age ? `, ${Math.round(item.age)}` : ""} · {item.nBeats} beats
                </p>
                {item.warnings.length > 0 && (
                  <p className="text-xs text-brand-warning mt-2">
                    {item.warnings.length} warning{item.warnings.length === 1 ? "" : "s"}
                  </p>
                )}
              </button>
            ))}
          </div>

          {/* the case */}
          {detailLoading || !shown ? (
            <div className="card p-8 text-brand-muted">Loading case…</div>
          ) : (
            <div className="space-y-6">
              <div className="card overflow-hidden">
                <EcgImage caseId={shown.id} kind="clean" height={260} />
                <div className="p-5">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <h2 className="text-xl font-semibold">ECG {shown.sourceEcgId}</h2>
                    <span className={`text-sm ${statusTone(shown.measurementStatus)}`}>
                      {shown.measurementStatus} · {Math.round(shown.overallConfidence * 100)}%
                      confidence
                    </span>
                  </div>
                  <p className="text-sm text-brand-muted mt-2">
                    {shown.sex}
                    {shown.age ? `, ${Math.round(shown.age)}` : ""}
                    {shown.ageCensored ? " or older" : ""} · {shown.nBeats} beats ·{" "}
                    {shown.rhythmRegularity?.toLowerCase().replace(/_/g, " ")} · axis{" "}
                    {shown.axisCategory?.toLowerCase()}
                  </p>
                  <p className="text-xs text-brand-muted mt-3">
                    <span className="font-semibold">Cardiologist annotation:</span>{" "}
                    {shown.diagnosticLabels.join("; ")}
                  </p>
                  {shown.warnings.length > 0 && (
                    <ul className="mt-3 space-y-1">
                      {shown.warnings.map((warning) => (
                        <li key={warning} className="text-xs text-brand-warning">
                          • {humanWarning(warning)}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>

              {/* measurements, editable */}
              <div className="card p-5">
                <h3 className="font-semibold">Computed measurements</h3>
                <p className="text-xs text-brand-muted mt-1">
                  Spread is median absolute deviation across beats. Type a value only to correct it;
                  the engine's number is kept either way.
                </p>
                <div className="mt-4 space-y-2">
                  {shown.measurements.map((measure) => (
                    <div
                      key={measure.name}
                      className="grid grid-cols-[1fr_auto_auto] items-center gap-3 text-sm border-b border-white/5 pb-2"
                    >
                      <div>
                        <span className="font-medium">
                          {MEASURE_LABELS[measure.name] || measure.name}
                        </span>
                        <span className={`ml-2 text-xs ${statusTone(measure.status)}`}>
                          {measure.status === "NOT_MEASURABLE"
                            ? "not measurable"
                            : measure.status.toLowerCase().replace(/_/g, " ")}
                        </span>
                      </div>
                      <div className="text-right">
                        <span className="font-mono">
                          {measure.value === null ? "—" : measure.value.toFixed(0)}
                        </span>
                        <span className="text-brand-muted text-xs ml-1">{measure.unit}</span>
                        {measure.mad !== null && (
                          <span className="text-brand-muted text-xs ml-2">
                            ±{measure.mad.toFixed(0)}
                          </span>
                        )}
                      </div>
                      <input
                        type="number"
                        step="1"
                        placeholder="correct"
                        value={corrections[measure.name] ?? ""}
                        onChange={(event) =>
                          setCorrections({ ...corrections, [measure.name]: event.target.value })
                        }
                        className="w-24 bg-brand-bg2 border border-white/10 rounded px-2 py-1 text-sm text-right"
                      />
                    </div>
                  ))}
                </div>
              </div>

              {/* the decision */}
              <div className="card p-5">
                <h3 className="font-semibold">Decision</h3>
                <textarea
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  rows={2}
                  placeholder="Note (optional)"
                  className="w-full mt-3 bg-brand-bg2 border border-white/10 rounded px-3 py-2 text-sm"
                />
                <div className="flex flex-wrap items-center gap-3 mt-4">
                  <button
                    disabled={busy || editedMeasures.length > 0}
                    onClick={() => decide("APPROVE")}
                    className="btn-primary text-sm"
                    title={
                      editedMeasures.length > 0
                        ? "Clear the corrections to approve as measured"
                        : "The measurements are right as computed"
                    }
                  >
                    Approve as measured
                  </button>
                  <button
                    disabled={busy || editedMeasures.length === 0}
                    onClick={() => decide("EDIT")}
                    className="btn-primary text-sm"
                    title={
                      editedMeasures.length === 0
                        ? "Type at least one corrected value first"
                        : "Record the corrections and approve"
                    }
                  >
                    Save {editedMeasures.length || ""} correction
                    {editedMeasures.length === 1 ? "" : "s"}
                  </button>
                  <span className="flex items-center gap-2 ml-auto">
                    <select
                      value={rejectionReason}
                      onChange={(event) => setRejectionReason(event.target.value)}
                      className="bg-brand-bg2 border border-white/10 rounded px-2 py-2 text-xs"
                    >
                      {(options.rejectionReasons || []).map((reason) => (
                        <option key={reason} value={reason}>
                          {REASON_LABELS[reason] || reason}
                        </option>
                      ))}
                    </select>
                    <button
                      disabled={busy}
                      onClick={() => decide("REJECT")}
                      className="btn-ghost text-sm"
                    >
                      Reject
                    </button>
                  </span>
                </div>
                <p className="text-xs text-brand-muted mt-3">
                  A rejection always records a reason: the rejection log is reported as a
                  pipeline-accuracy measure.
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </Layout>
  );
}
