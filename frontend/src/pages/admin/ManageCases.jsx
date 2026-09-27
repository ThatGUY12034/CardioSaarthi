import Layout from "../../components/Layout";

const CASES = [
  { id: 1, title: "Normal Sinus Rhythm", status: "Published", difficulty: "Easy" },
  { id: 2, title: "Atrial Fibrillation", status: "Published", difficulty: "Medium" },
  { id: 18, title: "Ventricular Tachycardia", status: "Pending", difficulty: "Hard" },
];

export default function ManageCases() {
  return (
    <Layout role="ADMIN">
      <h1 className="text-3xl font-bold">Manage Cases</h1>
      <p className="text-brand-muted mt-1">View and manage all ECG cases</p>

      <div className="card mt-8 overflow-x-auto">
        <table className="w-full text-sm min-w-[600px]">
          <thead className="bg-brand-cardLight text-brand-muted text-xs uppercase">
            <tr>
              <th className="text-left px-5 py-3">ID</th>
              <th className="text-left px-5 py-3">Title</th>
              <th className="text-left px-5 py-3">Difficulty</th>
              <th className="text-left px-5 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {CASES.map((c) => (
              <tr key={c.id} className="border-t border-white/5 hover:bg-white/5">
                <td className="px-5 py-4">{c.id}</td>
                <td className="px-5 py-4 font-medium">{c.title}</td>
                <td className="px-5 py-4">{c.difficulty}</td>
                <td className="px-5 py-4">
                  <span
                    className={`text-xs px-2 py-1 rounded ${
                      c.status === "Published"
                        ? "bg-brand-success/20 text-brand-success"
                        : "bg-brand-warning/20 text-brand-warning"
                    }`}
                  >
                    {c.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}