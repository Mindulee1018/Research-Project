// src/AppRoutes.jsx
import { useEffect, useMemo, useState } from "react";
import { Routes, Route } from "react-router-dom";

import AppLayout from "./layout/AppLayout.jsx";
import HomePage from "./pages/HomePage.jsx";
import DriftPage from "./pages/DriftPage.jsx";

import { loadDashboardData } from "./lib/api.js";

export default function AppRoutes() {
  const [metrics, setMetrics] = useState(null);
  const [drift, setDrift] = useState([]);
  const [triggers, setTriggers] = useState([]);
  const [variantGroups, setVariantGroups] = useState([]);
  const [manualMap, setManualMap] = useState({});
  const [err, setErr] = useState("");

  // keep “reviewed” state globally (for VariantGroups page)
  const [checkedGroups, setCheckedGroups] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("checkedVariantGroups") || "{}");
    } catch {
      return {};
    }
  });

  const [refreshTick, setRefreshTick] = useState(0);

  const thresholds = useMemo(
    () => ({ jsd: 0.2, concept: 0.1, newTerm: 0.4 }),
    [],
  );

  function toggleGroupChecked(key) {
    setCheckedGroups((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      localStorage.setItem("checkedVariantGroups", JSON.stringify(next));
      return next;
    });
  }

  useEffect(() => {
    async function load() {
      try {
        setErr("");
        const data = await loadDashboardData();

        setMetrics(data.metrics);
        setDrift(data.drift);
        setTriggers(data.triggers);

        // ✅ IMPORTANT: these were missing in your file
        setVariantGroups(data.variantGroups);
        setManualMap(data.manualMap);
      } catch (e) {
        setErr(String(e?.message || e));
      }
    }
    load();
  }, [refreshTick]);

  const refresh = () => setRefreshTick((x) => x + 1);

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

  const latestRow = drift?.length ? drift[drift.length - 1] : null;

  const action = useMemo(() => {
    if (!latestRow) return { level: "info", title: "Waiting for data...", steps: [] };

    const jsd = latestRow.jsd === "" ? null : Number(latestRow.jsd);
    const concept =
      latestRow.concept_mean_abs_delta === ""
        ? null
        : Number(latestRow.concept_mean_abs_delta);
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
      title: trig
        ? "Trigger detected — Review recommended"
        : "Drift elevated — Review recommended",
      steps: [
        "Collect ~100 labeled samples from this batch (votes / human review).",
        "Confirm new terms and add Manual Merge aliases if needed.",
        "When the static model is ready: run incremental update for this batch.",
      ],
    };
  }, [latestRow, thresholds]);

  const statusColor =
    action.level === "good"
      ? "#16a34a"
      : action.level === "warn"
        ? "#f59e0b"
        : "#2563eb";

  const latestTrigger = triggers.length ? triggers[triggers.length - 1] : null;

  return (
    <Routes>
      <Route element={<AppLayout />}>
        {/* HOME: KPI + Status + Drift chart */}
        <Route
          path="/"
          element={
            <HomePage
              metrics={metrics}
              action={action}
              statusColor={statusColor}
              thresholds={thresholds}
              driftChartData={driftChartData}
              onRefresh={refresh}
              err={err}
            />
          }
        />

        {/* DRIFT DETAILS: triggers + merges */}
        <Route
          path="/drift"
          element={
            <DriftPage
              triggers={triggers}
              latestTrigger={latestTrigger}
              variantGroups={variantGroups}
              manualMap={manualMap}
              checkedGroups={checkedGroups}
              toggleGroupChecked={toggleGroupChecked}
              onRefresh={refresh}
              err={err}
            />
          }
        />
      </Route>
    </Routes>
  );
}