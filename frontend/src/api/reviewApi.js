import axiosClient from "./axiosClient";

/**
 * The faculty review endpoints.
 *
 * One module so that no page invents its own URL or its own idea of what an
 * action is called. The vocabulary for actions and rejection reasons is fetched
 * from the server rather than duplicated here, because the server validates
 * against a closed list and a copy in the client would eventually disagree
 * with it.
 */

/** A page of pending cases. Ordering is the server's policy, not ours. */
export async function getQueue({ order = "BANK_FIRST", condition, status, limit = 12, offset = 0 } = {}) {
  const { data } = await axiosClient.get("/queue", {
    params: { order, condition, status, limit, offset },
  });
  return data;
}

/** Everything about one case: measurements with spread and confidence, per-lead ST. */
export async function getCase(caseId) {
  const { data } = await axiosClient.get(`/cases/${caseId}`);
  return data;
}

/**
 * The rendered ECG, as an object URL.
 *
 * Fetched rather than pointed at with an img src, because these images are
 * behind the same authentication as everything else and a bare src sends no
 * Authorization header. Callers must revoke the URL when they are done with it
 * or the blob stays in memory for the life of the tab.
 */
export async function fetchEcgImage(caseId, kind = "clean") {
  const { data } = await axiosClient.get(`/cases/${caseId}/image/${kind}`, {
    responseType: "blob",
  });
  return URL.createObjectURL(data);
}

/**
 * Record a decision.
 *
 * @param action APPROVE, EDIT or REJECT
 * @param corrections [{name, value, note}] — required for EDIT, refused otherwise
 * @param rejectionReason required for REJECT, refused otherwise
 * @param durationSeconds how long the reviewer spent; worth sending, since
 *        reviewer throughput is the critical path of the whole project
 */
export async function submitReview(caseId, { action, corrections, rejectionReason, note, durationSeconds }) {
  const { data } = await axiosClient.post(`/cases/${caseId}/review`, {
    action,
    corrections,
    rejectionReason,
    note,
    durationSeconds,
  });
  return data;
}

/** Valid action and rejection-reason names, so a form cannot drift from the server. */
export async function getReviewOptions() {
  const { data } = await axiosClient.get("/review/options");
  return data;
}

/** How full the case bank is per syllabus condition, gaps included. */
export async function getConditions() {
  const { data } = await axiosClient.get("/conditions");
  return data;
}

/** Pipeline accuracy, measurement agreement and reviewer throughput. */
export async function getStats() {
  const { data } = await axiosClient.get("/stats");
  return data;
}

/**
 * Turn an API error into something a reviewer can act on.
 *
 * The server writes its messages for the person at the screen -- a refused
 * correction says which measure and what range would have been accepted -- so
 * the message is used when there is one rather than replaced with a generic
 * string.
 */
export function errorMessage(error, fallback = "Something went wrong.") {
  return error?.response?.data?.message || error?.message || fallback;
}
