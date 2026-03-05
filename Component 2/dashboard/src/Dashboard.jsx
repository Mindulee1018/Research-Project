// dashboard/src/Dashboard.jsx
import { useEffect, useMemo, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  BarChart,
  Bar,
} from "recharts";

const API = "/api";

function KPI({ title, value }) {
  return (
    <div className="card">
      <div className="kpiTitle">{title}</div>
      <div className="kpiValue">{value ?? "-"}</div>
    </div>
  );
}

export default function Dashboard() {
  const [metrics, setMetrics] = useState(null);
  const [drift, setDrift] = useState([]);
  const [triggers, setTriggers] = useState([]);
  const [lexTop, setLexTop] = useState([]);
  const [variantGroups, setVariantGroups] = useState([]);
  const [err, setErr] = useState("");

  const [manualFrom, setManualFrom] = useState("");
  const [manualTo, setManualTo] = useState("");
  const [manualMap, setManualMap] = useState({});

  // lexicon search
  const [query, setQuery] = useState("");

  // manual refresh (optional)
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    async function load() {
      try {
        setErr("");
        const [m, d, t, l, vg, mm] = await Promise.all([
          fetch(`${API}/metrics`).then((r) => r.json()),
          fetch(`${API}/drift_history`).then((r) => r.json()),
          fetch(`${API}/triggers`).then((r) => r.json()),
          fetch(`${API}/lexicon_top?limit=200`).then((r) => r.json()),
          fetch(`${API}/variant_groups?limit=10&min_variants=1`).then(
            (r) => r.json(),
            fetch(`${API}/manual_aliases`).then((r) => r.json()),
          ),
        ]);

        setMetrics(m);
        setDrift(d);
        setTriggers(t);
        setLexTop(l);
        setVariantGroups(vg);
        setManualMap(mm);
      } catch (e) {
        setErr(String(e));
      }
    }
    load();
  }, [refreshTick]);

  const triggerBatches = useMemo(
    () => new Set(triggers.map((x) => String(x.batch_no))),
    [triggers],
  );

  const driftChartData = useMemo(() => {
    return drift.map((r) => ({
      batch_no: String(r.batch_no),
      jsd: r.jsd === "" ? null : Number(r.jsd),
      concept:
        r.concept_mean_abs_delta === ""
          ? null
          : Number(r.concept_mean_abs_delta),
      new_term_rate: r.new_term_rate === "" ? null : Number(r.new_term_rate),
      hate_rate: r.hate_rate === "" ? null : Number(r.hate_rate),
      // mark trigger batches (0/1)
      trigger: triggerBatches.has(String(r.batch_no)) ? 1 : 0,
    }));
  }, [drift, triggerBatches]);

  const filteredLex = useMemo(() => {
    const q = query.trim();
    if (!q) return lexTop;
    return lexTop.filter((x) => String(x.term).includes(q));
  }, [query, lexTop]);

  const lexChartData = useMemo(() => {
    // show top 20 of filtered results to keep chart readable
    return filteredLex.slice(0, 20).map((x) => ({
      term: x.term,
      weight: Number(x.weight || 0),
    }));
  }, [filteredLex]);

  const latestTrigger = triggers.length ? triggers[triggers.length - 1] : null;

  return (
    <div className="container">
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h1 className="title" style={{ marginBottom: 0 }}>
          Component 2 Dashboard — Drift & New Terms
        </h1>

        <button
          onClick={() => setRefreshTick((x) => x + 1)}
          style={{
            marginLeft: "auto",
            padding: "8px 12px",
            borderRadius: 10,
            border: "1px solid #e5e7eb",
            background: "white",
            cursor: "pointer",
            boxShadow: "0 6px 18px rgba(0,0,0,0.04)",
          }}
          title="Reload data from artifacts"
        >
          Refresh
        </button>
      </div>

      {err && (
        <div className="small" style={{ color: "crimson", marginTop: 8 }}>
          {err}
        </div>
      )}

      <div className="grid grid-4" style={{ marginTop: 12, marginBottom: 12 }}>
        <KPI title="Latest Batch" value={metrics?.latest_batch} />
        <KPI title="Batches Seen" value={metrics?.batches_seen} />
        <KPI title="Trigger Events" value={metrics?.trigger_count} />
        <KPI title="Lexicon Size" value={metrics?.lexicon_size} />
      </div>

      <div
        className="grid"
        style={{ gridTemplateColumns: "1.4fr 1fr", gap: 12 }}
      >
        {/* Drift chart */}
        <div className="card">
          <div className="sectionTitle">
            Drift Trends (JSD / Concept / New-Term Rate) + Trigger Markers
          </div>
          <div style={{ width: "100%", height: 340 }}>
            <ResponsiveContainer>
              <LineChart data={driftChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="batch_no" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="jsd" dot={false} />
                <Line type="monotone" dataKey="concept" dot={false} />
                <Line type="monotone" dataKey="new_term_rate" dot={false} />
                {/* trigger marker line (0/1) */}
                <Line type="stepAfter" dataKey="trigger" dot />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="small">
            JSD=data drift (term distribution). Concept=relationship drift
            proxy. Trigger line shows incremental update points.
          </div>
        </div>

        {/* Lexicon chart + search */}
        <div className="card">
          <div className="sectionTitle">Top Terms by Weight (Lexicon)</div>

          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search Sinhala term…"
            style={{
              width: "100%",
              padding: 10,
              borderRadius: 10,
              border: "1px solid #eee",
              marginBottom: 10,
              outline: "none",
            }}
          />

          <div style={{ width: "100%", height: 340 }}>
            <ResponsiveContainer>
              <BarChart data={lexChartData}>
                <XAxis dataKey="term" hide />
                <YAxis />
                <Tooltip />
                <Bar dataKey="weight" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="small">
            Weight ≈ P(Hate|term) with smoothing. Showing top 20 matches.
          </div>
        </div>

        <div className="card" style={{ gridColumn: "1 / -1" }}>
          <div className="sectionTitle">
            Variant Groups (What got merged - Top 10)
          </div>

          {!variantGroups?.length ? (
            <div className="small">No merged groups found yet.</div>
          ) : (
            <div
              className="grid"
              style={{ gridTemplateColumns: "1fr", gap: 10 }}
            >
              {variantGroups.map((g, idx) => (
                <div className="listItem" key={idx}>
                  <div style={{ fontWeight: 800 }}>
                    Canonical: {g.canonical}
                    <span className="small">
                      {" "}
                      — variants: {g.variant_count}, total: {g.total_count}
                    </span>
                  </div>
                  <div className="small" style={{ marginTop: 6 }}>
                    {g.variants.map((v) => `${v.term}(${v.count})`).join(", ")}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card" style={{ gridColumn: "1 / -1" }}>
          <div className="sectionTitle">Manual Merge (Override)</div>

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <input
              value={manualFrom}
              onChange={(e) => setManualFrom(e.target.value)}
              placeholder="From (variant) e.g., අන්තවාදීන්ට"
              style={{
                padding: 10,
                borderRadius: 10,
                border: "1px solid #eee",
                flex: 1,
              }}
            />
            <input
              value={manualTo}
              onChange={(e) => setManualTo(e.target.value)}
              placeholder="To (canonical) e.g., අන්තවාදී"
              style={{
                padding: 10,
                borderRadius: 10,
                border: "1px solid #eee",
                flex: 1,
              }}
            />
            <button
              onClick={async () => {
                await fetch(`${API}/manual_aliases`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ from: manualFrom, to: manualTo }),
                });
                setManualFrom("");
                setManualTo("");
                setRefreshTick((x) => x + 1);
              }}
              style={{
                padding: "10px 14px",
                borderRadius: 10,
                border: "1px solid #e5e7eb",
                background: "white",
              }}
            >
              Add
            </button>
          </div>

          <div className="small" style={{ marginTop: 10 }}>
            Current overrides:
          </div>

          {!Object.keys(manualMap || {}).length ? (
            <div className="small">No manual merges yet.</div>
          ) : (
            <div
              className="grid"
              style={{ gridTemplateColumns: "1fr", gap: 8, marginTop: 8 }}
            >
              {Object.entries(manualMap).map(([k, v]) => (
                <div
                  className="listItem"
                  key={k}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 8,
                  }}
                >
                  <div>
                    <b>{k}</b> → {v}
                  </div>
                  <button
                    onClick={async () => {
                      await fetch(
                        `${API}/manual_aliases?term=${encodeURIComponent(k)}`,
                        { method: "DELETE" },
                      );
                      setRefreshTick((x) => x + 1);
                    }}
                    style={{
                      padding: "6px 10px",
                      borderRadius: 10,
                      border: "1px solid #e5e7eb",
                      background: "white",
                    }}
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Latest trigger card */}
        <div className="card" style={{ gridColumn: "1 / -1" }}>
          <div className="sectionTitle">Latest Trigger</div>

          {!latestTrigger ? (
            <div className="small">No triggers yet.</div>
          ) : (
            <div>
              <div style={{ marginBottom: 8 }}>
                <span className="pill">Batch: {latestTrigger.batch_no}</span>
                <span className="pill">
                  Vote count: {latestTrigger.vote_count}
                </span>
                <span className="pill">JSD: {latestTrigger.jsd ?? "-"}</span>
                <span className="pill">
                  new_terms_in_hate: {latestTrigger.new_terms_in_hate ?? "-"}
                </span>
              </div>

              <div className="small" style={{ marginBottom: 6 }}>
                New terms:
              </div>
              <div className="listItem" style={{ marginBottom: 10 }}>
                {(latestTrigger.new_terms || []).length
                  ? latestTrigger.new_terms.join(", ")
                  : "None"}
              </div>

              <div className="small" style={{ marginBottom: 6 }}>
                Votes:
              </div>
              <pre className="listItem" style={{ overflow: "auto", margin: 0 }}>
                {JSON.stringify(latestTrigger.votes, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* New terms over time */}
        <div className="card" style={{ gridColumn: "1 / -1" }}>
          <div className="sectionTitle">
            New Terms Over Time (by Trigger Batch)
          </div>
          <div className="grid" style={{ gridTemplateColumns: "1fr", gap: 10 }}>
            {[...triggers].reverse().map((t, idx) => (
              <div className="listItem" key={idx}>
                <div style={{ fontWeight: 700 }}>
                  {t.batch_no}{" "}
                  <span className="small">
                    — new_terms_in_hate: {t.new_terms_in_hate ?? "-"} | votes:{" "}
                    {t.vote_count}
                  </span>
                </div>
                <div className="small" style={{ marginTop: 4 }}>
                  {(t.new_terms || []).length
                    ? t.new_terms.join(", ")
                    : "No new terms"}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Trigger log */}
        <div className="card" style={{ gridColumn: "1 / -1" }}>
          <div className="sectionTitle">Trigger Log</div>
          <div className="grid" style={{ gridTemplateColumns: "1fr", gap: 10 }}>
            {[...triggers].reverse().map((t, idx) => (
              <div className="listItem" key={idx}>
                <div style={{ fontWeight: 700 }}>
                  {t.batch_no}{" "}
                  <span className="small">— votes: {t.vote_count}</span>
                </div>
                <div className="small">
                  target_drift: {String(t?.votes?.target_drift)} | data_drift:{" "}
                  {String(t?.votes?.data_drift)} | concept_proxy:{" "}
                  {String(t?.votes?.concept_proxy)} | new_term_flag:{" "}
                  {String(t?.votes?.new_term_flag)}
                </div>
                <div className="small">
                  JSD: {t.jsd ?? "-"} | new_terms_in_hate:{" "}
                  {t.new_terms_in_hate ?? "-"}
                </div>
                <div className="small" style={{ marginTop: 4 }}>
                  new terms: {(t.new_terms || []).join(", ") || "None"}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
