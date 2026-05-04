import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from "recharts";

const METRIC_LABELS = {
  accuracy: "Accuracy",
  precision: "Precision",
  recall: "Recall",
  f1: "F1-score",
};

function fmt(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${Number(value).toFixed(2)}%`;
}

function ImprovementBadge({ value }) {
  if (value === null || value === undefined) {
    return <span className="badge bg-secondary-subtle text-secondary">N/A</span>;
  }

  const positive = Number(value) >= 0;

  return (
    <span
      className={`badge ${
        positive
          ? "bg-success-subtle text-success border border-success-subtle"
          : "bg-danger-subtle text-danger border border-danger-subtle"
      }`}
    >
      {positive ? "+" : ""}
      {Number(value).toFixed(2)}%
    </span>
  );
}

export default function ModelEvaluationComparison({ evaluation }) {
  if (!evaluation) {
    return (
      <div className="card shadow-sm border-0">
        <div className="card-body text-muted">Loading model evaluation...</div>
      </div>
    );
  }

  if (!evaluation.available) {
    return (
      <div className="card shadow-sm border-0">
        <div className="card-body">
          <h5 className="mb-1">Adaptive Model Evaluation</h5>
          <p className="text-muted small mb-0">
            No evaluation results found. Run base and adaptive evaluation first.
          </p>
        </div>
      </div>
    );
  }

  const chartData = Object.keys(METRIC_LABELS).map((key) => ({
    metric: METRIC_LABELS[key],
    Base: evaluation.base?.[key] ?? 0,
    Adaptive: evaluation.adaptive?.[key] ?? 0,
  }));

  const baseCm = evaluation.base?.confusion_matrix;
  const adaptiveCm = evaluation.adaptive?.confusion_matrix;

  return (
    <div className="card shadow-sm border-0">
      <div className="card-body">
        <div className="d-flex flex-wrap justify-content-between align-items-start gap-2 mb-3">
          <div>
            <h5 className="mb-1">Adaptive Learning Evaluation</h5>
            <div className="text-muted small">
              Base model vs latest adaptive model · {evaluation.evaluation_type}
            </div>
          </div>

          <div className="text-end">
            <span className="badge rounded-pill bg-primary-subtle text-primary border border-primary-subtle">
              {evaluation.latest_model || "Latest adaptive model"}
            </span>
            <div className="text-muted small mt-1">
              Test rows: {evaluation.test_rows ?? "-"}
            </div>
          </div>
        </div>

        <div className="row g-3 mb-3">
          {Object.keys(METRIC_LABELS).map((key) => (
            <div className="col-12 col-md-6 col-xl-3" key={key}>
              <div className="p-3 rounded-4 border bg-light h-100">
                <div className="text-muted small fw-semibold">
                  {METRIC_LABELS[key]}
                </div>

                <div className="d-flex justify-content-between align-items-end mt-2">
                  <div>
                    <div className="small text-muted">Base</div>
                    <div className="fw-bold">{fmt(evaluation.base?.[key])}</div>
                  </div>

                  <div>
                    <div className="small text-muted">Adaptive</div>
                    <div className="fw-bold text-success">
                      {fmt(evaluation.adaptive?.[key])}
                    </div>
                  </div>

                  <div>
                    <div className="small text-muted">Gain</div>
                    <ImprovementBadge value={evaluation.improvement?.[key]} />
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* <div style={{ width: "100%", height: 320 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="metric" />
              <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
              <Tooltip formatter={(value) => `${Number(value).toFixed(2)}%`} />
              <Legend />
              <Bar dataKey="Base" radius={[6, 6, 0, 0]}>
                {chartData.map((_, index) => (
                  <Cell key={`base-${index}`} fill="#94a3b8" />
                ))}
              </Bar>
              <Bar dataKey="Adaptive" radius={[6, 6, 0, 0]}>
                {chartData.map((_, index) => (
                  <Cell key={`adaptive-${index}`} fill="#22c55e" />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div> */}

        <div className="row g-3 mt-3">
          <div className="col-12 col-lg-6">
            <ConfusionMatrix title="Base Model Confusion Matrix" matrix={baseCm} />
          </div>

          <div className="col-12 col-lg-6">
            <ConfusionMatrix
              title="Adaptive Model Confusion Matrix"
              matrix={adaptiveCm}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function ConfusionMatrix({ title, matrix }) {
  const safe = matrix || [
    [0, 0],
    [0, 0],
  ];

  return (
    <div className="border rounded-4 p-3 h-100">
      <div className="fw-semibold mb-2">{title}</div>
      <div className="text-muted small mb-2">
        Rows = actual, columns = predicted
      </div>

      <div className="table-responsive">
        <table className="table table-sm align-middle mb-0">
          <thead>
            <tr>
              <th></th>
              <th className="text-center">Pred HATE</th>
              <th className="text-center">Pred NORMAL</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th>Actual HATE</th>
              <td className="text-center fw-bold">{safe[0]?.[0] ?? 0}</td>
              <td className="text-center">{safe[0]?.[1] ?? 0}</td>
            </tr>
            <tr>
              <th>Actual NORMAL</th>
              <td className="text-center">{safe[1]?.[0] ?? 0}</td>
              <td className="text-center fw-bold">{safe[1]?.[1] ?? 0}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}