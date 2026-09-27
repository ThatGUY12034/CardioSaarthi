import { useCallback, useEffect, useState } from "react";
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
 * Case approval: expand a case, verify all nine parameters, correct any of them.
 *
 * <p>The difference from the review queue is the shape of the work. The queue is
 * for working through cases one after another; this is for looking over several,
 * opening the ones that need attention, and correcting them. Both post the same
 * review, so a case decided here leaves the queue too.
 *
 * <p>All nine parameters are editable, including the four that are not numbers.
 * Those four are where the engine is most often wrong -- a fibrillation case can
 * arrive with the rhythm called regularly irregular, P waves called present and
 * a PR interval measured off waves that are not P waves -- and until they were
 * correctable a reviewer could see the mistake and not fix it.
 */

const RHYTHMS = ["REGULAR", "REGULARLY_IRREGULAR", "IRREGULARLY_IRREGULAR", "INDETERMINATE"];
const AXES = ["NORMAL", "LEFT", "RIGHT", "EXTREME", "INDETERMINATE"];
const P_WAVES = ["PRESENT", "ABSENT"];

/**
 * What each categorical parameter may be set to.
 *
 * <p>t_waves is deliberately absent. The engine does not compute T-wave
 * polarity, so there is nothing to correct and the server refuses a correction
 * to it. Offering an input that can only fail is worse than offering none.
 */
const CATEGORY_OPTIONS = { rhythm: RHYTHMS, axis: AXES, p_waves: P_WAVES };
const LEADS = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"];

const REASON_LABELS = {
  WRONG_MEASUREMENT: "Wrong measurement",
  POOR_SIGNAL_QUALITY: "Poor signal quality",
  WRONG_DIAGNOSIS_LABEL: "Wrong diagnosis label",
  UNSUITABLE_FOR_TEACHING: "Unsuitable for teaching",
  NARRATIVE_INCONSISTENT: "Narrative inconsistent",
  OTHER: "Other",
};

function human(value) {
  if (value === null || value === undefined || value === "") return "—";
  return String(value).replace(/_/g, " ").toLowerCase();
}

function statusTone(status) {
  if (status === "OK") return "text-brand-success";
  if (status === "NOT_MEASURABLE") return "text-brand-muted";
  return "text-brand-warning";
}

/** One parameter row, with the right input for its kind. */
function ParameterRow({ parameter, draft, onChange }) {
  const edited = draft !== undefined && draft !== "";
  const shown = parameter.kind === "NUMERIC"
    ? (parameter.value === null ? "—" : parameter.value.toFixed(0))
    : human(parameter.textValue);

  return (
    <div className="grid grid-cols-[2rem_1fr_auto_minmax(11rem,auto)] items-center gap-3 text-sm border-b border-white/5 py-2">
      <span className="text-brand-muted text-xs">{parameter.step}</span>

      <div>
        <span className="font-medium">{parameter.label}</span>
        <span className={`ml-2 text-xs ${statusTone(parameter.status)}`}>
          {parameter.status === "NOT_MEASURABLE" ? "not measurable" : human(parameter.status)}
        </span>
        {parameter.corrected && (
          <span className="ml-2 text-xs text-brand-accent">corrected</span>
        )}
      </div>

      <div className="text-right whitespace-nowrap">
        <span className="font-mono">{shown}</span>
        {parameter.unit && parameter.value !== null && (
          <span className="text-brand-muted text-xs ml-1">{parameter.unit}</span>
        )}
        {parameter.mad !== null && parameter.mad !== undefined && (
          <span className="text-brand-muted text-xs ml-2">±{parameter.mad.toFixed(0)}</span>
        )}
      </div>

      {parameter.kind === "NUMERIC" ? (
        <input
          type="number"
          step="1"
          placeholder="correct"
          value={draft ?? ""}
          onChange={(event) => onChange(parameter.name, event.target.value)}
          className={`w-full bg-brand-bg2 border rounded px-2 py-1 text-sm text-right ${
            edited ? "border-brand-accent" : "border-white/10"
          }`}
        />
      ) : parameter.name === "st_segment" ? (
        <LeadPicker
          value={draft ?? parameter.textValue ?? ""}
          onChange={(value) => onChange(parameter.name, value)}
        />
      ) : CATEGORY_OPTIONS[parameter.name] ? (
        <select
          value={draft ?? parameter.textValue ?? ""}
          onChange={(event) => onChange(parameter.name, event.target.value)}
          className={`w-full bg-brand-bg2 border rounded px-2 py-1 text-sm ${
            edited ? "border-brand-accent" : "border-white/10"
          }`}
        >
          <option value="">—</option>
          {CATEGORY_OPTIONS[parameter.name].map((option) => (
            <option key={option} value={option}>{human(option)}</option>
          ))}
        </select>
      ) : (
        <span className="text-[11px] text-brand-muted text-right">
          not computed yet
        </span>
      )}
    </div>
  );
}

