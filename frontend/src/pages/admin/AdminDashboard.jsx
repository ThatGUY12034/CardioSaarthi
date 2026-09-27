import Layout from "../../components/Layout";
import StatCard from "../../components/StatCard";

export default function AdminDashboard() {
  return (
    <Layout role="ADMIN">
      <h1 className="text-3xl font-bold">Admin Dashboard</h1>
      <p className="text-brand-muted mt-1">System overview & management</p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mt-8">
        <StatCard icon="👥" label="Total Users" value="184" />
        <StatCard icon="📋" label="Total Cases" value="56" />
        <StatCard icon="📝" label="Submissions" value="1,204" />
        <StatCard icon="⚠" label="System Alerts" value="2" />
      </div>
    </Layout>
  );
}