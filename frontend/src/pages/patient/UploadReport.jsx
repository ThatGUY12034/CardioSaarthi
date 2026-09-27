import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";

export default function UploadReport() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);

  const handleUpload = (e) => {
    e.preventDefault();
    // TODO: POST to backend → get reportId
    setTimeout(() => navigate("/patient/report/new"), 800);
  };

  return (
    <Layout role="PATIENT">
      <h1 className="text-3xl font-bold">Upload ECG Report</h1>
      <p className="text-brand-muted mt-1">
        Upload a photo or PDF of your ECG report to get a simple explanation
      </p>

      <form onSubmit={handleUpload} className="card p-8 mt-8 max-w-xl">
        <label className="border-2 border-dashed border-white/10 hover:border-brand-primary/50 rounded-xl p-12 flex flex-col items-center cursor-pointer transition-colors">
          <div className="text-4xl mb-3">📄</div>
          <p className="text-sm text-brand-muted">
            {file ? file.name : "Click to upload or drag & drop"}
          </p>
          <p className="text-xs text-brand-muted mt-1">PDF, JPG, PNG (max 10 MB)</p>
          <input
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
            className="hidden"
            onChange={(e) => setFile(e.target.files[0])}
          />
        </label>

        <button type="submit" className="btn-primary w-full mt-6" disabled={!file}>
          Analyze Report
        </button>
      </form>
    </Layout>
  );
}