/** Twelve toggles, because typing lead names invites typos the server then rejects. */
function LeadPicker({ value, onChange }) {
  const selected = value ? value.split(",").filter(Boolean) : [];
  const toggle = (lead) => {
    const next = selected.includes(lead)
      ? selected.filter((item) => item !== lead)
      : [...selected, lead];
    onChange(LEADS.filter((item) => next.includes(item)).join(","));
  };

  return (
    <div className="flex flex-wrap gap-1 justify-end">
      {LEADS.map((lead) => (
        <button
          key={lead}
          type="button"
          onClick={() => toggle(lead)}
          className={`text-[11px] px-1.5 py-0.5 rounded border ${
            selected.includes(lead)
              ? "border-brand-accent text-brand-accent"
              : "border-white/10 text-brand-muted"
          }`}
        >
          {lead}
        </button>
      ))}
    </div>
  );
}

export default function CaseApproval() {
  const [reloads, setReloads] = useState(0);
  const [queue, setQueue] = useState({ key: null, items: [], total: 0 });
  const [expanded, setExpanded] = useState(null);
  const [detail, setDetail] = useState({ caseId: null, data: null });
  const [drafts, setDrafts] = useState({});
  const [options, setOptions] = useState({ rejectionReasons: [] });
  const [rejectionReason, setRejectionReason] = useState("WRONG_MEASUREMENT");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [flash, setFlash] = useState(null);

  const queueKey = `approvals:${reloads}`;
  const loading = queue.key !== queueKey;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const page = await getQueue({ order: "BANK_FIRST", limit: 12 });
        if (!cancelled) setQueue({ key: queueKey, items: page.items, total: page.total });
      } catch (exception) {
        if (!cancelled) setError(errorMessage(exception, "Could not load the cases."));
      }
    })();
    return () => { cancelled = true; };
  }, [queueKey]);

  useEffect(() => {
    getReviewOptions().then(setOptions).catch(() => {});
  }, []);

  useEffect(() => {
    if (expanded === null) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const loaded = await getCase(expanded);
        if (!cancelled) setDetail({ caseId: expanded, data: loaded });
      } catch (exception) {
        if (!cancelled) setError(errorMessage(exception, "Could not load that case."));
      }
    })();
    return () => { cancelled = true; };
  }, [expanded]);

  const toggle = useCallback((caseId) => {
    setExpanded((current) => (current === caseId ? null : caseId));
    setDrafts({});
    setError(null);
    setFlash(null);
  }, []);

  const onDraft = useCallback((name, value) => {
    setDrafts((current) => ({ ...current, [name]: value }));
  }, []);

  const shown = detail.caseId === expanded ? detail.data : null;

  /** Only values the reviewer actually changed become corrections. */
  const corrections = shown
    ? Object.entries(drafts)
        .map(([name, raw]) => {
          const parameter = shown.parameters.find((p) => p.name === name);
          if (!parameter || raw === "" || raw === null || raw === undefined) return null;
          if (parameter.kind === "NUMERIC") {
            const value = Number(raw);
            return Number.isFinite(value) ? { name, value } : null;
          }
          // Unchanged text is not a correction; the server would reject it as
          // an edit that changed nothing.
          if (String(raw) === String(parameter.textValue ?? "")) return null;
          return { name, text: String(raw) };
        })
        .filter(Boolean)
    : [];

  async function decide(action) {
    if (expanded === null) return;
    setBusy(true);
    setError(null);
    setFlash(null);
    try {
      const outcome = await submitReview(expanded, {
        action,
        corrections: action === "EDIT" ? corrections : undefined,
        rejectionReason: action === "REJECT" ? rejectionReason : undefined,
      });
      const recorded = outcome.correctionsRecorded?.length
        ? ` (${outcome.correctionsRecorded.join(", ")} corrected)`
        : "";
      setFlash(`Case ${outcome.caseId} ${outcome.reviewStatus}${recorded}.`);
      setExpanded(null);
      setDrafts({});
      setReloads((count) => count + 1);
    } catch (exception) {
      setError(errorMessage(exception, "The review was not recorded."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Layout role="FACULTY">
      <h1 className="text-3xl font-bold">Case Approval</h1>
      <p className="text-brand-muted mt-1">
        Open a case to verify all nine interpretation parameters. Correct any of them; the engine's
        value is kept either way.
      </p>

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

      {loading ? (
        <p className="text-brand-muted mt-8">Loading cases…</p>
      ) : (
        <div className="space-y-3 mt-8">
          {queue.items.map((item) => {
            const open = item.caseId === expanded;
            return (
              <div key={item.caseId} className="card overflow-hidden">
                <button
                  onClick={() => toggle(item.caseId)}
                  className="w-full text-left p-5 flex flex-wrap items-center gap-4"
                >
                  <span className="text-brand-muted text-xs w-4">{open ? "▾" : "▸"}</span>
                  <span className="font-semibold">ECG {item.sourceEcgId}</span>
                  <span className="text-xs text-brand-muted">
                    {item.conditionCodes.join(", ") || "no condition tagged"}
                  </span>
                  <span className="text-xs text-brand-muted">
                    {item.sex}{item.age ? `, ${Math.round(item.age)}` : ""} · {item.nBeats} beats
                  </span>
                  {item.warnings.length > 0 && (
                    <span className="text-xs text-brand-warning">
                      {item.warnings.length} warning{item.warnings.length === 1 ? "" : "s"}
                    </span>
                  )}
                  <span className="ml-auto text-xs text-brand-muted">
                    {Math.round(item.overallConfidence * 100)}% confidence
                  </span>
                </button>

                {open && (
                  !shown ? (
                    <p className="px-5 pb-5 text-brand-muted text-sm">Loading case…</p>
                  ) : (
                    <div className="px-5 pb-5 space-y-5">
                      <EcgImage caseId={shown.id} kind="clean" height={240} className="rounded" />

                      <p className="text-xs text-brand-muted">
                        <span className="font-semibold">Cardiologist annotation:</span>{" "}
                        {shown.diagnosticLabels.join("; ")}
                      </p>
                      {shown.warnings.length > 0 && (
                        <ul className="space-y-1">
                          {shown.warnings.map((warning) => (
                            <li key={warning} className="text-xs text-brand-warning">
                              • {warning.replace(/[:_]/g, " ")}
                            </li>
                          ))}
                        </ul>
                      )}

                      <div>
                        <h3 className="font-semibold text-sm mb-2">
                          The nine parameters a student is examined on
                        </h3>
                        {shown.parameters.map((parameter) => (
                          <ParameterRow
                            key={parameter.name}
                            parameter={parameter}
                            draft={drafts[parameter.name]}
                            onChange={onDraft}
                          />
                        ))}
                      </div>

                      <div className="flex flex-wrap items-center gap-3">
                        <button
                          disabled={busy || corrections.length > 0}
                          onClick={() => decide("APPROVE")}
                          className="btn-primary text-sm"
                        >
                          Approve as measured
                        </button>
                        <button
                          disabled={busy || corrections.length === 0}
                          onClick={() => decide("EDIT")}
                          className="btn-primary text-sm"
                        >
                          Save {corrections.length || ""} correction
                          {corrections.length === 1 ? "" : "s"}
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
                          <button disabled={busy} onClick={() => decide("REJECT")} className="btn-ghost text-sm">
                            Reject
                          </button>
                        </span>
                      </div>
                    </div>
                  )
                )}
              </div>
            );
          })}
        </div>
      )}
    </Layout>
  );
}
