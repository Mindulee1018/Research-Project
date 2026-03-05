import { useState, useEffect, useRef } from "react";

const API_URL = "http://localhost:8000";

const STAGES = [
  { id: "scraping",  label: "Scraping Comments",   icon: "⬇", desc: "Fetching comments from YouTube..." },
  { id: "cleaning",  label: "Cleaning Data",        icon: "🧹", desc: "Removing noise, emojis & URLs..." },
  { id: "labeling",  label: "Classifying Comments", icon: "🤖", desc: "Running XLM-R model predictions..." },
  { id: "saving",    label: "Saving Results",        icon: "💾", desc: "Generating CSV output..." },
];

export default function App() {
  const [url, setUrl]           = useState("");
  const [maxComments, setMax]   = useState(500);
  const [status, setStatus]     = useState("idle"); // idle | processing | done | error
  const [stage, setStage]       = useState(-1);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs]         = useState([]);
  const [results, setResults]   = useState(null);
  const [csvData, setCsvData]   = useState(null);
  const [error, setError]       = useState("");
  const logsRef                 = useRef(null);
  const pollRef                 = useRef(null);
  const jobIdRef                = useRef(null);

  const addLog = (msg) => setLogs(prev => [...prev, { msg, time: new Date().toLocaleTimeString() }]);

  useEffect(() => {
    if (logsRef.current) logsRef.current.scrollTop = logsRef.current.scrollHeight;
  }, [logs]);

  useEffect(() => () => clearInterval(pollRef.current), []);

  const isValidUrl = (u) => u.includes("youtube.com") || u.includes("youtu.be");

  const startPipeline = async () => {
    if (!isValidUrl(url)) { setError("Please enter a valid YouTube URL"); return; }
    setError("");
    setStatus("processing");
    setStage(0);
    setProgress(0);
    setLogs([]);
    setResults(null);
    setCsvData(null);

    addLog("🚀 Starting pipeline...");

    try {
      const res = await fetch(`${API_URL}/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ youtube_url: url, max_comments: maxComments }),
      });

      if (!res.ok) throw new Error("Failed to start pipeline");
      const data = await res.json();
      jobIdRef.current = data.job_id;
      addLog(`📋 Job started: ${data.job_id}`);
      pollRef.current = setInterval(pollStatus, 2000);
    } catch (e) {
      setError("Could not connect to backend. Make sure the server is running!");
      setStatus("error");
    }
  };

  const pollStatus = async () => {
    try {
      const res  = await fetch(`${API_URL}/status/${jobIdRef.current}`);
      const data = await res.json();

      if (data.log) addLog(data.log);
      if (data.stage !== undefined) setStage(data.stage);
      if (data.progress !== undefined) setProgress(data.progress);

      if (data.status === "done") {
        clearInterval(pollRef.current);
        setStage(4);
        setProgress(100);
        setResults(data.results);
        setCsvData(data.csv);
        setStatus("done");
        addLog("✅ Pipeline complete!");
      } else if (data.status === "error") {
        clearInterval(pollRef.current);
        setError(data.error || "Something went wrong");
        setStatus("error");
      }
    } catch (e) {
      // keep polling
    }
  };

  const downloadCsv = () => {
    if (!csvData) return;
    const blob = new Blob([csvData], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href  = URL.createObjectURL(blob);
    link.download = `sinhala_analysis_${Date.now()}.csv`;
    link.click();
  };

  const reset = () => {
    setUrl(""); setStatus("idle"); setStage(-1); setProgress(0);
    setLogs([]); setResults(null); setCsvData(null); setError("");
    jobIdRef.current = null;
  };

  return (
    <div style={styles.root}>
      {/* Background grid */}
      <div style={styles.grid} />

      {/* Header */}
      <header style={styles.header}>
        <div style={styles.badge}>NLP Research Tool</div>
        <h1 style={styles.title}>
          <span style={styles.titleSin}>සිංහල</span> Hate Detector
        </h1>
        <p style={styles.subtitle}>
          Scrape · Clean · Classify · Download
        </p>
      </header>

      {/* Main card */}
      <main style={styles.main}>

        {/* Input section */}
        {status === "idle" && (
          <div style={styles.inputCard}>
            <label style={styles.label}>YouTube Video URL</label>
            <div style={styles.inputRow}>
              <input
                style={{
                  ...styles.input,
                  borderColor: error ? "#ff4d4d" : url && isValidUrl(url) ? "#00e5a0" : "#2a2a3a",
                }}
                placeholder="https://www.youtube.com/watch?v=..."
                value={url}
                onChange={e => { setUrl(e.target.value); setError(""); }}
                onKeyDown={e => e.key === "Enter" && startPipeline()}
              />
            </div>
            {error && <p style={styles.errorText}>{error}</p>}

            <div style={styles.optionRow}>
              <label style={styles.optionLabel}>Max Comments</label>
              {[100, 250, 500, 1000].map(n => (
                <button
                  key={n}
                  style={{ ...styles.chip, ...(maxComments === n ? styles.chipActive : {}) }}
                  onClick={() => setMax(n)}
                >{n}</button>
              ))}
            </div>

            <button
              style={{
                ...styles.processBtn,
                opacity: url && isValidUrl(url) ? 1 : 0.5,
                cursor: url && isValidUrl(url) ? "pointer" : "not-allowed",
              }}
              onClick={startPipeline}
              disabled={!url || !isValidUrl(url)}
            >
              <span>Process Video</span>
              <span style={styles.btnArrow}>→</span>
            </button>
          </div>
        )}

        {/* Processing section */}
        {status === "processing" && (
          <div style={styles.processingCard}>

            {/* Stages */}
            <div style={styles.stages}>
              {STAGES.map((s, i) => {
                const state = i < stage ? "done" : i === stage ? "active" : "waiting";
                return (
                  <div key={s.id} style={{ ...styles.stageItem, ...(state === "active" ? styles.stageActive : state === "done" ? styles.stageDone : styles.stageWaiting) }}>
                    <div style={styles.stageIconWrap}>
                      <span style={styles.stageIcon}>{state === "done" ? "✓" : s.icon}</span>
                      {i < STAGES.length - 1 && (
                        <div style={{ ...styles.stageLine, backgroundColor: state === "done" ? "#00e5a0" : "#2a2a3a" }} />
                      )}
                    </div>
                    <div>
                      <div style={styles.stageName}>{s.label}</div>
                      {state === "active" && <div style={styles.stageDesc}>{s.desc}</div>}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Progress bar */}
            <div style={styles.progressWrap}>
              <div style={styles.progressBar}>
                <div style={{ ...styles.progressFill, width: `${progress}%` }} />
              </div>
              <span style={styles.progressText}>{progress}%</span>
            </div>

            {/* Logs */}
            <div style={styles.logsWrap} ref={logsRef}>
              {logs.map((l, i) => (
                <div key={i} style={styles.logLine}>
                  <span style={styles.logTime}>{l.time}</span>
                  <span style={styles.logMsg}>{l.msg}</span>
                </div>
              ))}
              <div style={styles.logCursor}>▋</div>
            </div>
          </div>
        )}

        {/* Results section */}
        {status === "done" && results && (
          <div style={styles.resultsCard}>
            <div style={styles.resultsHeader}>
              <span style={styles.successBadge}>✓ Analysis Complete</span>
              <h2 style={styles.resultsTitle}>Results Summary</h2>
            </div>

            {/* Stats */}
            <div style={styles.statsGrid}>
              {[
                { label: "Total Comments", value: results.total,   color: "#a0a0c0" },
                { label: "Hate Speech",    value: results.hate,    color: "#ff4d4d" },
                { label: "Disinformation", value: results.disinfo, color: "#ffaa00" },
                { label: "Normal",         value: results.normal,  color: "#00e5a0" },
              ].map(s => (
                <div key={s.label} style={{ ...styles.statCard, borderColor: s.color + "44" }}>
                  <div style={{ ...styles.statValue, color: s.color }}>{s.value}</div>
                  <div style={styles.statLabel}>{s.label}</div>
                  <div style={{ ...styles.statBar }}>
                    <div style={{
                      height: "100%",
                      width: `${(s.value / results.total * 100).toFixed(0)}%`,
                      backgroundColor: s.color,
                      borderRadius: "2px",
                      transition: "width 1s ease",
                    }} />
                  </div>
                  <div style={{ ...styles.statPct, color: s.color }}>
                    {results.total > 0 ? (s.value / results.total * 100).toFixed(1) : 0}%
                  </div>
                </div>
              ))}
            </div>

            {/* Actions */}
            <div style={styles.actionsRow}>
              <button style={styles.downloadBtn} onClick={downloadCsv}>
                <span>⬇</span> Download CSV
              </button>
              <button style={styles.resetBtn} onClick={reset}>
                ↺ Analyze Another
              </button>
            </div>
          </div>
        )}

        {/* Error section */}
        {status === "error" && (
          <div style={styles.errorCard}>
            <span style={styles.errorIcon}>⚠</span>
            <p style={styles.errorCardText}>{error || "Something went wrong"}</p>
            <button style={styles.resetBtn} onClick={reset}>Try Again</button>
          </div>
        )}

      </main>

      {/* Footer */}
      <footer style={styles.footer}>
        XLM-RoBERTa · BIO Token Classification · Sinhala NLP Research
      </footer>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────
const styles = {
  root: {
    minHeight: "100vh",
    backgroundColor: "#0a0a12",
    color: "#e0e0f0",
    fontFamily: "'DM Mono', 'Fira Code', monospace",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    padding: "40px 20px",
    position: "relative",
    overflow: "hidden",
  },
  grid: {
    position: "fixed",
    inset: 0,
    backgroundImage: "linear-gradient(#1a1a2e22 1px, transparent 1px), linear-gradient(90deg, #1a1a2e22 1px, transparent 1px)",
    backgroundSize: "40px 40px",
    pointerEvents: "none",
  },
  header: {
    textAlign: "center",
    marginBottom: "40px",
    position: "relative",
    zIndex: 1,
  },
  badge: {
    display: "inline-block",
    padding: "4px 14px",
    border: "1px solid #00e5a044",
    borderRadius: "20px",
    fontSize: "11px",
    color: "#00e5a0",
    letterSpacing: "2px",
    marginBottom: "16px",
    textTransform: "uppercase",
  },
  title: {
    fontSize: "clamp(28px, 5vw, 48px)",
    fontWeight: "700",
    margin: "0 0 8px",
    letterSpacing: "-1px",
    color: "#ffffff",
  },
  titleSin: {
    color: "#00e5a0",
  },
  subtitle: {
    color: "#606080",
    fontSize: "13px",
    letterSpacing: "4px",
    textTransform: "uppercase",
    margin: 0,
  },
  main: {
    width: "100%",
    maxWidth: "680px",
    position: "relative",
    zIndex: 1,
  },
  inputCard: {
    background: "#10101e",
    border: "1px solid #1e1e30",
    borderRadius: "16px",
    padding: "32px",
  },
  label: {
    display: "block",
    fontSize: "11px",
    letterSpacing: "2px",
    color: "#606080",
    textTransform: "uppercase",
    marginBottom: "10px",
  },
  inputRow: {
    display: "flex",
    gap: "10px",
    marginBottom: "8px",
  },
  input: {
    flex: 1,
    background: "#0a0a12",
    border: "1px solid #2a2a3a",
    borderRadius: "8px",
    padding: "14px 16px",
    color: "#e0e0f0",
    fontSize: "13px",
    outline: "none",
    fontFamily: "inherit",
    transition: "border-color 0.2s",
  },
  errorText: {
    color: "#ff4d4d",
    fontSize: "12px",
    margin: "4px 0 0",
  },
  optionRow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    margin: "20px 0",
    flexWrap: "wrap",
  },
  optionLabel: {
    fontSize: "11px",
    color: "#606080",
    letterSpacing: "1px",
    marginRight: "4px",
  },
  chip: {
    padding: "6px 14px",
    border: "1px solid #2a2a3a",
    borderRadius: "20px",
    background: "transparent",
    color: "#606080",
    fontSize: "12px",
    cursor: "pointer",
    fontFamily: "inherit",
    transition: "all 0.2s",
  },
  chipActive: {
    border: "1px solid #00e5a0",
    color: "#00e5a0",
    background: "#00e5a011",
  },
  processBtn: {
    width: "100%",
    padding: "16px",
    background: "linear-gradient(135deg, #00e5a0, #00b8ff)",
    border: "none",
    borderRadius: "10px",
    color: "#0a0a12",
    fontSize: "15px",
    fontWeight: "700",
    fontFamily: "inherit",
    letterSpacing: "1px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "10px",
    marginTop: "8px",
    transition: "transform 0.1s, opacity 0.2s",
  },
  btnArrow: { fontSize: "18px" },
  processingCard: {
    background: "#10101e",
    border: "1px solid #1e1e30",
    borderRadius: "16px",
    padding: "32px",
  },
  stages: {
    display: "flex",
    flexDirection: "column",
    gap: "16px",
    marginBottom: "28px",
  },
  stageItem: {
    display: "flex",
    alignItems: "flex-start",
    gap: "16px",
    padding: "14px 16px",
    borderRadius: "10px",
    border: "1px solid transparent",
    transition: "all 0.3s",
  },
  stageActive: {
    border: "1px solid #00e5a033",
    background: "#00e5a008",
  },
  stageDone: {
    border: "1px solid #ffffff11",
    background: "#ffffff04",
  },
  stageWaiting: {
    opacity: 0.3,
  },
  stageIconWrap: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "4px",
  },
  stageIcon: { fontSize: "20px" },
  stageLine: {
    width: "1px",
    height: "20px",
    backgroundColor: "#2a2a3a",
  },
  stageName: {
    fontSize: "14px",
    fontWeight: "600",
    color: "#e0e0f0",
  },
  stageDesc: {
    fontSize: "12px",
    color: "#00e5a0",
    marginTop: "4px",
    animation: "pulse 2s infinite",
  },
  progressWrap: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    marginBottom: "20px",
  },
  progressBar: {
    flex: 1,
    height: "4px",
    background: "#1e1e30",
    borderRadius: "2px",
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    background: "linear-gradient(90deg, #00e5a0, #00b8ff)",
    borderRadius: "2px",
    transition: "width 0.5s ease",
  },
  progressText: {
    fontSize: "12px",
    color: "#00e5a0",
    minWidth: "36px",
  },
  logsWrap: {
    background: "#0a0a12",
    border: "1px solid #1e1e30",
    borderRadius: "8px",
    padding: "16px",
    maxHeight: "200px",
    overflowY: "auto",
    fontFamily: "inherit",
  },
  logLine: {
    display: "flex",
    gap: "12px",
    fontSize: "12px",
    marginBottom: "6px",
    lineHeight: "1.4",
  },
  logTime: { color: "#404060", minWidth: "70px" },
  logMsg:  { color: "#a0a0c0" },
  logCursor: {
    color: "#00e5a0",
    animation: "blink 1s infinite",
    fontSize: "14px",
  },
  resultsCard: {
    background: "#10101e",
    border: "1px solid #1e1e30",
    borderRadius: "16px",
    padding: "32px",
  },
  resultsHeader: { marginBottom: "24px" },
  successBadge: {
    display: "inline-block",
    padding: "4px 12px",
    background: "#00e5a011",
    border: "1px solid #00e5a033",
    borderRadius: "20px",
    fontSize: "11px",
    color: "#00e5a0",
    letterSpacing: "1px",
    marginBottom: "10px",
  },
  resultsTitle: {
    margin: 0,
    fontSize: "22px",
    fontWeight: "700",
    color: "#ffffff",
  },
  statsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, 1fr)",
    gap: "12px",
    marginBottom: "28px",
  },
  statCard: {
    background: "#0a0a12",
    border: "1px solid #1e1e30",
    borderRadius: "10px",
    padding: "16px",
  },
  statValue: {
    fontSize: "32px",
    fontWeight: "700",
    lineHeight: 1,
    marginBottom: "4px",
  },
  statLabel: {
    fontSize: "11px",
    color: "#606080",
    letterSpacing: "1px",
    textTransform: "uppercase",
    marginBottom: "10px",
  },
  statBar: {
    height: "3px",
    background: "#1e1e30",
    borderRadius: "2px",
    overflow: "hidden",
    marginBottom: "6px",
  },
  statPct: {
    fontSize: "11px",
    fontWeight: "600",
  },
  actionsRow: {
    display: "flex",
    gap: "12px",
  },
  downloadBtn: {
    flex: 1,
    padding: "14px",
    background: "linear-gradient(135deg, #00e5a0, #00b8ff)",
    border: "none",
    borderRadius: "10px",
    color: "#0a0a12",
    fontSize: "14px",
    fontWeight: "700",
    fontFamily: "inherit",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "8px",
  },
  resetBtn: {
    padding: "14px 20px",
    background: "transparent",
    border: "1px solid #2a2a3a",
    borderRadius: "10px",
    color: "#a0a0c0",
    fontSize: "13px",
    fontFamily: "inherit",
    cursor: "pointer",
  },
  errorCard: {
    background: "#10101e",
    border: "1px solid #ff4d4d33",
    borderRadius: "16px",
    padding: "32px",
    textAlign: "center",
  },
  errorIcon: { fontSize: "36px", display: "block", marginBottom: "12px" },
  errorCardText: { color: "#ff4d4d", marginBottom: "20px" },
  footer: {
    marginTop: "40px",
    fontSize: "11px",
    color: "#303050",
    letterSpacing: "2px",
    textTransform: "uppercase",
    position: "relative",
    zIndex: 1,
  },
};
