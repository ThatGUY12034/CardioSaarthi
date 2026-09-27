import Layout from "../../components/Layout";
import StatCard from "../../components/StatCard";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from "chart.js";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend);

export default function Progress() {
  const data = {
    labels: ["Case 1", "Case 2", "Case 3", "Case 4", "Case 5", "Case 6"],
    datasets: [
      {
        label: "Score (%)",
        data: [55, 62, 70, 68, 78, 85],
        borderColor: "#60a5fa",
        backgroundColor: "rgba(96,165,250,0.2)",
        tension: 0.4,
        fill: true,
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: { legend: { labels: { color: "#e5e7eb" } } },
    scales: {
      x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } },
      y: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } },
    },
  };

  return (
    <Layout role="STUDENT">
      <h1 className="text-3xl font-bold">Your Progress</h1>
      <p className="text-brand-muted mt-1">Track your improvement over time</p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mt-8">
        <StatCard icon="🎯" label="Cases Attempted" value="8" />
        <StatCard icon="🏅" label="Best Score" value="85%" />
        <StatCard icon="📈" label="Avg Score" value="78%" />
        <StatCard icon="🔥" label="Streak" value="3 days" />
      </div>

      <div className="card p-6 mt-8">
        <h3 className="font-semibold mb-4">Score Trend</h3>
        <Line data={data} options={options} />
      </div>
    </Layout>
  );
}