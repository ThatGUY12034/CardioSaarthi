import Layout from "../../components/Layout";

const USERS = [
  { name: "Aarav Patel", role: "Student", email: "aarav@terna.edu" },
  { name: "Dr. Sharma", role: "Faculty", email: "sharma@terna.edu" },
  { name: "Neel Gosavi", role: "Admin", email: "neel@terna.edu" },
];

export default function ManageUsers() {
  return (
    <Layout role="ADMIN">
      <h1 className="text-3xl font-bold">Manage Users</h1>
      <p className="text-brand-muted mt-1">View and manage all platform users</p>

      <div className="card mt-8 overflow-x-auto">
        <table className="w-full text-sm min-w-[600px]">
          <thead className="bg-brand-cardLight text-brand-muted text-xs uppercase">
            <tr>
              <th className="text-left px-5 py-3">Name</th>
              <th className="text-left px-5 py-3">Role</th>
              <th className="text-left px-5 py-3">Email</th>
            </tr>
          </thead>
          <tbody>
            {USERS.map((u) => (
              <tr key={u.email} className="border-t border-white/5 hover:bg-white/5">
                <td className="px-5 py-4 font-medium">{u.name}</td>
                <td className="px-5 py-4">{u.role}</td>
                <td className="px-5 py-4 text-brand-muted">{u.email}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}