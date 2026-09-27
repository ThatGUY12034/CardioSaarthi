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
  return error?.response?.data?.message || error?.message || fallback;
}
