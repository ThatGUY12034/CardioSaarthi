import Layout from "../../components/Layout";

const STUDENTS = [
  { name: "Aarav Patel", collegeId: "TE18/2023/C5001", avg: 92, streak: 7, status: "High" },
  { name: "Sneha Iyer", collegeId: "TE18/2023/C5005", avg: 88, streak: 5, status: "High" },
  { name: "Rohan Shah", collegeId: "TE18/2023/C5002", avg: 85, streak: 4, status: "High" },
  { name: "Isha Desai", collegeId: "TE18/2023/C5034", avg: 80, streak: 3, status: "Medium" },
  { name: "Aditya Nair", collegeId: "TE18/2023/C5041", avg: 72, streak: 2, status: "Medium" },
];

const statusColor = {
  High: "bg-brand-success/20 text-brand-success",
  Medium: "bg-brand-warning/20 text-brand-warning",
  Low: "bg-brand-danger/20 text-brand-danger",
};

export default function StudentPerformance() {
  return (
    <Layout role="FACULTY">
      <h1 className="text-3xl font-bold">Student Performance</h1>
      <p className="text-brand-muted mt-1">Monitor individual and cohort progress</p>

      <div className="card mt-8 overflow-hidden overflow-x-auto">
        <table className="w-full text-sm min-w-[700px]">
          <thead className="bg-brand-cardLight text-brand-muted text-xs uppercase">
            <tr>
              <th className="text-left px-5 py-3">Name</th>
              <th className="text-left px-5 py-3">College ID</th>
              <th className="text-left px-5 py-3">Avg Score</th>
              <th className="text-left px-5 py-3">Streak</th>
              <th className="text-left px-5 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {STUDENTS.map((s) => (
              <tr key={s.collegeId} className="border-t border-white/5 hover:bg-white/5">
                <td className="px-5 py-4 font-medium">{s.name}</td>
                <td className="px-5 py-4 text-brand-muted">{s.collegeId}</td>
                <td className="px-5 py-4">{s.avg}%</td>
                <td className="px-5 py-4">🔥 {s.streak} days</td>
                <td className="px-5 py-4">
                  <span className={`text-xs px-2 py-1 rounded ${statusColor[s.status]}`}>
                    {s.status}
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