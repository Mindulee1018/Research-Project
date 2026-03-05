export default function ManualMerge({
  manualFrom,
  setManualFrom,
  manualTo,
  setManualTo,
  manualMap,
  onAdd,
  onRemove,
}) {
  return (
    <div className="card shadow-sm">
      <div className="card-body">
        <div className="fw-bold mb-2">Manual Merge (Override)</div>

        <div className="row g-2">
          <div className="col-12 col-md-5">
            <input
              className="form-control form-control-sm"
              value={manualFrom}
              onChange={(e) => setManualFrom(e.target.value)}
              placeholder="From (variant) e.g., අන්තවාදීන්ට"
            />
          </div>
          <div className="col-12 col-md-5">
            <input
              className="form-control form-control-sm"
              value={manualTo}
              onChange={(e) => setManualTo(e.target.value)}
              placeholder="To (canonical) e.g., අන්තවාදී"
            />
          </div>
          <div className="col-12 col-md-2 d-grid">
            <button className="btn btn-outline-secondary btn-sm" onClick={onAdd}>
              Add
            </button>
          </div>
        </div>

        <div className="text-muted small mt-3">Current overrides:</div>

        {!Object.keys(manualMap || {}).length ? (
          <div className="text-muted small">No manual merges yet.</div>
        ) : (
          <div className="d-grid gap-2 mt-2">
            {Object.entries(manualMap).map(([k, v]) => (
              <div
                key={k}
                className="border rounded p-2 d-flex justify-content-between align-items-center gap-2"
              >
                <div className="small">
                  <span className="fw-semibold">{k}</span> → {v}
                </div>
                <button
                  className="btn btn-outline-danger btn-sm"
                  onClick={() => onRemove(k)}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}