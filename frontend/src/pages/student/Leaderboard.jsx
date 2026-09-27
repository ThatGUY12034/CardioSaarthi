import Layout from "../../components/Layout";

const STUDENTS = [
  { rank: 1, name: "Aarav Patel", score: 92, streak: 7 },
  { rank: 2, name: "Sneha Iyer", score: 88, streak: 5 },
  { rank: 3, name: "Rohan Shah", score: 85, streak: 4 },
  { rank: 4, name: "Isha Desai", score: 80, streak: 3 },
  { rank: 5, name: "Aditya Nair", score: 72, streak: 2 },
];

export default function Leaderboard() {
  return (
    <Layout role="STUDENT">
      <h1 className="text-3xl font-bold">Leaderboard</h1>
      <p className="text-brand-muted mt-1">Top performers this week</p>

      <div className="card mt-8 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-brand-cardLight text-brand-muted text-xs uppercase">
            <tr>
              <th className="text-left px-5 py-3">Rank</th>
              <th className="text-left px-5 py-3">Student</th>
              <th className="text-left px-5 py-3">Avg Score</th>
              <th className="text-left px-5 py-3">Streak</th>
            </tr>
          </thead>
          <tbody>
            {STUDENTS.map((s) => (
              <tr key={s.rank} className="border-t border-white/5 hover:bg-white/5">
                <td className="px-5 py-4">
                  <span
                    className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${
                      s.rank === 1
                        ? "bg-yellow-500/20 text-yellow-400"
                        : s.rank === 2
                        ? "bg-gray-400/20 text-gray-300"
                        : s.rank === 3
                        ? "bg-amber-700/20 text-amber-600"
                        : "bg-brand-cardLight text-brand-muted"
                    }`}
                  >
                    {s.rank}
                  </span>
                </td>
                <td className="px-5 py-4 font-medium">{s.name}</td>
                <td className="px-5 py-4">{s.score}%</td>
                <td className="px-5 py-4">🔥 {s.streak} days</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}