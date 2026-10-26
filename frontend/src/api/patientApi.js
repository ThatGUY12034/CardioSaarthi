import axiosClient from "./axiosClient";

/**
 * Layer 4: a patient's own report.
 *
 * <p>Nothing here takes a patient id. Every endpoint is scoped to the
 * authenticated caller on the server, because a patient identifier a client can
 * choose is one it can choose to be somebody else's.
 */

/** Reports issued to this patient, newest first. */
export async function getReports() {
  const { data } = await axiosClient.get("/patient/reports");
  return data;
}

/**
 * One report: the computed findings, each with its approved explanation where
 * one exists. A finding with no approved sentence comes back `explained: false`
 * and is shown named but unexplained rather than filled in.
 */
export async function getReport(id) {
  const { data } = await axiosClient.get(`/patient/reports/${id}`);
  return data;
}

/** Plain-language definitions, faculty-approved. */
export async function getGlossary() {
  const { data } = await axiosClient.get("/patient/glossary");
  return data;
}
