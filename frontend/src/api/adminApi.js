import axiosClient from "./axiosClient";

/**
 * Running the installation.
 *
 * <p>Every endpoint here is administrator-only, enforced at the filter chain as
 * well as on the controller.
 */

/** Counts across the whole platform, read live from the database. */
export async function getOverview() {
  const { data } = await axiosClient.get("/admin/overview");
  return data;
}

/** All three populations, or one of them. `kind` is reviewer, student or patient. */
export async function getUsers(kind = null) {
  const { data } = await axiosClient.get("/admin/users", { params: { kind } });
  return data;
}

/**
 * Revoke or restore access.
 *
 * <p>Deactivation, never deletion: a reviewer's decisions and a student's
 * attempts are the evidence this platform exists to preserve, and removing the
 * person removes the attribution on all of it.
 */
export async function setActive(kind, id, active) {
  const { data } = await axiosClient.post(`/admin/users/${kind}/${id}/active`, { active });
  return data;
}

/** Syllabus coverage per condition, thinnest first. */
export async function getCoverage() {
  const { data } = await axiosClient.get("/admin/coverage");
  return data;
}
