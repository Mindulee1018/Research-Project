export default function KPI({ title, value, hint, accent = "#2563eb" }) {
  return (
    <div className="card shadow-sm h-100 border-0">
      <div
        style={{
          height: 5,
          background: `linear-gradient(90deg, ${accent}, rgba(0,0,0,0))`,
          borderTopLeftRadius: 12,
          borderTopRightRadius: 12,
        }}
      />
      <div className="card-body py-3">
        <div className="d-flex align-items-start justify-content-between">
          <div>
            <div className="text-muted small fw-semibold">{title}</div>
            <div className="fs-3 fw-bold lh-1 mt-1">{value ?? "-"}</div>
            {hint ? (
              <div className="text-muted small mt-1" style={{ lineHeight: 1.2 }}>
                {hint}
              </div>
            ) : null}
          </div>

          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 12,
              background: "rgba(37,99,235,0.10)",
              border: "1px solid rgba(0,0,0,0.06)",
            }}
          />
        </div>
      </div>
    </div>
  );
}