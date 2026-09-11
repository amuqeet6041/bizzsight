"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";

const CARD_METRICS = [
  "Revenue",
  "Gross Profit",
  "Net Profit",
  "Orders",
  "AOV",
  "CAC",
  "Repeat Purchase Rate",
  "Return/Cancel Rate",
];

const COLORS = ["#3b82f6", "#ef4444"];

export default function Dashboard({
  displayMetrics,
  rawMetrics,
  insights,
  chartData,
  onDownloadExcel,
  onReset,
}) {
  const costBreakdown = [
    { name: "COGS", value: rawMetrics["COGS"] || 0 },
    { name: "Shipping", value: rawMetrics["Shipping Cost"] || 0 },
    { name: "Marketing", value: rawMetrics["Marketing Spend"] || 0 },
  ];

  const deliveredVsCancelled = [
    { name: "Delivered", value: 1 - (rawMetrics["Return/Cancel Rate"] || 0) },
    { name: "Returned/Cancelled", value: rawMetrics["Return/Cancel Rate"] || 0 },
  ];

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-800">Business Insights</h2>
        <div className="flex gap-2">
          <button
            onClick={onDownloadExcel}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Download for Power BI
          </button>
          <button
            onClick={onReset}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Upload another file
          </button>
        </div>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {CARD_METRICS.map((key) => (
          <div key={key} className="rounded-xl border bg-white p-4 shadow-sm">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-400">{key}</p>
            <p className="mt-1 text-xl font-semibold text-gray-800">
              {displayMetrics[key] ?? "N/A"}
            </p>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="rounded-xl border bg-white p-4 shadow-sm">
          <p className="mb-2 text-sm font-medium text-gray-600">Cost Breakdown</p>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={costBreakdown}>
              <XAxis dataKey="name" fontSize={12} />
              <YAxis fontSize={12} />
              <Tooltip />
              <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-xl border bg-white p-4 shadow-sm">
          <p className="mb-2 text-sm font-medium text-gray-600">Delivered vs Returned/Cancelled</p>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={deliveredVsCancelled}
                dataKey="value"
                nameKey="name"
                innerRadius={50}
                outerRadius={80}
              >
                {deliveredVsCancelled.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Legend />
              <Tooltip formatter={(v) => `${(v * 100).toFixed(1)}%`} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Insights */}
      <div className="rounded-xl border bg-white p-4 shadow-sm">
        <p className="mb-2 text-sm font-medium text-gray-600">Auto-Generated Insights</p>
        <ul className="space-y-1">
          {insights.map((insight, i) => (
            <li key={i} className="text-sm text-gray-700">
              {insight}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
