"use client";

import Link from "next/link";
import { startTransition, useCallback, useEffect, useMemo, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:5000";
const MODERATOR_ID = process.env.NEXT_PUBLIC_MODERATOR_ID || "ui_moderator";
const CONSOLE_STATE_KEY = "sl_moderator_console_state_v2";
const DECISIONS_REFRESH_MS = 15000;
const TOAST_DURATION_MS = 4500;
const DEFAULT_TIMEOUT_MS = 30000;
const MODERATE_TIMEOUT_MS = 30000;
const EXPLAIN_TIMEOUT_MS = 180000;
const SHAP_TIMEOUT_MS = 0;
const COUNTERFACTUAL_TIMEOUT_MS = 60000;
const ATTENTION_TIMEOUT_MS = 30000;

const SAMPLE_QUEUE = [
  "මේක 100% ඇත්තක්, හැමෝටම දැන්ම share කරන්න.",
  "එයාව මිනිස්සුන්ගේ ඉස්සරහා අපහාස කරන්න ඕන.",
  "මෙම පණිවිඩය තහවුරු කරගෙන පසුව බෙදාගන්න.",
];

function normalizeApiResponse(payload) {
  if (payload && typeof payload === "object" && "success" in payload) {
    if (!payload.success) {
      throw new Error(payload.message || "API failure");
    }
    return payload.data;
  }
  return payload;
}

function isAbortError(error) {
  return error?.name === "AbortError" || error?.message === "Request cancelled";
}

async function fetchJson(path, { method = "GET", body, signal, timeoutMs = DEFAULT_TIMEOUT_MS, retries = 0 } = {}) {
  const controller = new AbortController();
  const requestId = typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `req_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  const onAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", onAbort, { once: true });
  }
  const timeout = timeoutMs > 0
    ? window.setTimeout(() => controller.abort(), timeoutMs)
    : null;

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        "X-Request-ID": requestId,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const text = await res.text();
    const parsed = text ? JSON.parse(text) : {};
    if (!res.ok) {
      const error = new Error(parsed?.message || `HTTP ${res.status}`);
      error.status = res.status;
      throw error;
    }
    return normalizeApiResponse(parsed);
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error(signal?.aborted ? "Request cancelled" : `Request timed out after ${timeoutMs} ms`);
    }
    const shouldRetry = retries > 0 && (!("status" in error) || error.status >= 500);
    if (shouldRetry) {
      return fetchJson(path, { method, body, signal, timeoutMs, retries: retries - 1 });
    }
    throw error;
  } finally {
    if (timeout !== null) {
      window.clearTimeout(timeout);
    }
    if (signal) signal.removeEventListener("abort", onAbort);
  }
}

async function postJson(path, body, options = {}) {
  return fetchJson(path, { ...options, method: "POST", body });
}

async function getJson(path, options = {}) {
  return fetchJson(path, { ...options, method: "GET" });
}

async function deleteJson(path, options = {}) {
  return fetchJson(path, { ...options, method: "DELETE" });
}

function createQueueItem(text, source = "manual_input") {
  const id = typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `item_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  return { id, text, source, status: "queued", analyzedAt: null };
}

function labelColor(label) {
  if (label === "HATE") return "danger";
  if (label === "DISINFO") return "warning";
  if (label === "NORMAL") return "success";
  return "secondary";
}

function previewText(text, maxLen = 72) {
  const value = (text || "").trim().replace(/\s+/g, " ");
  if (!value) return "-";
  return value.length > maxLen ? `${value.slice(0, maxLen).trim()}...` : value;
}

function formatDuration(ms) {
  if (typeof ms !== "number" || Number.isNaN(ms) || ms < 0) return "-";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(ms >= 10000 ? 0 : 1)} s`;
}

function getEvidenceProgress(analysis) {
  if (!analysis) return { ready: 0, total: 4, loading: false, hasError: false, complete: false };
  const keys = ["explain", "shap", "counterfactual", "attention"];
  const loading = keys.some((key) => {
    const config = ANALYSIS_TAB_CONFIG[key];
    return Boolean(analysis[config.loadingKey]);
  });
  const hasError = keys.some((key) => {
    const config = ANALYSIS_TAB_CONFIG[key];
    return Boolean(analysis[config.errorKey]);
  });
  const ready = keys.filter((key) => {
    const config = ANALYSIS_TAB_CONFIG[key];
    return Boolean(analysis[key] || analysis[config.errorKey]);
  }).length;
  return { ready, total: keys.length, loading, hasError, complete: ready === keys.length && !loading };
}

function buildInteractiveExplainPayload(text, includeLlmFeedback = false) {
  return { text, include_llm_feedback: includeLlmFeedback };
}

const ANALYSIS_TAB_CONFIG = {
  explain: {
    key: "explain",
    path: "/api/explain",
    errorKey: "explainError",
    loadingKey: "explainLoading",
    optional: false,
    timeoutMs: EXPLAIN_TIMEOUT_MS,
    retries: 1,
  },
  shap: {
    key: "shap",
    path: "/api/explain/shap",
    errorKey: "shapError",
    loadingKey: "shapLoading",
    optional: true,
    timeoutMs: SHAP_TIMEOUT_MS,
    retries: 1,
  },
  counterfactual: {
    key: "counterfactual",
    path: "/api/explain/counterfactual",
    errorKey: "counterfactualError",
    loadingKey: "counterfactualLoading",
    optional: false,
    timeoutMs: COUNTERFACTUAL_TIMEOUT_MS,
    retries: 1,
  },
  attention: {
    key: "attention",
    path: "/api/explain/attention",
    errorKey: "attentionError",
    loadingKey: "attentionLoading",
    optional: true,
    timeoutMs: ATTENTION_TIMEOUT_MS,
    retries: 1,
  },
};

async function optionalPostJson(path, body, options = {}) {
  try {
    return { data: await postJson(path, body, options), error: null };
  } catch (error) {
    return { data: null, error: error?.message || "Unavailable" };
  }
}

export default function ModeratorConsole({ view = "all" }) {
  const [singleText, setSingleText] = useState("");
  const [batchText, setBatchText] = useState(SAMPLE_QUEUE.join("\n"));
  const [queue, setQueue] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [analysisById, setAnalysisById] = useState({});
  const analysisByIdRef = useRef({});
  const analysisControllersRef = useRef({});
  const whatIfControllerRef = useRef(null);
  const decisionsControllerRef = useRef(null);
  const [whatIfText, setWhatIfText] = useState("");
  const [whatIfAnalysis, setWhatIfAnalysis] = useState(null);
  const [activeAnalysisTab, setActiveAnalysisTab] = useState("explain");
  const [queueFilter, setQueueFilter] = useState("all");
  const [queueSearch, setQueueSearch] = useState("");
  const [toast, setToast] = useState(null);
  const [health, setHealth] = useState(null);
  const [decisionNotes, setDecisionNotes] = useState("");
  const [finalDecisionLabel, setFinalDecisionLabel] = useState("NORMAL");
  const [includeLlmFeedback, setIncludeLlmFeedback] = useState(true);
  const [decisions, setDecisions] = useState([]);
  const [expandedDecisionId, setExpandedDecisionId] = useState(null);
  const [decisionsLoading, setDecisionsLoading] = useState(false);
  const selected = useMemo(
    () => queue.find((item) => item.id === selectedId) || null,
    [queue, selectedId]
  );
  const selectedAnalysis = selected ? analysisById[selected.id] : null;
  const analyzedItems = useMemo(
    () => queue.filter((item) => item.status === "done"),
    [queue]
  );
  const queueSummary = useMemo(() => {
    const counts = { queued: 0, running: 0, done: 0, error: 0 };
    for (const item of queue) {
      counts[item.status] = (counts[item.status] || 0) + 1;
    }
    return counts;
  }, [queue]);
  const labelSummary = useMemo(() => {
    const counts = { HATE: 0, DISINFO: 0, NORMAL: 0 };
    for (const item of analyzedItems) {
      const prediction = analysisById[item.id]?.moderate?.prediction;
      if (prediction && prediction in counts) {
        counts[prediction] += 1;
      }
    }
    return counts;
  }, [analyzedItems, analysisById]);
  const showInput = view !== "decisions";
  const showBatchInput = view === "all" || view === "batch";
  const showQueue = view !== "decisions";
  const showAnalysis = view !== "decisions";
  const showDecisions = view === "all" || view === "decisions";
  const showOverviewHero = view === "all";
  const visibleQueue = useMemo(() => {
    const search = queueSearch.trim().toLowerCase();
    return queue.filter((item) => {
      if (queueFilter !== "all" && item.status !== queueFilter) return false;
      if (!search) return true;
      const prediction = analysisById[item.id]?.moderate?.prediction || "";
      return (
        item.text.toLowerCase().includes(search) ||
        item.source.toLowerCase().includes(search) ||
        prediction.toLowerCase().includes(search)
      );
    });
  }, [queue, queueFilter, queueSearch, analysisById]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(CONSOLE_STATE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed.queue)) setQueue(parsed.queue);
      if (typeof parsed.selectedId === "string" || parsed.selectedId === null) setSelectedId(parsed.selectedId);
      if (parsed.analysisById && typeof parsed.analysisById === "object") setAnalysisById(parsed.analysisById);
      if (typeof parsed.batchText === "string") setBatchText(parsed.batchText);
    } catch {
      // ignore corrupted local state
    }
  }, []);

  useEffect(() => {
    analysisByIdRef.current = analysisById;
  }, [analysisById]);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        CONSOLE_STATE_KEY,
        JSON.stringify({ queue, selectedId, analysisById, batchText })
      );
    } catch {
      // ignore storage quota/availability issues
    }
  }, [queue, selectedId, analysisById, batchText]);

  useEffect(() => {
    let isMounted = true;
    getJson("/health", { timeoutMs: 8000 })
      .then((data) => {
        if (isMounted) setHealth(data);
      })
      .catch(() => {
        if (isMounted) setHealth(null);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!showDecisions) return undefined;
    let isMounted = true;

    const load = async () => {
      decisionsControllerRef.current?.abort();
      decisionsControllerRef.current = new AbortController();
      if (isMounted) setDecisionsLoading(true);
      try {
        const data = await getJson("/api/moderation/decision?limit=10", {
          signal: decisionsControllerRef.current.signal,
          timeoutMs: 8000,
        });
        if (isMounted) {
          setDecisions(data.items || []);
        }
      } catch (error) {
        if (isAbortError(error)) return;
        if (isMounted) {
          setDecisions([]);
        }
      } finally {
        if (isMounted) {
          setDecisionsLoading(false);
        }
      }
    };

    load();
    const timer = window.setInterval(load, DECISIONS_REFRESH_MS);
    return () => {
      isMounted = false;
      decisionsControllerRef.current?.abort();
      window.clearInterval(timer);
    };
  }, [showDecisions]);

  useEffect(() => {
    if (!selected) {
      whatIfControllerRef.current?.abort();
      setWhatIfText("");
      setWhatIfAnalysis(null);
      return;
    }
    setWhatIfText(selected.text || "");
    setWhatIfAnalysis(null);
    setActiveAnalysisTab("explain");
  }, [selectedId, selected]);

  useEffect(() => {
    const prediction = selectedAnalysis?.moderate?.prediction;
    if (prediction === "HATE" || prediction === "DISINFO" || prediction === "NORMAL") {
      setFinalDecisionLabel(prediction);
    } else {
      setFinalDecisionLabel("NORMAL");
    }
  }, [selectedAnalysis]);

  useEffect(() => {
    if (!toast?.message) return undefined;
    const timer = window.setTimeout(() => setToast(null), TOAST_DURATION_MS);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => () => {
    whatIfControllerRef.current?.abort();
    decisionsControllerRef.current?.abort();
    Object.values(analysisControllersRef.current).forEach((entry) => {
      Object.values(entry || {}).forEach((controller) => controller?.abort());
    });
  }, []);

  const showToast = (message, tone = "info") => {
    setToast({ message, tone });
  };

  const getAnalysisController = (itemId, tabKey) => {
    if (!analysisControllersRef.current[itemId]) {
      analysisControllersRef.current[itemId] = {};
    }
    analysisControllersRef.current[itemId][tabKey]?.abort();
    const controller = new AbortController();
    analysisControllersRef.current[itemId][tabKey] = controller;
    return controller;
  };

  const clearAnalysisController = (itemId, tabKey, controller) => {
    if (analysisControllersRef.current[itemId]?.[tabKey] === controller) {
      delete analysisControllersRef.current[itemId][tabKey];
      if (!Object.keys(analysisControllersRef.current[itemId]).length) {
        delete analysisControllersRef.current[itemId];
      }
    }
  };

  const abortAnalysisRequests = (itemId) => {
    const entry = analysisControllersRef.current[itemId];
    if (!entry) return;
    Object.values(entry).forEach((controller) => controller?.abort());
    delete analysisControllersRef.current[itemId];
  };

  const loadAnalysisTab = useCallback(async (itemId, text, tabKey, { force = false } = {}) => {
    const config = ANALYSIS_TAB_CONFIG[tabKey];
    if (!config) return;
    const current = analysisByIdRef.current[itemId];
    if (!current || current[config.loadingKey]) {
      return;
    }
    if (!force && (current[config.key] || current[config.errorKey])) {
      return;
    }
    const controller = getAnalysisController(itemId, tabKey);
    const requestBody = tabKey === "explain" || tabKey === "counterfactual"
      ? buildInteractiveExplainPayload(text, false)
      : (config.body ? config.body(text) : { text });

    setAnalysisById((prev) => ({
      ...prev,
      [itemId]: {
        ...prev[itemId],
        [config.errorKey]: null,
        [config.loadingKey]: true,
      },
    }));

    const startedAt = performance.now();
    try {
      const result = config.optional
        ? await optionalPostJson(config.path, requestBody, {
            signal: controller.signal,
            timeoutMs: config.timeoutMs,
            retries: config.retries,
          })
        : {
            data: await postJson(
              config.path,
              requestBody,
              {
                signal: controller.signal,
                timeoutMs: config.timeoutMs,
                retries: config.retries,
              }
            ),
            error: null,
          };
      setAnalysisById((prev) => ({
        ...prev,
        [itemId]: {
          ...prev[itemId],
          [config.key]: result.data,
          [config.errorKey]: result.error,
          [config.loadingKey]: false,
          [`${config.key}DurationMs`]: performance.now() - startedAt,
        },
      }));
    } catch (error) {
      if (isAbortError(error)) {
        setAnalysisById((prev) => ({
          ...prev,
          [itemId]: {
            ...prev[itemId],
            [config.loadingKey]: false,
          },
        }));
        return;
      }
      setAnalysisById((prev) => ({
        ...prev,
        [itemId]: {
          ...prev[itemId],
          [config.errorKey]: error?.message || "Unavailable",
          [config.loadingKey]: false,
          [`${config.key}DurationMs`]: performance.now() - startedAt,
        },
      }));
    } finally {
      clearAnalysisController(itemId, tabKey, controller);
    }
  }, []);

  const loadExplainLlmFeedback = useCallback(async (itemId, text, { force = false } = {}) => {
    if (!includeLlmFeedback || !health?.llm_feedback_enabled) return;
    const current = analysisByIdRef.current[itemId];
    if (!current?.explain || current.llmFeedbackLoading) return;
    if (!["HATE", "DISINFO"].includes(current.explain?.prediction || "")) return;
    if (!force && (current.llmFeedbackFetched || current.llmFeedbackError)) return;

    const controller = getAnalysisController(itemId, "explainLlm");
    setAnalysisById((prev) => ({
      ...prev,
      [itemId]: {
        ...prev[itemId],
        llmFeedbackLoading: true,
        llmFeedbackError: null,
        llmFeedbackFetched: false,
      },
    }));

    const startedAt = performance.now();
    try {
      const explainWithLlm = await postJson(
        "/api/explain/llm-feedback",
        buildInteractiveExplainPayload(text, true),
        {
          signal: controller.signal,
          timeoutMs: 60000,
          retries: 1,
        }
      );

      setAnalysisById((prev) => ({
        ...prev,
        [itemId]: {
          ...prev[itemId],
          explain: prev[itemId]?.explain
            ? {
                ...prev[itemId].explain,
                llm_feedback: explainWithLlm.llm_feedback,
                suggestions: prev[itemId].explain?.suggestions?.length
                  ? prev[itemId].explain.suggestions
                  : (explainWithLlm.suggestions || []),
              }
            : explainWithLlm,
          llmFeedbackLoading: false,
          llmFeedbackError: null,
          llmFeedbackFetched: true,
          llmFeedbackDurationMs: performance.now() - startedAt,
        },
      }));
    } catch (error) {
      if (isAbortError(error)) {
        setAnalysisById((prev) => ({
          ...prev,
          [itemId]: {
            ...prev[itemId],
            llmFeedbackLoading: false,
            llmFeedbackFetched: false,
          },
        }));
        return;
      }

      setAnalysisById((prev) => ({
        ...prev,
        [itemId]: {
          ...prev[itemId],
          llmFeedbackLoading: false,
          llmFeedbackError: error?.message || "Unavailable",
          llmFeedbackFetched: false,
          llmFeedbackDurationMs: performance.now() - startedAt,
        },
      }));
    } finally {
      clearAnalysisController(itemId, "explainLlm", controller);
    }
  }, [health?.llm_feedback_enabled, includeLlmFeedback]);

  useEffect(() => {
    if (!selected || !selectedAnalysis?.moderate || selectedAnalysis.loading) return;
    const config = ANALYSIS_TAB_CONFIG[activeAnalysisTab];
    if (!config) return;
    loadAnalysisTab(selected.id, selected.text, activeAnalysisTab);
  }, [activeAnalysisTab, selected, selectedAnalysis, loadAnalysisTab]);

  useEffect(() => {
    if (!selected || !selectedAnalysis?.explain) return;
    void loadExplainLlmFeedback(selected.id, selected.text);
  }, [includeLlmFeedback, loadExplainLlmFeedback, selected, selectedAnalysis?.explain]);

  const enqueueSingle = () => {
    const text = singleText.trim();
    if (!text) return;
    const item = createQueueItem(text);
    setQueue((prev) => [item, ...prev]);
    setSingleText("");
    setSelectedId(item.id);
  };

  const enqueueBatch = () => {
    const rows = batchText
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    if (!rows.length) return;
    const items = rows.map((line) => createQueueItem(line));
    startTransition(() => {
      setQueue((prev) => [...items, ...prev]);
      setSelectedId(items[0].id);
    });
  };

  const runItem = async (item) => {
    abortAnalysisRequests(item.id);
    const startedAt = performance.now();
    setQueue((prev) => prev.map((p) => (p.id === item.id ? { ...p, status: "running" } : p)));
    setAnalysisById((prev) => ({
      ...prev,
      [item.id]: { loading: true, error: null, startedAtMs: startedAt },
    }));

    try {
      const moderate = await postJson("/api/moderate", { text: item.text }, {
        timeoutMs: MODERATE_TIMEOUT_MS,
        retries: 1,
      });
      const moderateDurationMs = performance.now() - startedAt;

      setAnalysisById((prev) => ({
        ...prev,
        [item.id]: {
          loading: false,
          moderate,
          moderateDurationMs,
          totalDurationMs: moderateDurationMs,
          explain: null,
          counterfactual: null,
          shap: null,
          attention: null,
          explainError: null,
          llmFeedbackError: null,
          counterfactualError: null,
          shapError: null,
          attentionError: null,
          explainLoading: false,
          llmFeedbackLoading: false,
          llmFeedbackFetched: false,
          counterfactualLoading: false,
          shapLoading: false,
          attentionLoading: false,
        },
      }));
      setQueue((prev) =>
        prev.map((p) =>
          p.id === item.id
            ? { ...p, status: "done", analyzedAt: new Date().toISOString(), processingMs: moderateDurationMs }
            : p
        )
      );

      for (const tabKey of Object.keys(ANALYSIS_TAB_CONFIG)) {
        void loadAnalysisTab(item.id, item.text, tabKey);
      }

      showToast(`Prediction ready in ${formatDuration(moderateDurationMs)}.`, "success");
    } catch (error) {
      if (isAbortError(error)) {
        return;
      }
      setAnalysisById((prev) => ({
        ...prev,
        [item.id]: { loading: false, error: error?.message || "Unknown error" },
      }));
      setQueue((prev) => prev.map((p) => (p.id === item.id ? { ...p, status: "error" } : p)));
      showToast(`Analysis failed: ${error?.message || "unknown"}`, "error");
    }
  };

  const runBatch = async () => {
    for (const item of queue.filter((x) => x.status === "queued")) {
      // Intentionally sequential to keep backend load stable and preserve visible progress.
      await runItem(item);
    }
  };

  const removeQueueItem = (itemId) => {
    abortAnalysisRequests(itemId);
    setQueue((prev) => prev.filter((item) => item.id !== itemId));
    setAnalysisById((prev) => {
      const next = { ...prev };
      delete next[itemId];
      return next;
    });
    if (selectedId === itemId) {
      setSelectedId(null);
      setWhatIfAnalysis(null);
      setWhatIfText("");
    }
    showToast("Queue item removed.", "info");
  };

  const clearCompletedItems = () => {
    const removableIds = new Set(queue.filter((item) => item.status === "done" || item.status === "error").map((item) => item.id));
    if (!removableIds.size) return;
    removableIds.forEach((id) => abortAnalysisRequests(id));
    setQueue((prev) => prev.filter((item) => !removableIds.has(item.id)));
    setAnalysisById((prev) => {
      const next = { ...prev };
      for (const id of removableIds) delete next[id];
      return next;
    });
    if (selectedId && removableIds.has(selectedId)) {
      setSelectedId(null);
      setWhatIfAnalysis(null);
      setWhatIfText("");
    }
    showToast("Completed queue items cleared.", "info");
  };

  const runWhatIf = async (seedText) => {
    const text = (seedText ?? whatIfText).trim();
    if (!text) return;
    const startedAt = performance.now();
    whatIfControllerRef.current?.abort();
    const controller = new AbortController();
    whatIfControllerRef.current = controller;
    setWhatIfAnalysis({ loading: true, error: null });
    try {
      const [moderate, counterfactual, shapResult] = await Promise.all([
        postJson("/api/moderate", { text }, {
          signal: controller.signal,
          timeoutMs: MODERATE_TIMEOUT_MS,
          retries: 1,
        }),
        postJson("/api/explain/counterfactual", buildInteractiveExplainPayload(text, includeLlmFeedback), {
          signal: controller.signal,
          timeoutMs: COUNTERFACTUAL_TIMEOUT_MS,
          retries: 1,
        }),
        optionalPostJson("/api/explain/shap", { text }, {
          signal: controller.signal,
          timeoutMs: SHAP_TIMEOUT_MS,
          retries: 1,
        }),
      ]);
      setWhatIfAnalysis({
        loading: false,
        error: null,
        text,
        moderate,
        counterfactual,
        shap: shapResult.data,
        shapError: shapResult.error,
        totalDurationMs: performance.now() - startedAt,
      });
      setWhatIfText(text);
      showToast(`What-if analysis updated in ${formatDuration(performance.now() - startedAt)}.`, "success");
    } catch (error) {
      if (isAbortError(error)) {
        return;
      }
      setWhatIfAnalysis({
        loading: false,
        error: error?.message || "Unknown error",
        text,
      });
      showToast(`What-if analysis failed: ${error?.message || "unknown"}`, "error");
    } finally {
      if (whatIfControllerRef.current === controller) {
        whatIfControllerRef.current = null;
      }
    }
  };

  const submitDecision = async (moderatorAction) => {
    if (!selected || !selectedAnalysis?.moderate) return;
    const modelPrediction = selectedAnalysis.moderate.prediction || "NORMAL";
    await postJson("/api/moderation/decision", {
      item_id: selected.id,
      source: selected.source,
      text: selected.text,
      model_prediction: modelPrediction,
      moderator_action: moderatorAction,
      final_label: finalDecisionLabel,
      moderator_id: MODERATOR_ID,
      notes: decisionNotes.trim(),
    });
    await refreshDecisions();
    setDecisionNotes("");
    showToast("Decision logged.", "success");
  };

  const refreshDecisions = async () => {
    decisionsControllerRef.current?.abort();
    decisionsControllerRef.current = new AbortController();
    setDecisionsLoading(true);
    try {
      const data = await getJson("/api/moderation/decision?limit=10", {
        signal: decisionsControllerRef.current.signal,
        timeoutMs: 8000,
      });
      setDecisions(data.items || []);
    } catch (error) {
      if (!isAbortError(error)) {
        throw error;
      }
    } finally {
      setDecisionsLoading(false);
      decisionsControllerRef.current = null;
    }
  };

  const exportDecisions = async (format) => {
    const data = await getJson(`/api/moderation/decision/export?format=${format}`);
    const content = data.content || "";
    const blob = new Blob([content], { type: format === "csv" ? "text/csv" : "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `moderator_decisions.${format}`;
    anchor.click();
    URL.revokeObjectURL(url);
    showToast(`Exported ${format.toUpperCase()}.`, "success");
  };

  const clearDecisions = async () => {
    const result = await deleteJson("/api/moderation/decision");
    setDecisions([]);
    setExpandedDecisionId(null);
    showToast(`Cleared ${result?.removed || 0} decision records.`, "info");
  };

  return (
    <div className="mod-shell">
      <header className="mod-header mod-hero">
        <div className="mod-hero-copy">
          <div className="mod-kicker">Sri Lankan Social Moderation Workspace</div>
          <h1>Sinhala Moderator Console</h1>
          <p>
            Review harmful-content predictions, inspect explanation evidence, test safer phrasing,
            and log moderator decisions in one workflow.
          </p>
          <div className="d-flex gap-2 flex-wrap mt-3">
            <span className={`badge text-bg-${health?.status === "ok" ? "success" : "secondary"}`}>
              Service: {health?.status || "unknown"}
            </span>
            <span className={`badge text-bg-${health?.shap_enabled ? "success" : "warning"}`}>
              SHAP: {health?.shap_enabled ? "enabled" : "unavailable"}
            </span>
            <span className={`badge text-bg-${health?.attention_enabled ? "success" : "warning"}`}>
              Attention: {health?.attention_enabled ? (health?.attention_backend || "enabled") : "unavailable"}
            </span>
            <span className={`badge text-bg-${health?.llm_feedback_enabled ? "success" : "secondary"}`}>
              LLM: {health?.llm_feedback_enabled ? "enabled" : "disabled"}
            </span>
          </div>
        </div>
        <div className="mod-hero-panel">
          <div className="mod-hero-stat">
            <span className="mod-hero-stat-value">{queue.length}</span>
            <span className="mod-hero-stat-label">Queued items</span>
          </div>
          <div className="mod-hero-stat">
            <span className="mod-hero-stat-value">{analyzedItems.length}</span>
            <span className="mod-hero-stat-label">Analyzed</span>
          </div>
          <div className="mod-hero-stat">
            <span className="mod-hero-stat-value">{decisions.length}</span>
            <span className="mod-hero-stat-label">Recent decisions</span>
          </div>
        </div>
        <nav className="mod-nav mt-3">
          <Link href="/" className={view === "all" ? "active" : ""}>Overview</Link>
          <Link href="/moderate" className={view === "moderate" ? "active" : ""}>Moderate</Link>
          <Link href="/batch" className={view === "batch" ? "active" : ""}>Batch</Link>
          <Link href="/decisions" className={view === "decisions" ? "active" : ""}>Decisions</Link>
        </nav>
      </header>

      {showOverviewHero && (
        <section className="mod-overview-grid">
          <article className="mod-summary-card">
            <div className="mod-summary-title">Queue Status</div>
            <div className="mod-summary-stats">
              <div><strong>{queueSummary.queued}</strong><span>Queued</span></div>
              <div><strong>{queueSummary.running}</strong><span>Running</span></div>
              <div><strong>{queueSummary.done}</strong><span>Done</span></div>
              <div><strong>{queueSummary.error}</strong><span>Error</span></div>
            </div>
          </article>
          <article className="mod-summary-card">
            <div className="mod-summary-title">Predicted Labels</div>
            <div className="mod-summary-stats">
              <div><strong>{labelSummary.NORMAL}</strong><span>Normal</span></div>
              <div><strong>{labelSummary.HATE}</strong><span>Hate</span></div>
              <div><strong>{labelSummary.DISINFO}</strong><span>Disinfo</span></div>
            </div>
          </article>
          <article className="mod-summary-card mod-summary-note">
            <div className="mod-summary-title">Workflow</div>
            <p>
              Start with single moderation or batch review, inspect explanation tabs, then use
              the what-if editor to compare safer wording before logging a final moderator action.
            </p>
          </article>
        </section>
      )}

      <main className="mod-grid">
        {showInput && (
        <section className="mod-card">
          <h2>Input</h2>
          <label className="mod-label">Single comment</label>
          <textarea
            className="form-control mod-textarea"
            rows={3}
            value={singleText}
            onChange={(e) => setSingleText(e.target.value)}
            placeholder="Type a Sinhala comment..."
          />
          <button className="btn btn-primary mt-2" onClick={enqueueSingle}>Add to Queue</button>

          {showBatchInput && (
          <>
          <hr />

          <label className="mod-label">Batch comments (one per line)</label>
          <textarea
            className="form-control mod-textarea"
            rows={8}
            value={batchText}
            onChange={(e) => setBatchText(e.target.value)}
          />
          <div className="d-flex gap-2 mt-2">
            <button className="btn btn-outline-primary" onClick={enqueueBatch}>Queue Batch</button>
          </div>
          </>
          )}
        </section>
        )}

        {showQueue && (
        <section className="mod-card">
          <div className="mod-section-head">
            <div>
              <h2>Review Queue</h2>
              <div className="mod-section-meta">{visibleQueue.length} visible / {queue.length} total</div>
            </div>
            <div className="mod-queue-actions">
              <div className="mod-filter-pills">
                {["all", "queued", "running", "done", "error"].map((status) => (
                  <button
                    key={status}
                    type="button"
                    className={`mod-filter-pill ${queueFilter === status ? "active" : ""}`}
                    onClick={() => setQueueFilter(status)}
                  >
                    {status}
                  </button>
                ))}
              </div>
              <div className="d-flex gap-2 flex-wrap justify-content-end">
                <button className="btn btn-sm btn-success" onClick={runBatch}>Run Queued Batch</button>
                <button className="btn btn-sm btn-outline-danger" onClick={clearCompletedItems}>
                  Clear Done/Error
                </button>
              </div>
            </div>
          </div>
          <input
            className="form-control mod-queue-search"
            value={queueSearch}
            onChange={(e) => setQueueSearch(e.target.value)}
            placeholder="Search queue text, source, or prediction..."
          />
          <div className="mod-queue">
            {visibleQueue.map((item) => {
              const itemAnalysis = analysisById[item.id];
              const prediction = itemAnalysis?.moderate?.prediction;
              const confidence = itemAnalysis?.moderate?.confidence;
              const evidenceProgress = getEvidenceProgress(itemAnalysis);
              return (
                <div
                  key={item.id}
                  className={`mod-queue-item ${selectedId === item.id ? "active" : ""}`}
                  onClick={() => setSelectedId(item.id)}
                >
                  <div className="d-flex justify-content-between align-items-start gap-2">
                    <div className="mod-queue-meta">
                      <span className="small text-muted">{item.source}</span>
                      {item.analyzedAt && (
                        <span className="mod-queue-time">
                          {new Date(item.analyzedAt).toLocaleTimeString()}
                        </span>
                      )}
                    </div>
                    <div className="d-flex gap-2 align-items-center">
                      <span className={`badge text-bg-${labelColor(prediction)}`}>{prediction || item.status}</span>
                      <button
                        className="btn btn-sm btn-outline-dark"
                        onClick={(e) => {
                          e.stopPropagation();
                          runItem(item);
                        }}
                      >
                        Analyze
                      </button>
                      <button
                        className="btn btn-sm btn-outline-danger"
                        onClick={(e) => {
                          e.stopPropagation();
                          removeQueueItem(item.id);
                        }}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                  <div className="mt-2 mod-item-text">{item.text}</div>
                  <div className="mod-queue-footer">
                    <span className="mod-queue-id">
                      {item.status === "running"
                        ? "Processing..."
                        : item.processingMs
                          ? formatDuration(item.processingMs)
                          : item.id.slice(0, 8)}
                    </span>
                    <div className="d-flex gap-2 flex-wrap justify-content-end">
                      {typeof confidence === "number" && (
                        <span className="mod-queue-conf">Conf {(confidence * 100).toFixed(1)}%</span>
                      )}
                      {itemAnalysis?.moderateDurationMs && (
                        <span className="mod-queue-conf">Took {formatDuration(itemAnalysis.moderateDurationMs)}</span>
                      )}
                      {prediction && (
                        <span
                          className={`mod-queue-progress ${
                            evidenceProgress.complete
                              ? "is-complete"
                              : evidenceProgress.hasError
                                ? "is-warning"
                                : evidenceProgress.loading
                                  ? "is-loading"
                                  : ""
                          }`}
                        >
                          {evidenceProgress.complete
                            ? `Evidence ${evidenceProgress.ready}/${evidenceProgress.total} ready`
                            : evidenceProgress.hasError
                              ? `Evidence ${evidenceProgress.ready}/${evidenceProgress.total} with warning`
                              : evidenceProgress.loading
                                ? `Evidence ${evidenceProgress.ready}/${evidenceProgress.total} loading`
                                : `Evidence ${evidenceProgress.ready}/${evidenceProgress.total}`}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
            {!visibleQueue.length && (
              <div className="mod-empty-state">
                <strong>No queue items visible</strong>
                <span>Adjust filters, update the search, or add new comments to continue moderation.</span>
              </div>
            )}
          </div>
        </section>
        )}

        {showAnalysis && (
        <section className="mod-card mod-analysis-card">
          <div className="mod-section-head">
            <div>
              <h2>Analysis</h2>
              <div className="mod-section-meta">
                {selected ? `Selected from ${selected.source}` : "Select a queue item to inspect"}
              </div>
            </div>
            {selectedAnalysis?.moderate && (
              <div className="d-flex flex-column align-items-end gap-2">
                <div className="mod-analysis-badges">
                  <span className={`badge text-bg-${labelColor(selectedAnalysis.moderate.prediction)}`}>
                    {selectedAnalysis.moderate.prediction}
                  </span>
                  <span className="badge text-bg-light text-dark">
                    {(selectedAnalysis.moderate.confidence * 100).toFixed(2)}%
                  </span>
                  <span className="badge text-bg-light text-dark">
                    {formatDuration(selectedAnalysis.moderateDurationMs)}
                  </span>
                </div>
                <label className="form-check form-switch mb-0">
                  <input
                    className="form-check-input"
                    type="checkbox"
                    checked={includeLlmFeedback}
                    onChange={(e) => setIncludeLlmFeedback(e.target.checked)}
                    disabled={!health?.llm_feedback_enabled}
                  />
                  <span className="form-check-label small">
                    Enable AI feedback
                  </span>
                </label>
              </div>
            )}
          </div>
          {selected && (
            <div className="mod-section-meta">
              {health?.llm_feedback_enabled
                ? "AI feedback is enabled by default. Turn it off if you need a faster review flow."
                : "AI feedback is unavailable in the current backend configuration."}
            </div>
          )}
          {!selected && (
            <div className="mod-empty-state">
              <strong>No item selected</strong>
              <span>Choose a queued or analyzed comment to inspect prediction, evidence, and moderator actions.</span>
            </div>
          )}
          {selected && selectedAnalysis?.loading && (
            <div className="mod-loader-block">
              <div className="mod-loader-line mod-loader-line-lg" />
              <div className="mod-loader-line" />
              <div className="mod-loader-line mod-loader-line-sm" />
              <div className="mod-loader-grid">
                <div className="mod-loader-card" />
                <div className="mod-loader-card" />
              </div>
            </div>
          )}
          {selected && selectedAnalysis?.error && (
            <div className="alert alert-danger py-2">{selectedAnalysis.error}</div>
          )}
          {selected && selectedAnalysis?.moderate && (
            <>
              <div className="mod-analysis-text mb-3">
                <div className="mod-section-meta mb-1">Comment text</div>
                <div>{selected.text}</div>
              </div>

              <div className="mod-tabs">
                <div className="mod-tablist" role="tablist" aria-label="Analysis evidence tabs">
                  {[
                    ["explain", "Explanation"],
                    ["shap", "SHAP"],
                    ["counterfactual", "What-if"],
                    ["attention", "Attention"],
                  ].map(([key, label]) => {
                    const loadingKey = ANALYSIS_TAB_CONFIG[key]?.loadingKey;
                    const isLoading = loadingKey ? selectedAnalysis?.[loadingKey] : false;
                    return (
                      <button
                        key={key}
                        type="button"
                        role="tab"
                        className={`mod-tab ${activeAnalysisTab === key ? "active" : ""} ${isLoading ? "is-loading" : ""}`}
                        aria-selected={activeAnalysisTab === key}
                        onClick={() => setActiveAnalysisTab(key)}
                      >
                        <span>{label}</span>
                        {isLoading && <span className="mod-tab-spinner" aria-hidden="true" />}
                      </button>
                    );
                  })}
                </div>

                <div className="mod-tabpanel" role="tabpanel">
                  {activeAnalysisTab === "explain" && (
                    <>
                      <div className="mod-panel-status" aria-live="polite">
                        <div className="mod-panel-meta">
                          {selectedAnalysis.explainDurationMs
                            ? `Loaded in ${formatDuration(selectedAnalysis.explainDurationMs)}`
                            : "\u00A0"}
                        </div>
                      </div>
                      {selectedAnalysis.explainLoading && (
                        <div className="mod-panel-loading">
                          <div className="mod-loader-line mod-loader-line-lg" />
                          <div className="mod-loader-line" />
                          <div className="mod-loader-line mod-loader-line-sm" />
                        </div>
                      )}
                      {selectedAnalysis.explainError && (
                        <div className="alert alert-danger py-2 mb-2 d-flex justify-content-between align-items-center gap-2 flex-wrap">
                          <span>Explanation unavailable: {selectedAnalysis.explainError}</span>
                          <button
                            className="btn btn-sm btn-outline-danger"
                            onClick={() => loadAnalysisTab(selected.id, selected.text, "explain", { force: true })}
                          >
                            Retry
                          </button>
                        </div>
                      )}
                      <p className="mb-1">{selectedAnalysis.explain?.xai_sentence}</p>
                      <div
                        className="mod-highlight"
                        dangerouslySetInnerHTML={{ __html: selectedAnalysis.explain?.highlight_html || "" }}
                      />
                      {includeLlmFeedback && selectedAnalysis.llmFeedbackLoading && (
                        <div className="alert alert-secondary py-2 mt-2 mb-2">
                          Loading AI feedback...
                        </div>
                      )}
                      {includeLlmFeedback && selectedAnalysis.llmFeedbackError && (
                        <div className="alert alert-warning py-2 mt-2 mb-2 d-flex justify-content-between align-items-center gap-2 flex-wrap">
                          <span>AI feedback unavailable: {selectedAnalysis.llmFeedbackError}</span>
                          <button
                            className="btn btn-sm btn-outline-dark"
                            onClick={() => loadExplainLlmFeedback(selected.id, selected.text, { force: true })}
                          >
                            Retry
                          </button>
                        </div>
                      )}
                      {!!selectedAnalysis.explain?.llm_feedback?.feedback && (
                        <div className="alert alert-info py-2 mt-2 mb-2">
                          <strong>LLM Feedback:</strong> {selectedAnalysis.explain.llm_feedback.feedback}
                        </div>
                      )}
                      <ul className="mb-0">
                        {(selectedAnalysis.explain?.llm_feedback?.suggestions || []).map((s, idx) => (
                          <li key={`llm-${idx}`}>{s}</li>
                        ))}
                        {(selectedAnalysis.explain?.suggestions || []).map((s, idx) => (
                          <li key={`ret-${idx}`}>{s.suggestion}</li>
                        ))}
                      </ul>
                    </>
                  )}

                  {activeAnalysisTab === "shap" && (
                    <>
                      {!!selectedAnalysis.shapDurationMs && (
                        <div className="mod-panel-meta">Loaded in {formatDuration(selectedAnalysis.shapDurationMs)}</div>
                      )}
                      {selectedAnalysis.shapLoading && (
                        <div className="mod-token-wrap">
                          <span className="mod-token mod-token-loading" />
                          <span className="mod-token mod-token-loading" />
                          <span className="mod-token mod-token-loading" />
                          <span className="mod-token mod-token-loading" />
                        </div>
                      )}
                      {selectedAnalysis.shapError && (
                        <div className="alert alert-warning py-2 mb-2 d-flex justify-content-between align-items-center gap-2 flex-wrap">
                          <span>SHAP unavailable: {selectedAnalysis.shapError}</span>
                          <button
                            className="btn btn-sm btn-outline-dark"
                            onClick={() => loadAnalysisTab(selected.id, selected.text, "shap", { force: true })}
                          >
                            Retry
                          </button>
                        </div>
                      )}
                      <div className="mod-token-wrap">
                        {(selectedAnalysis.shap?.top_contributors || []).map((token, idx) => (
                          <span key={idx} className={`mod-token ${token.direction}`}>
                            {token.token} ({token.contribution.toFixed(3)})
                          </span>
                        ))}
                      </div>
                    </>
                  )}

                  {activeAnalysisTab === "counterfactual" && (
                    <>
                      {!!selectedAnalysis.counterfactualDurationMs && (
                        <div className="mod-panel-meta">Loaded in {formatDuration(selectedAnalysis.counterfactualDurationMs)}</div>
                      )}
                      {selectedAnalysis.counterfactualLoading && (
                        <div className="mod-loader-block">
                          <div className="mod-loader-line mod-loader-line-lg" />
                          <div className="mod-loader-line" />
                          <div className="mod-loader-card" />
                          <div className="mod-loader-card" />
                        </div>
                      )}
                      {selectedAnalysis.counterfactualError && (
                        <div className="alert alert-danger py-2 mb-2 d-flex justify-content-between align-items-center gap-2 flex-wrap">
                          <span>Counterfactual analysis unavailable: {selectedAnalysis.counterfactualError}</span>
                          <button
                            className="btn btn-sm btn-outline-danger"
                            onClick={() => loadAnalysisTab(selected.id, selected.text, "counterfactual", { force: true })}
                          >
                            Retry
                          </button>
                        </div>
                      )}
                      <div className="mod-whatif">
                        <label className="mod-label">Edit comment and re-check outcome</label>
                        <textarea
                          className="form-control mod-textarea"
                          rows={4}
                          value={whatIfText}
                          onChange={(e) => setWhatIfText(e.target.value)}
                          placeholder="Adjust wording to compare how the prediction changes..."
                        />
                        <div className="d-flex gap-2 mt-2 flex-wrap">
                          <button
                            className="btn btn-sm btn-primary"
                            onClick={() => runWhatIf()}
                            disabled={!whatIfText.trim() || whatIfAnalysis?.loading}
                          >
                            {whatIfAnalysis?.loading ? "Checking..." : "Run What-if"}
                          </button>
                          <button
                            className="btn btn-sm btn-outline-dark"
                            onClick={() => {
                              setWhatIfText(selected.text || "");
                              setWhatIfAnalysis(null);
                            }}
                          >
                            Reset to Original
                          </button>
                        </div>
                        {whatIfAnalysis?.error && (
                          <div className="alert alert-danger py-2 mt-2 mb-0">{whatIfAnalysis.error}</div>
                        )}
                        {whatIfAnalysis?.shapError && (
                          <div className="alert alert-warning py-2 mt-2 mb-0">
                            Edited-text SHAP unavailable: {whatIfAnalysis.shapError}
                          </div>
                        )}
                        {whatIfAnalysis?.moderate && (
                          <div className="mod-whatif-compare mt-3">
                            <div className="mod-whatif-card">
                              <div className="small text-muted mb-1">Original</div>
                              <div className="d-flex align-items-center gap-2 flex-wrap">
                                <span className={`badge text-bg-${labelColor(selectedAnalysis.moderate.prediction)}`}>
                                  {selectedAnalysis.moderate.prediction}
                                </span>
                                <span className="small">
                                  {(selectedAnalysis.moderate.confidence * 100).toFixed(2)}%
                                </span>
                              </div>
                            </div>
                            <div className="mod-whatif-card">
                              <div className="small text-muted mb-1">Edited</div>
                              <div className="d-flex align-items-center gap-2 flex-wrap">
                                <span className={`badge text-bg-${labelColor(whatIfAnalysis.moderate.prediction)}`}>
                                  {whatIfAnalysis.moderate.prediction}
                                </span>
                                <span className="small">
                                  {(whatIfAnalysis.moderate.confidence * 100).toFixed(2)}%
                                </span>
                              </div>
                            </div>
                          </div>
                        )}
                        {!!whatIfAnalysis?.totalDurationMs && (
                          <div className="mod-panel-meta mt-2">
                            What-if processed in {formatDuration(whatIfAnalysis.totalDurationMs)}
                          </div>
                        )}
                        {!!whatIfAnalysis?.counterfactual?.counterfactuals?.length && (
                          <>
                            <div className="small text-muted mt-3 mb-2">Candidate rewrites from the current text</div>
                            <ul className="mb-0 mod-cf-list">
                              {whatIfAnalysis.counterfactual.counterfactuals.map((c, idx) => (
                                <li key={`whatif-${idx}`} className="mod-cf-item">
                                  <div>
                                    <strong>{c.prediction}</strong> | {(c.confidence * 100).toFixed(2)}% | {c.text}
                                  </div>
                                  <button
                                    className="btn btn-sm btn-outline-primary"
                                    onClick={() => {
                                      setWhatIfText(c.text);
                                      runWhatIf(c.text);
                                    }}
                                  >
                                    Use This
                                  </button>
                                </li>
                              ))}
                            </ul>
                          </>
                        )}
                        {!!whatIfAnalysis?.shap?.top_contributors?.length && (
                          <>
                            <div className="small text-muted mt-3 mb-2">Edited-text token evidence</div>
                            <div className="mod-token-wrap">
                              {whatIfAnalysis.shap.top_contributors.map((token, idx) => (
                                <span key={`whatif-token-${idx}`} className={`mod-token ${token.direction}`}>
                                  {token.token} ({token.contribution.toFixed(3)})
                                </span>
                              ))}
                            </div>
                          </>
                        )}
                      </div>
                      <hr />
                      <ul className="mb-0 mod-cf-list">
                        {(selectedAnalysis.counterfactual?.counterfactuals || []).map((c, idx) => (
                          <li key={idx} className="mod-cf-item">
                            <div>
                              <strong>{c.prediction}</strong> | {(c.confidence * 100).toFixed(2)}% | {c.text}
                            </div>
                            <button
                              className="btn btn-sm btn-outline-primary"
                              onClick={() => {
                                setWhatIfText(c.text);
                                runWhatIf(c.text);
                              }}
                            >
                              Try This
                            </button>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}

                  {activeAnalysisTab === "attention" && (
                    <>
                      {!!selectedAnalysis.attentionDurationMs && (
                        <div className="mod-panel-meta">Loaded in {formatDuration(selectedAnalysis.attentionDurationMs)}</div>
                      )}
                      {selectedAnalysis.attentionLoading && (
                        <div className="mod-token-wrap">
                          <span className="mod-token mod-token-loading" />
                          <span className="mod-token mod-token-loading" />
                          <span className="mod-token mod-token-loading" />
                        </div>
                      )}
                      {selectedAnalysis.attentionError && (
                        <div className="alert alert-warning py-2 mb-2 d-flex justify-content-between align-items-center gap-2 flex-wrap">
                          <span>Attention unavailable: {selectedAnalysis.attentionError}</span>
                          <button
                            className="btn btn-sm btn-outline-dark"
                            onClick={() => loadAnalysisTab(selected.id, selected.text, "attention", { force: true })}
                          >
                            Retry
                          </button>
                        </div>
                      )}
                      <div className="mod-token-wrap">
                        {(selectedAnalysis.attention?.top_attention_tokens || []).map((token, idx) => (
                          <span key={idx} className="mod-token neutral">
                            {token.token} ({token.weight.toFixed(3)})
                          </span>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              </div>

              <hr />
              <h3 className="mod-subtitle">Moderator Decision</h3>
              <label className="mod-label">Final label</label>
              <select
                className="form-select"
                value={finalDecisionLabel}
                onChange={(e) => setFinalDecisionLabel(e.target.value)}
              >
                <option value="NORMAL">NORMAL</option>
                <option value="HATE">HATE</option>
                <option value="DISINFO">DISINFO</option>
              </select>
              <textarea
                className="form-control mod-textarea mt-2"
                rows={2}
                placeholder="Notes..."
                value={decisionNotes}
                onChange={(e) => setDecisionNotes(e.target.value)}
              />
              <div className="d-flex flex-wrap gap-2 mt-2">
                <button className="btn btn-success btn-sm" onClick={() => submitDecision("approve")}>Approve</button>
                <button className="btn btn-danger btn-sm" onClick={() => submitDecision("reject")}>Reject</button>
                <button className="btn btn-warning btn-sm" onClick={() => submitDecision("escalate")}>Escalate</button>
                <button className="btn btn-primary btn-sm" onClick={() => submitDecision("rewrite")}>Request Rewrite</button>
              </div>
            </>
          )}
        </section>
        )}
      </main>

      {showDecisions && (
      <section className="mod-card mt-3">
        <div className="d-flex justify-content-between align-items-center flex-wrap gap-2">
          <div>
            <h2 className="mb-0">Recent Decisions</h2>
            <div className="mod-section-meta">Audit trail for moderator overrides, approvals, and rewrite requests.</div>
          </div>
          <div className="d-flex gap-2">
            <button className="btn btn-outline-dark btn-sm" onClick={refreshDecisions}>Refresh</button>
            <button className="btn btn-outline-dark btn-sm" onClick={() => exportDecisions("json")}>Export JSON</button>
            <button className="btn btn-outline-dark btn-sm" onClick={() => exportDecisions("csv")}>Export CSV</button>
            <button className="btn btn-outline-danger btn-sm" onClick={clearDecisions}>Clear</button>
          </div>
        </div>
        <div className="mod-decision-summary mt-3">
          <div className="mod-decision-stat">
            <strong>{decisions.length}</strong>
            <span>Loaded records</span>
          </div>
          <div className="mod-decision-stat">
            <strong>{decisions.filter((d) => d.moderator_action === "rewrite").length}</strong>
            <span>Rewrite actions</span>
          </div>
          <div className="mod-decision-stat">
            <strong>{decisions.filter((d) => d.moderator_action === "escalate").length}</strong>
            <span>Escalations</span>
          </div>
          <div className="mod-decision-stat">
            <strong>{decisions.filter((d) => d.final_label === "HATE" || d.final_label === "DISINFO").length}</strong>
            <span>Harmful finals</span>
          </div>
        </div>
        <div className="table-responsive mt-2">
          <table className="table table-sm align-middle mod-decision-table">
            <thead>
              <tr>
                <th>Comment</th>
                <th>Source</th>
                <th>Model</th>
                <th>Action</th>
                <th>Final Label</th>
                <th>Moderator</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {decisionsLoading && !decisions.length && (
                <>
                  <tr><td colSpan={7}><div className="mod-loader-line mod-loader-line-lg" /></td></tr>
                  <tr><td colSpan={7}><div className="mod-loader-line" /></td></tr>
                  <tr><td colSpan={7}><div className="mod-loader-line mod-loader-line-sm" /></td></tr>
                </>
              )}
              {decisions.map((d) => (
                d.decision_id ? (
                  [
                    <tr
                      key={d.decision_id}
                      className={`mod-decision-row ${expandedDecisionId === d.decision_id ? "active" : ""}`}
                      onClick={() =>
                        setExpandedDecisionId((prev) => (prev === d.decision_id ? null : d.decision_id))
                      }
                    >
                      <td className="small">{previewText(d.text)}</td>
                      <td className="small text-muted">{d.source}</td>
                      <td><span className={`badge text-bg-${labelColor(d.model_prediction)}`}>{d.model_prediction}</span></td>
                      <td>{d.moderator_action}</td>
                      <td><span className={`badge text-bg-${labelColor(d.final_label)}`}>{d.final_label}</span></td>
                      <td>{d.moderator_id}</td>
                      <td className="small">{previewText(d.notes, 48)}</td>
                    </tr>,
                    expandedDecisionId === d.decision_id ? (
                      <tr key={`${d.decision_id}-detail`} className="mod-decision-detail-row">
                        <td colSpan={7}>
                          <div className="mod-decision-detail">
                            <div>
                              <div className="mod-detail-label">Full comment</div>
                              <div className="mod-detail-text">{d.text || "-"}</div>
                            </div>
                            <div className="mod-detail-grid">
                              <div>
                                <div className="mod-detail-label">Decision ID</div>
                                <div className="mod-detail-text">{d.decision_id}</div>
                              </div>
                              <div>
                                <div className="mod-detail-label">Decided At</div>
                                <div className="mod-detail-text">{d.decided_at || "-"}</div>
                              </div>
                              <div>
                                <div className="mod-detail-label">Logged At</div>
                                <div className="mod-detail-text">{d.logged_at || "-"}</div>
                              </div>
                              <div>
                                <div className="mod-detail-label">Notes</div>
                                <div className="mod-detail-text">{d.notes || "-"}</div>
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    ) : null,
                  ]
                ) : null
              ))}
              {!decisions.length && !decisionsLoading && (
                <tr><td colSpan={7} className="text-muted small">No decisions loaded.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
      )}

      {!!toast?.message && (
        <div className={`mod-toast mod-toast-${toast.tone || "info"}`} role="status">
          <div className="mod-toast-accent" aria-hidden="true" />
          <div className="mod-toast-body">
            <div className="mod-toast-top">
              <strong className="mod-toast-title">
                {toast.tone === "error" ? "Action Failed" : toast.tone === "success" ? "Updated" : "Notice"}
              </strong>
              <button className="mod-toast-close" onClick={() => setToast(null)} aria-label="Close notification">
                ×
              </button>
            </div>
            <span>{toast.message}</span>
          </div>
        </div>
      )}
    </div>
  );
}
