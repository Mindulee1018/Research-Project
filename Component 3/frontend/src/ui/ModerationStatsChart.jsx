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

export default function ModerationStatsChart({ posts = [] }) {
  const allComments = posts.flatMap((post) => post.comments || []);

  const stats = {
    BLOCK: 0,
    FLAG: 0,
    ALLOW: 0,
    PENDING: 0,
    ERROR: 0,
  };

  allComments.forEach((comment) => {
    if (!comment.analysis) {
      stats.PENDING += 1;
      return;
    }

    if (comment.analysis.prediction === "ERROR") {
      stats.ERROR += 1;
      return;
    }

    const action = (comment.analysis?.moderation?.action || "ALLOW").toUpperCase();

    if (stats[action] !== undefined) {
      stats[action] += 1;
    } else {
      stats.ALLOW += 1;
    }
  });

  const data = [
    { name: "BLOCK", value: stats.BLOCK, color: "#dc3545" },
    { name: "FLAG", value: stats.FLAG, color: "#f59e0b" },
    { name: "ALLOW", value: stats.ALLOW, color: "#42b72a" },
    { name: "PENDING", value: stats.PENDING, color: "#adb5bd" },
    { name: "ERROR", value: stats.ERROR, color: "#6c757d" },
  ];

  const total = data.reduce((sum, item) => sum + item.value, 0);

  return (
    <div
      style={{
        background: "white",
        borderRadius: "12px",
        padding: "20px",
        boxShadow: "0 2px 12px rgba(0,0,0,0.08)",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: "16px",
          alignItems: "center",
        }}
      >
        <h3 style={{ margin: 0 }}>Moderation Statistics</h3>
        <span>Total Comments: {total}</span>
      </div>

      <div style={{ width: "100%", height: 320 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="value">
              {data.map((entry, index) => (
                <Cell key={index} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}