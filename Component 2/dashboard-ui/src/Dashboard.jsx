import { useEffect, useMemo, useState } from "react";

import KPI from "./components/KPI.jsx";
import DriftChart from "./components/DriftChart.jsx";
import LexiconTop from "./components/LexiconTop.jsx";
import StatusCard from "./components/StatusCard.jsx";
import VariantGroups from "./components/VariantGroups.jsx";
import ManualMerge from "./components/ManualMerge.jsx";
import LatestTrigger from "./components/LatestTrigger.jsx";
import TriggerTimeline from "./components/TriggerTimeline.jsx";

import { addManualAlias, deleteManualAlias, loadDashboardData } from "./lib/api.js";

export default function Dashboard() {
  const [metrics, setMetrics] = useState(null);
  const [drift, setDrift] = useState([]);
  const [triggers, setTriggers] = useState([]);
  const [lexTop, setLexTop] = useState([]);
  const [variantGroups, setVariantGroups] = useState([]);
  const [manualMap, setManualMap] = useState({});
  const [err, setErr] = useState("");

  const [refreshTick, setRefreshTick] = useState(0);

  // lexicon search
  const [query, setQuery] = useState("");

  // manual merge inputs
  const [manualFrom, setManualFrom] = useState("");
  const [manualTo, setManualTo] = useState("");

  // trigger timeline controls
  const [tlQuery, setTlQuery] = useState("");
  const [tlLimit, setTlLimit] = useState(10);
  const [tlExpanded, setTlExpanded] = useState({});
  const [tlOnlyFlagged, setTlOnlyFlagged] = useState(false);

  // variant groups controls + pagination
  const [vgQuery, setVgQuery] = useState("");
  const [vgOnlyUnchecked, setVgOnlyUnchecked] = useState(false);
  const [vgPage, setVgPage] = useState(1);

  const [checkedGroups, setCheckedGroups] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("checkedVariantGroups") || "{}");
    } catch {
      return {};
    }
  });

  const thresholds = useMemo(
    () => ({
      jsd: 0.2,
      concept: 0.1,
      newTerm: 0.4,
    }),
    [],
  );

  function toggleGroupChecked(key) {
    setCheckedGroups((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      localStorage.setItem("checkedVariantGroups", JSON.stringify(next));
      return next;
    });
  }

  function toggleTlExpanded(batchNo) {
    setTlExpanded((prev) => ({ ...prev, [batchNo]: !prev[batchNo] }));
  }

  useEffect(() => {
    async function load() {
      try {
        setErr("");
        const data = await loadDashboardData();
        setMetrics(data.metrics);
        setDrift(data.drift);
        setTriggers(data.triggers);
        setLexTop(data.lexTop);
        setVariantGroups(data.variantGroups);
        setManualMap(data.manualMap);
        setVgPage(1);
      } catch (e) {
        setErr(String(e?.message || e));
      }
    }
    load();
  }, [refreshTick]);

  const triggerBatches = useMemo(
    () => new Set((triggers || []).map((x) => String(x.batch_no))),
    [triggers],
  );

  const driftChartData = useMemo(() => {
    return (drift || []).map((r) => ({
      batch_no: String(r.batch_no),
      jsd: r.jsd === "" || r.jsd == null ? null : Number(r.jsd),
      concept:
        r.concept_mean_abs_delta === "" || r.concept_mean_abs_delta == null
          ? null
          : Number(r.concept_mean_abs_delta),
      new_term_rate:
        r.new_term_rate === "" || r.new_term_rate == null
          ? null
          : Number(r.new_term_rate),
      trigger: triggerBatches.has(String(r.batch_no)) ? 1 : 0,
    }));
  }, [drift, triggerBatches]);

  const latestTrigger = triggers.length ? triggers[triggers.length - 1] : null;
  const latestRow = drift?.length ? drift[drift.length - 1] : null;

  const action = useMemo(() => {
    if (!latestRow) return { level: "info", title: "Waiting for data...", steps: [] };

    const jsd = latestRow.jsd === "" ? null : Number(latestRow.jsd);
    const concept =
      latestRow.concept_mean_abs_delta === "" ? null : Number(latestRow.concept_mean_abs_delta);
    const newTerm =
      latestRow.new_term_rate === "" ? null : Number(latestRow.new_term_rate);

    const trig = String(latestRow.trigger) === "True" || latestRow.trigger === true;

    const driftHigh =
      (jsd != null && jsd >= thresholds.jsd) ||
      (concept != null && concept >= thresholds.concept) ||
      (newTerm != null && newTerm >= thresholds.newTerm);

    if (!trig && !driftHigh) {
      return {
        level: "good",
        title: "Stable (no action needed)",
        steps: ["Continue monitoring batches.", "No review required right now."],
      };
    }

    return {
      level: "warn",
      title: trig ? "Trigger detected — Review recommended" : "Drift elevated — Review recommended",
      steps: [
        "Collect ~100 labeled samples from this batch (votes / human review).",
        "Confirm new terms and add Manual Merge aliases if needed.",
        "When the static model is ready: run incremental update for this batch.",
      ],
    };
  }, [latestRow, thresholds]);

  const statusColor =
    action.level === "good" ? "#16a34a" : action.level === "warn" ? "#f59e0b" : "#2563eb";

  return (
    <div className="container my-3">
      {/* Header */}
      <div className="d-flex align-items-center gap-3">
        <div>
          <h3 className="mb-0">Component 2 Dashboard — Drift & New Terms</h3>
          <div className="text-muted small">
            Drift monitoring + lexicon review (model updates can be connected later)
          </div>
        </div>

        <button
          className="btn btn-outline-primary btn-sm ms-auto"
          onClick={() => setRefreshTick((x) => x + 1)}
          title="Reload data from backend"
        >
          Refresh
        </button>
      </div>

      {/* Error */}
      {err && (
        <div className="alert alert-danger mt-3 mb-0 py-2">
          <div className="small" style={{ whiteSpace: "pre-wrap" }}>
            {err}
          </div>
        </div>
      )}

      {/* KPI row */}
      <div className="row g-3 mt-2">
        <div className="col-12 col-md-6 col-lg-3">
          <KPI title="Latest Batch" value={metrics?.latest_batch} hint="Most recent processed batch" />
        </div>
        <div className="col-12 col-md-6 col-lg-3">
          <KPI title="Batches Seen" value={metrics?.batches_seen} hint="Total batches in history" accent="#16a34a" />
        </div>
        <div className="col-12 col-md-6 col-lg-3">
          <KPI title="Trigger Events" value={metrics?.trigger_count} hint="Batches requiring review" accent="#ef4444" />
        </div>
        <div className="col-12 col-md-6 col-lg-3">
          <KPI title="Lexicon Size" value={metrics?.lexicon_size} hint="Unique terms tracked" accent="#f59e0b" />
        </div>
      </div>

      {/* Drift chart */}
      <div className="row g-3 mt-0">
        <div className="col-12">
          <DriftChart data={driftChartData} thresholds={thresholds} />
        </div>
      </div>

      {/* Lexicon + Status */}
      <div className="row g-3 mt-0">
        <div className="col-12 col-lg-7">
          <LexiconTop lexTop={lexTop} query={query} setQuery={setQuery} />
        </div>
        <div className="col-12 col-lg-5">
          <StatusCard actionTitle={action.title} actionSteps={action.steps} statusColor={statusColor} />
        </div>
      </div>

      {/* Variant groups */}
      <div className="row g-3 mt-0">
        <div className="col-12">
          <VariantGroups
            variantGroups={variantGroups}
            vgQuery={vgQuery}
            setVgQuery={setVgQuery}
            vgOnlyUnchecked={vgOnlyUnchecked}
            setVgOnlyUnchecked={setVgOnlyUnchecked}
            checkedGroups={checkedGroups}
            toggleGroupChecked={toggleGroupChecked}
            vgPage={vgPage}
            setVgPage={setVgPage}
          />
        </div>
      </div>

      {/* Manual merge */}
      <div className="row g-3 mt-0">
        <div className="col-12">
          <ManualMerge
            manualFrom={manualFrom}
            setManualFrom={setManualFrom}
            manualTo={manualTo}
            setManualTo={setManualTo}
            manualMap={manualMap}
            onAdd={async () => {
              await addManualAlias(manualFrom, manualTo);
              setManualFrom("");
              setManualTo("");
              setRefreshTick((x) => x + 1);
            }}
            onRemove={async (term) => {
              await deleteManualAlias(term);
              setRefreshTick((x) => x + 1);
            }}
          />
        </div>
      </div>

      {/* Latest trigger */}
      <div className="row g-3 mt-0">
        <div className="col-12">
          <LatestTrigger latestTrigger={latestTrigger} />
        </div>
      </div>

      {/* Trigger timeline */}
      <div className="row g-3 mt-0">
        <div className="col-12">
          <TriggerTimeline
            triggers={triggers}
            tlQuery={tlQuery}
            setTlQuery={setTlQuery}
            tlOnlyFlagged={tlOnlyFlagged}
            setTlOnlyFlagged={setTlOnlyFlagged}
            tlLimit={tlLimit}
            setTlLimit={setTlLimit}
            tlExpanded={tlExpanded}
            toggleTlExpanded={toggleTlExpanded}
          />
        </div>
      </div>

      <div className="text-muted small mt-3">
        Tip: Bootstrap should be imported in <code>src/main.jsx</code>.
      </div>
    </div>
  );
}