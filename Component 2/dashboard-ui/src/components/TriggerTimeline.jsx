export default function TriggerTimeline({
  triggers,
  tlQuery,
  setTlQuery,
  tlOnlyFlagged,
  setTlOnlyFlagged,
  tlLimit,
  setTlLimit,
  tlExpanded,
  toggleTlExpanded,
}) {
  const triggerTimeline = (() => {
    const q = tlQuery.trim().toLowerCase();
    let rows = [...(triggers || [])].reverse(); // newest first

    if (tlOnlyFlagged) {
      rows = rows.filter((t) => {
        const v = t?.votes || {};
        return (
          v.target_drift === true ||
          v.data_drift === true ||
          v.concept_proxy === true ||
          v.new_term_flag === true
        );
      });
    }

    if (q) {
      rows = rows.filter((t) => {
        const batch = String(t.batch_no || "").toLowerCase();
        const terms = Array.isArray(t.new_terms) ? t.new_terms : [];
        const termMatch = terms.some((x) => String(x).toLowerCase().includes(q));
        return batch.includes(q) || termMatch;
      });
    }

    const lim = Number(tlLimit);
    if (!Number.isFinite(lim) || lim <= 0) return rows;
    if (lim >= 9999) return rows;
    return rows.slice(0, lim);
  })();

  return (
    <div className="card shadow-sm">
      <div className="card-body">
        <div className="d-flex align-items-center justify-content-between flex-wrap gap-2">
          <div className="fw-bold">Trigger Timeline (Drift + Votes + New Terms)</div>
          <div className="text-muted small">
            Showing {triggerTimeline.length} / {triggers.length} triggers
          </div>
        </div>

        <div className="row g-2 mt-2 align-items-center">
          <div className="col-12 col-md-6">
            <input
              className="form-control form-control-sm"
              value={tlQuery}
              onChange={(e) => setTlQuery(e.target.value)}
              placeholder="Filter by batch or term…"
            />
          </div>

          <div className="col-12 col-md-3">
            <div className="form-check">
              <input
                className="form-check-input"
                type="checkbox"
                checked={tlOnlyFlagged}
                onChange={(e) => setTlOnlyFlagged(e.target.checked)}
                id="onlyFlagged"
              />
              <label className="form-check-label small" htmlFor="onlyFlagged">
                Show only flagged
              </label>
            </div>
          </div>

          <div className="col-12 col-md-3 d-flex gap-2 justify-content-md-end">
            <label className="small text-muted align-self-center">Recent:</label>
            <select
              className="form-select form-select-sm"
              style={{ width: 160 }}
              value={tlLimit}
              onChange={(e) => setTlLimit(Number(e.target.value))}
            >
              <option value={5}>Last 5</option>
              <option value={10}>Last 10</option>
              <option value={20}>Last 20</option>
              <option value={9999}>All</option>
            </select>
          </div>
        </div>

        {!triggerTimeline.length ? (
          <div className="text-muted small mt-3">No triggers match your filter.</div>
        ) : (
          <div className="d-grid gap-2 mt-3">
            {triggerTimeline.map((t, idx) => {
              const batch = t.batch_no;
              const terms = Array.isArray(t.new_terms) ? t.new_terms : [];
              const open = !!tlExpanded[batch];

              const PREVIEW_N = 12;
              const shown = open ? terms : terms.slice(0, PREVIEW_N);
              const hiddenCount = Math.max(0, terms.length - shown.length);

              const v = t?.votes || {};
              const flagged =
                v.target_drift === true ||
                v.data_drift === true ||
                v.concept_proxy === true ||
                v.new_term_flag === true;

              return (
                <div
                  key={idx}
                  className="border rounded p-2"
                  style={{
                    borderLeft: `6px solid ${flagged ? "#ef4444" : "#e5e7eb"}`,
                    background: flagged ? "rgba(239,68,68,0.04)" : "white",
                  }}
                >
                  <div className="d-flex justify-content-between flex-wrap gap-2">
                    <div className="fw-semibold small">
                      {batch}{" "}
                      <span className="text-muted">
                        — votes: {t.vote_count} | JSD: {t.jsd ?? "-"} | new_terms_in_hate:{" "}
                        {t.new_terms_in_hate ?? "-"}
                      </span>
                    </div>

                    {terms.length > PREVIEW_N && (
                      <button
                        className="btn btn-outline-secondary btn-sm"
                        onClick={() => toggleTlExpanded(batch)}
                      >
                        {open ? "Show less" : `Show all (${terms.length})`}
                      </button>
                    )}
                  </div>

                  <div className="text-muted small mt-1">
                    target_drift: {String(v.target_drift)} | data_drift: {String(v.data_drift)} |
                    concept_proxy: {String(v.concept_proxy)} | new_term_flag: {String(v.new_term_flag)}
                  </div>

                  <div className="text-muted small mt-1">
                    <span className="fw-semibold">New terms:</span>{" "}
                    {shown.length ? shown.join(", ") : "None"}
                    {!open && hiddenCount > 0 ? ` … (+${hiddenCount} more)` : ""}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className="text-muted small mt-2">
          Tip: Use “Show only flagged” for demos + use search to find when a term appeared.
        </div>
      </div>
    </div>
  );
}