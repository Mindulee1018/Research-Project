import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

export default function ModerationStatsChart({ stats }) {
  if (!stats) {
    return (
      <div className="card shadow-sm border-0">
        <div className="card-body text-center text-muted">
          Loading moderation statistics...
        </div>
      </div>
    );
  }

  const safeStats = {
    BLOCK: stats?.BLOCK ?? 0,
    FLAG: stats?.FLAG ?? 0,
    ALLOW: stats?.ALLOW ?? 0,
    PENDING: stats?.PENDING ?? 0,
    ERROR: stats?.ERROR ?? 0,
    TOTAL: stats?.TOTAL ?? 0,
  };

  const data = [
    { name: "BLOCK", value: safeStats.BLOCK, color: "#dc3545" },
    { name: "FLAG", value: safeStats.FLAG, color: "#f59e0b" },
    { name: "ALLOW", value: safeStats.ALLOW, color: "#22c55e" },
    { name: "PENDING", value: safeStats.PENDING, color: "#94a3b8" },
    { name: "ERROR", value: safeStats.ERROR, color: "#64748b" },
  ];

  return (
    <div className="card shadow-sm border-0">
      <div className="card-body">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h5 className="mb-0">Moderation Statistics</h5>
          <span className="text-muted small">
            Total Comments: {safeStats.TOTAL}
          </span>
        </div>

        <div style={{ width: "100%", height: 320 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis allowDecimals={false} />
              <Tooltip
                formatter={(value) => [`${value} comments`, "Count"]}
              />
              <Bar dataKey="value" animationDuration={700}>
                {data.map((entry, index) => (
                  <Cell key={index} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}