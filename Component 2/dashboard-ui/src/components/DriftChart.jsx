import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";

export default function DriftChart({ data, thresholds }) {
  return (
    <div className="card shadow-sm">
      <div className="card-body">
        <div className="d-flex align-items-center justify-content-between flex-wrap gap-2">
          <div className="fw-bold">
            Drift Trends (JSD / Concept / New-Term Rate) + Trigger Markers
          </div>
          <div className="text-muted small">
            Thresholds: JSD ≥ {thresholds.jsd}, Concept ≥ {thresholds.concept},
            NewTerm ≥ {thresholds.newTerm}
          </div>
        </div>

        <div style={{ width: "100%", height: 360 }} className="mt-2">
          <ResponsiveContainer>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="batch_no" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="jsd"
                name="JSD"
                stroke="#2563eb"
                dot={false}
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="concept"
                name="Concept Drift"
                stroke="#16a34a"
                dot={false}
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="new_term_rate"
                name="New Term Rate"
                stroke="#f59e0b"
                dot={false}
                strokeWidth={2}
              />
              <Line
                type="stepAfter"
                dataKey="trigger"
                name="Trigger"
                stroke="#ef4444"
                dot={{ r: 3 }}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="text-muted small mt-2">
          JSD = term distribution drift. Concept drift proxy = relationship
          change. Trigger = review/update candidate batch.
        </div>
      </div>
    </div>
  );
}