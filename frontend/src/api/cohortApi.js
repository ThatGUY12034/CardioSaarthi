import axiosClient from "./axiosClient";

/**
 * What a teacher can see of their students, and what they can say back.
 *
 * <p>The figures here are the same ones the student sees on their own pages. A
 * teacher and a student getting different numbers for the same thing is worse
 * than either of them having no number.
 */

/** The class, ordered by who has done the most. */
export async function getStudents(cohort = null) {
  const { data } = await axiosClient.get("/cohort/students", { params: { cohort } });
  return data;
}

/** One student: concept strength, every mistake, and their learning gain. */
export async function getStudent(id) {
  const { data } = await axiosClient.get(`/cohort/students/${id}`);
  return data;
}

/** Per-step difficulty across the whole class. */
export async function getDifficulty() {
  const { data } = await axiosClient.get("/cohort/difficulty");
  return data;
}

/** The mistakes the class makes most, by name. */
export async function getCohortErrors(limit = 15) {
  const { data } = await axiosClient.get("/cohort/errors", { params: { limit } });
  return data;
}

/** Remarks already left on one attempt. */
export async function getRemarks(sessionStepId) {
  const { data } = await axiosClient.get(`/cohort/attempts/${sessionStepId}/remarks`);
  return data;
}

/**
 * Leave a remark on the attempt that went wrong.
 *
 * <p>It cannot be edited afterwards, only marked read by the student: a remark
 * is a record of what was said.
 */
export async function addRemark(sessionStepId, body) {
  const { data } = await axiosClient.post(`/cohort/attempts/${sessionStepId}/remarks`, { body });
  return data;
}
