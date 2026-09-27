import { Link } from "react-router-dom";
import Layout from "../../components/Layout";
import CaseEcg from "../../components/CaseEcg";

export default function PatientDashboard() {
  return (
    <Layout role="PATIENT">
      <h1 className="text-3xl font-bold">Welcome back 👋</h1>
      <p className="text-brand-muted mt-1">Understand your ECG reports in simple language</p>

      <div className="card p-6 mt-8">
        <h3 className="font-semibold mb-4">Your Latest Report</h3>
        <div className="flex flex-col md:flex-row gap-6">
          <div className="md:w-1/2">
            <CaseEcg height={180} label="Report Date: 27 Apr 2026" />
          </div>
          <div className="flex-1">
            <h4 className="font-medium">Simple Explanation</h4>
            <p className="text-sm text-brand-muted mt-2">
              Your ECG shows a normal heart rhythm. The heart is beating at a regular
              rate and the electrical activity looks normal.
            </p>
            <span className="inline-block text-xs px-2 py-1 rounded bg-brand-success/20 text-brand-success mt-3">
              ● Normal
            </span>
            <Link to="/patient/report/1" className="btn-primary block text-center mt-5 text-sm">
              View Full Report
            </Link>
          </div>
        </div>
      </div>
    </Layout>
  );
}