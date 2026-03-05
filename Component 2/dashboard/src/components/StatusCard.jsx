import Pill from "./Pill.jsx";

export default function StatusCard({ actionTitle, actionSteps, statusColor }) {
  return (
    <div className="card shadow-sm h-100">
      <div className="card-body">
        <div className="fw-bold mb-2">System Status & Actions</div>

        <div className="d-flex gap-2 flex-wrap mb-2">
          <Pill>Static Model: Pending</Pill>
          <Pill>Incremental Learning: Disabled</Pill>
          <Pill>Last Update: —</Pill>
        </div>

        <div
          className="p-3 border rounded"
          style={{ borderLeft: `6px solid ${statusColor}` }}
        >
          <div className="fw-bold mb-2">{actionTitle}</div>
          <ul className="mb-0 small">
            {actionSteps.map((s, i) => (
              <li key={i} className="mb-1">
                {s}
              </li>
            ))}
          </ul>
        </div>

        <div className="text-muted small mt-2">
          Monitoring + term review works now. Model update activates once the
          static model is connected.
        </div>
      </div>
    </div>
  );
}