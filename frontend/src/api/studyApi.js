import axiosClient from "./axiosClient";

/**
 * The student runtime endpoints.
 *
 * <p>The nine steps are locked in order by the server, so the console does not
 * decide what comes next: it submits an answer and is told what happens. That is
 * the point of section 5.1 of the brief -- control flow is the server's, not the
 * client's and not a model's.
 */

/** Approved cases a student may practise on. Nothing unreviewed appears here. */
export async function getPractisableCases(limit = 24) {
  const { data } = await axiosClient.get("/study/cases", { params: { limit } });
  return data;
}

/**
 * The patient around the tracing: complaint, history, examination, vitals, labs.
 *
 * <p>Returns null when the case has no scenario written yet, which is a fact
 * about the case rather than a failure -- the trace is shown without a brief.
 */
export async function getCaseBrief(caseId) {
  const response = await axiosClient.get(`/study/cases/${caseId}/brief`);
  return response.status === 204 ? null : response.data;
}

/**
 * This student's own record: counts, average, streak, cases available.
 *
 * <p>Every figure is derived from the attempt record. The pages that show them
 * previously held constants.
 */
export async function getProgress() {
  const { data } = await axiosClient.get("/study/progress");
  return data;
}

/** Per-concept strength across the nine steps, weakest visible first. */
export async function getConceptStrength() {
  const { data } = await axiosClient.get("/study/progress/concepts");
  return data;
}

/** What the scheduler says to practise next, with the reason attached. */
export async function getNextConcepts(limit = 3) {
  const { data } = await axiosClient.get("/study/progress/next", { params: { limit } });
  return data;
}

/** Recent sessions with their scores, newest first. */
export async function getRecentSessions(limit = 10) {
  const { data } = await axiosClient.get("/study/progress/sessions", { params: { limit } });
  return data;
}

/** Positions without names: a ranking that identifies the bottom is a disclosure. */
export async function getLeaderboard(limit = 10) {
  const { data } = await axiosClient.get("/study/progress/leaderboard", { params: { limit } });
  return data;
}

/**
 * Remarks a teacher left on this student's attempts, unread first.
 *
 * <p>A remark cannot be edited once sent; marking it read is the one change
 * permitted, and a database trigger enforces the rest.
 */
export async function getRemarks(limit = 20) {
  const { data } = await axiosClient.get("/study/remarks", { params: { limit } });
  return data;
}

/** Opening a remark marks it read. */
export async function markRemarkRead(id) {
  await axiosClient.post(`/study/remarks/${id}/read`);
}

/** The nine steps, and what each accepts. Served so the form cannot drift. */
export async function getSteps() {
  const { data } = await axiosClient.get("/study/steps");
  return data;
}

/** @param mode BEGINNER_TUTOR, CLINICAL_MENTOR or EXAMINER */
export async function startSession(caseId, mode = "BEGINNER_TUTOR") {
  const { data } = await axiosClient.post("/study/sessions", { caseId, mode });
  return data;
}

export async function getSession(sessionId) {
  const { data } = await axiosClient.get(`/study/sessions/${sessionId}`);
  return data;
}

/**
 * Answer the current step.
 *
 * @param answer {value} | {notPresent:true} | {category} | {leads:[]}
 * @returns the turn: whether it was right, what feedback, whether it advanced.
 *          The expected value is only included once the step is finished with,
 *          so a hint cannot leak it.
 */
export async function submitAnswer(sessionId, step, answer, timeTakenMs) {
  const { data } = await axiosClient.post(`/study/sessions/${sessionId}/answer`, {
    step,
    answer,
    timeTakenMs,
  });
  return data;
}

export async function finishSession(sessionId, interpretation) {
  const { data } = await axiosClient.post(`/study/sessions/${sessionId}/finish`, { interpretation });
  return data;
}

export async function getSummary(sessionId) {
  const { data } = await axiosClient.get(`/study/sessions/${sessionId}/summary`);
  return data;
}

export function errorMessage(error, fallback = "Something went wrong.") {
  // The server's own message first: it is written for a person and says what
  // was actually refused.
  const fromServer = error?.response?.data?.message;
  if (fromServer) return fromServer;

  // Then the statuses the server answers without a body. Axios turns these
  // into "Request failed with status code 401", which tells a user nothing and
  // reads like a leaked stack trace.
  const status = error?.response?.status;
  if (status === 401) return "You are not signed in, or your session has ended. Sign in again.";
  if (status === 403) return "Your account does not have access to this.";
  if (status === 404) return "That is not here.";
  if (status === 409) return "Someone else changed this first. Reload and try again.";
  if (status >= 500) return "The server could not complete that. Try again in a moment.";

  // No response at all: the request never arrived.
  if (error?.code === "ERR_NETWORK") {
    return "The server could not be reached. Check that it is running.";
  }
  return fallback;
}
