import { Link } from "react-router-dom";
import Layout from "../../components/Layout";

/**
 * Uploading your own ECG: not something this platform can do.
 *
 * <p>What stood here before accepted a file, waited eight hundred milliseconds
 * to look like work, and sent the patient to a report that had never been
 * created. Nothing was uploaded, nothing was read, and the button said "Analyze
 * Report". A screen that fakes a clinical result is worse than a screen that
 * admits it has none.
 *
 * <p>There is no endpoint behind this and no measurement path for an arbitrary
 * photograph of a printout: the engine measures a twelve-lead digital recording,
 * not an image of one. So the page says so, and points at what the platform does
 * do -- reports a clinician has issued, which arrive on the dashboard.
 */
export default function UploadReport() {
  return (
    <Layout role="PATIENT">
      <h1 className="page-title">Upload an ECG report</h1>
      <p className="page-subtitle">Not available yet, and not pretending otherwise.</p>

      <div className="card p-6 mt-8 max-w-2xl">
        <div className="flex items-start gap-3">
          <span
            aria-hidden="true"
            className="shrink-0 w-8 h-8 rounded-full bg-brand-warning/15 text-brand-warning grid place-items-center text-sm"
          >
            !
          </span>
          <div>
            <h2 className="font-semibold">You cannot upload a report here</h2>
            <p className="text-sm text-brand-muted mt-2 leading-relaxed">
              CardioSaarthi reads twelve-lead recordings from the clinical databases it was
              built on. It cannot measure a photograph or a PDF of a printed report, so there
              is nothing for a file to be sent to.
            </p>
          </div>
        </div>
      </div>

      <div className="card p-6 mt-5 max-w-2xl">
        <h2 className="font-semibold">What you can do</h2>
        <ul className="mt-3 space-y-3 text-sm text-brand-muted">
          <li className="flex gap-3">
            <span aria-hidden="true" className="text-brand-accent">→</span>
            <span>
              <span className="text-brand-text">Read a report issued to you.</span> When a
              clinician issues one through this platform it appears on your dashboard, with
              each finding explained in plain language.
            </span>
          </li>
          <li className="flex gap-3">
            <span aria-hidden="true" className="text-brand-accent">→</span>
            <span>
              <span className="text-brand-text">Look up a term.</span> The glossary explains
              the words that appear on an ECG report, in wording a clinician has approved.
            </span>
          </li>
        </ul>
        <div className="flex flex-wrap gap-3 mt-6">
          <Link to="/patient/dashboard" className="btn-primary text-sm">
            Go to my reports
          </Link>
          <Link to="/patient/glossary" className="btn-ghost text-sm">
            Open the glossary
          </Link>
        </div>
      </div>

      <p className="text-xs text-brand-muted mt-6 max-w-2xl">
        If you have a printed ECG you want explained, take it to the clinician who ordered it.
        Nothing on this platform is a diagnosis, and nothing here replaces that conversation.
      </p>
    </Layout>
  );
}
