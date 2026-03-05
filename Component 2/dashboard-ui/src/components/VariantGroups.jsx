import { useMemo } from "react";

export default function VariantGroups({
  variantGroups,
  vgQuery,
  setVgQuery,
  vgOnlyUnchecked,
  setVgOnlyUnchecked,
  checkedGroups,
  toggleGroupChecked,
  vgPage,
  setVgPage,
}) {
  const VG_PAGE_SIZE = 12;

  const filteredVariantGroups = useMemo(() => {
    const q = vgQuery.trim().toLowerCase();
    return (variantGroups || []).filter((g) => {
      const globalIdx = variantGroups.indexOf(g);
      const key = `${g.canonical}_${globalIdx}`;
      if (vgOnlyUnchecked && checkedGroups[key]) return false;

      if (!q) return true;

      const canonical = String(g.canonical || "").toLowerCase();
      const vars = Array.isArray(g.variants) ? g.variants : [];
      const inVariants = vars.some((v) =>
        String(v.term || "").toLowerCase().includes(q),
      );
      return canonical.includes(q) || inVariants;
    });
  }, [variantGroups, vgQuery, vgOnlyUnchecked, checkedGroups]);

  const vgTotalPages = Math.max(
    1,
    Math.ceil(filteredVariantGroups.length / VG_PAGE_SIZE),
  );

  const pagedVariantGroups = useMemo(() => {
    const start = (vgPage - 1) * VG_PAGE_SIZE;
    return filteredVariantGroups.slice(start, start + VG_PAGE_SIZE);
  }, [filteredVariantGroups, vgPage]);

  return (
    <div className="card shadow-sm">
      <div className="card-body">
        <div className="d-flex align-items-center justify-content-between flex-wrap gap-2">
          <div className="fw-bold">Variant Groups (All Merges)</div>
          <div className="text-muted small">
            Showing {filteredVariantGroups.length} groups
          </div>
        </div>

        <div className="row g-2 mt-2 align-items-center">
          <div className="col-12 col-md-6">
            <input
              className="form-control form-control-sm"
              value={vgQuery}
              onChange={(e) => {
                setVgQuery(e.target.value);
                setVgPage(1);
              }}
              placeholder="Search canonical or variant term…"
            />
          </div>

          <div className="col-12 col-md-3">
            <div className="form-check">
              <input
                className="form-check-input"
                type="checkbox"
                checked={vgOnlyUnchecked}
                onChange={(e) => {
                  setVgOnlyUnchecked(e.target.checked);
                  setVgPage(1);
                }}
                id="onlyUnchecked"
              />
              <label className="form-check-label small" htmlFor="onlyUnchecked">
                Show only unchecked
              </label>
            </div>
          </div>

          <div className="col-12 col-md-3 d-flex justify-content-md-end gap-2">
            <button
              className="btn btn-outline-secondary btn-sm"
              disabled={vgPage <= 1}
              onClick={() => setVgPage((p) => Math.max(1, p - 1))}
            >
              Prev
            </button>
            <div className="small text-muted align-self-center">
              Page {vgPage} / {vgTotalPages}
            </div>
            <button
              className="btn btn-outline-secondary btn-sm"
              disabled={vgPage >= vgTotalPages}
              onClick={() => setVgPage((p) => Math.min(vgTotalPages, p + 1))}
            >
              Next
            </button>
          </div>
        </div>

        {!pagedVariantGroups.length ? (
          <div className="text-muted small mt-3">No groups match your search.</div>
        ) : (
          <div className="list-group mt-3" style={{ maxHeight: 420, overflowY: "auto" }}>
            {pagedVariantGroups.map((g) => {
              const globalIdx = variantGroups.indexOf(g);
              const key = `${g.canonical}_${globalIdx}`;
              const checked = !!checkedGroups[key];
              const vars = Array.isArray(g.variants) ? g.variants : [];

              return (
                <div
                  key={key}
                  className="list-group-item"
                  style={{
                    borderLeft: checked ? "6px solid #16a34a" : "6px solid #e5e7eb",
                    background: checked ? "rgba(22,163,74,0.05)" : "white",
                  }}
                >
                  <div className="d-flex align-items-start gap-2">
                    <input
                      type="checkbox"
                      className="form-check-input mt-1"
                      checked={checked}
                      onChange={() => toggleGroupChecked(key)}
                    />

                    <div className="w-100">
                      <div className="fw-semibold">
                        {g.canonical}
                        <span className="badge text-bg-light border ms-2">
                          variants: {g.variant_count}
                        </span>
                        <span className="badge text-bg-light border ms-2">
                          total: {g.total_count}
                        </span>
                        {checked && (
                          <span className="badge text-bg-success ms-2">
                            Reviewed
                          </span>
                        )}
                      </div>

                      <div className="small text-muted mt-2">
                        {vars.length
                          ? vars.map((v) => `${v.term} (${v.count})`).join(", ")
                          : "No variants"}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}