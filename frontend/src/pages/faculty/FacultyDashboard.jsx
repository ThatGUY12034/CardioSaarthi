import Layout from "../../components/Layout";
import StatCard from "../../components/StatCard";

export default function FacultyDashboard() {
  return (
    <Layout role="FACULTY">
      <h1 className="text-3xl font-bold">Faculty Dashboard</h1>
      <p className="text-brand-muted mt-1">Overview of class performance & content</p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mt-8">
        <StatCard icon="👥" label="Total Students" value="32" />
        <StatCard icon="📝" label="Pending Reviews" value="5" />
        <StatCard icon="📋" label="Active Cases" value="24" />
        <StatCard icon="📊" label="Class Avg" value="76%" />
      </div>

      <div className="grid md:grid-cols-2 gap-6 mt-8">
        <div className="card p-6">
          <h3 className="font-semibold mb-4">Recent Submissions</h3>
          <ul className="space-y-3 text-sm">
            <li className="flex justify-between">
              <span>Aarav Patel — Case 6</span>
              <span className="text-brand-success">92%</span>
            </li>
            <li className="flex justify-between">
              <span>Sneha Iyer — Case 6</span>
              <span className="text-brand-success">88%</span>
            </li>
            <li className="flex justify-between">
              <span>Rohan Shah — Case 5</span>
              <span className="text-brand-warning">68%</span>
            </li>
          </ul>
        </div>

        <div className="card p-6">
          <h3 className="font-semibold mb-4">Class-wide Weak Areas</h3>
          <ul className="space-y-3 text-sm">
            <li className="flex justify-between">
              <span>ST segment interpretation</span>
              <span className="text-brand-danger">42% avg</span>
            </li>
            <li className="flex justify-between">
              <span>QTc calculation</span>
              <span className="text-brand-warning">58% avg</span>
            </li>
            <li className="flex justify-between">
              <span>P wave identification</span>
              <span className="text-brand-warning">61% avg</span>
            </li>
          </ul>
        </div>
      </div>
    </Layout>
  );
}