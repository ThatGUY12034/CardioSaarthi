import { useState } from "react";
import { enrolStudent } from "../api/adminApi";
import { errorMessage } from "../api/studyApi";
import { InlineError } from "./States";

/**
 * Enrolling a real student.
 *
 * <p>Until now the only student account that existed was the seeded
 * demonstration one, so every figure a teacher saw belonged to "Demo Student".
 * The endpoint has been here; the form had not been built, which is the whole
 * reason the class list said enrolment was on the administration pages and
 * then offered nothing.
 *
 * <p>Twelve characters minimum, checked here so the person typing finds out
 * before they submit, and checked again by the server because a client-side
 * rule is a convenience and not a control. The four-digit demonstration logins
 * come from a configuration flag and cannot be created through this form.
 */

const EMPTY = { fullName: "", collegeId: "", email: "", cohort: "", password: "" };

export default function EnrolStudentForm({ onEnrolled }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [flash, setFlash] = useState(null);

  const set = (field) => (event) =>
    setForm((current) => ({ ...current, [field]: event.target.value }));

  const tooShort = form.password.length > 0 && form.password.length < 12;
  const ready =
    form.fullName.trim() && form.collegeId.trim() && form.email.trim() &&
    form.password.length >= 12;

  const submit = async (event) => {
    event.preventDefault();
    if (!ready) return;
    setBusy(true);
    setError(null);
    try {
      const student = await enrolStudent({
        fullName: form.fullName.trim(),
        collegeId: form.collegeId.trim(),
        email: form.email.trim(),
        cohort: form.cohort.trim() || null,
        password: form.password,
      });
      // The password is never echoed back, here or anywhere else.
      setFlash(`${student.fullName} can now sign in with ${student.identifier}.`);
      setForm(EMPTY);
      onEnrolled?.();
    } catch (e) {
      setError(errorMessage(e, "That student was not enrolled."));
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <div className="mt-6">
        {flash && (
          <p className="mb-3 rounded-lg border border-brand-success/40 bg-brand-success/10 px-4 py-3 text-sm text-brand-success">
            {flash}
          </p>
        )}
        <button onClick={() => setOpen(true)} className="btn-primary text-sm">
          Enrol a student
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="card p-6 mt-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-semibold">Enrol a student</h2>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="text-xs text-brand-muted hover:text-brand-text"
        >
          Close
        </button>
      </div>
      <p className="text-xs text-brand-muted mt-1">
        An existing email address resets that student's password and details. Their attempts
        and any remarks left on them are kept.
      </p>

      {flash && (
        <p className="mt-4 rounded-lg border border-brand-success/40 bg-brand-success/10 px-4 py-3 text-sm text-brand-success">
          {flash}
        </p>
      )}
      {error && <div className="mt-4"><InlineError message={error} /></div>}

      <div className="grid sm:grid-cols-2 gap-4 mt-5">
        <label className="text-sm">
          <span className="block text-xs text-brand-muted mb-1">Full name</span>
          <input
            value={form.fullName}
            onChange={set("fullName")}
            required
            maxLength={200}
            placeholder="Aarav Patel"
            className="w-full bg-brand-bg2 border border-white/10 rounded-lg px-3 py-2"
          />
        </label>

        <label className="text-sm">
          <span className="block text-xs text-brand-muted mb-1">College ID</span>
          <input
            value={form.collegeId}
            onChange={set("collegeId")}
            required
            placeholder="TE23CS001"
            className="w-full bg-brand-bg2 border border-white/10 rounded-lg px-3 py-2"
          />
        </label>

        <label className="text-sm">
          <span className="block text-xs text-brand-muted mb-1">Email</span>
          <input
            type="email"
            value={form.email}
            onChange={set("email")}
            required
            placeholder="aarav.patel@terna.edu"
            className="w-full bg-brand-bg2 border border-white/10 rounded-lg px-3 py-2"
          />
        </label>

        <label className="text-sm">
          <span className="block text-xs text-brand-muted mb-1">
            Cohort <span className="text-brand-muted/70">(optional)</span>
          </span>
          <input
            value={form.cohort}
            onChange={set("cohort")}
            placeholder="BE-CMPN-A"
            className="w-full bg-brand-bg2 border border-white/10 rounded-lg px-3 py-2"
          />
        </label>

        <label className="text-sm sm:col-span-2">
          <span className="block text-xs text-brand-muted mb-1">
            Password <span className="text-brand-muted/70">(at least 12 characters)</span>
          </span>
          <input
            type="password"
            value={form.password}
            onChange={set("password")}
            required
            minLength={12}
            autoComplete="new-password"
            className={`w-full bg-brand-bg2 border rounded-lg px-3 py-2 ${
              tooShort ? "border-brand-danger/60" : "border-white/10"
            }`}
          />
          {tooShort && (
            <span className="block text-[11px] text-brand-danger mt-1">
              {12 - form.password.length} more character
              {12 - form.password.length === 1 ? "" : "s"} needed.
            </span>
          )}
        </label>
      </div>

      <div className="flex items-center gap-3 mt-5">
        <button type="submit" disabled={!ready || busy} className="btn-primary text-sm">
          {busy ? "Enrolling…" : "Enrol"}
        </button>
        <p className="text-[11px] text-brand-muted">
          Give the student their password yourself. It is hashed on arrival and cannot be
          read back from the platform.
        </p>
      </div>
    </form>
  );
}
