import { useState, useEffect, useRef } from "react";

const API_URL = "http://localhost:8000";

const STAGES = [
  { id: "scraping",  label: "Scraping Comments",   icon: "⬇", desc: "Fetching comments from YouTube..." },
  { id: "cleaning",  label: "Cleaning Data",        icon: "🧹", desc: "Removing noise, emojis & URLs..." },
  { id: "labeling",  label: "Classifying Comments", icon: "🤖", desc: "Running XLM-R model predictions..." },
  { id: "saving",    label: "Building Datasets",    icon: "💾", desc: "Generating Comment & Post CSVs..." },
];

export default function App() {
  const [url, setUrl]           = useState("");
  const [maxComments, setMax]   = useState(500);
  const [status, setStatus]     = useState("idle");
  const [stage, setStage]       = useState(-1);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs]         = useState([]);
  const [results, setResults]   = useState(null);
  const [commentCsv, setCommentCsv] = useState(null);
  const [postCsv, setPostCsv]       = useState(null);
  const [error, setError]       = useState("");
  const logsRef  = useRef(null);
  const pollRef  = useRef(null);
  const jobIdRef = useRef(null);

  const addLog = (msg) => setLogs(prev => [...prev, { msg, time: new Date().toLocaleTimeString() }]);

  useEffect(() => {
    if (logsRef.current) logsRef.current.scrollTop = logsRef.current.scrollHeight;
  }, [logs]);

  useEffect(() => () => clearInterval(pollRef.current), []);

  const isValidUrl = (u) => u.includes("youtube.com") || u.includes("youtu.be");

  const startPipeline = async () => {
    if (!isValidUrl(url)) { setError("Please enter a valid YouTube URL"); return; }
    setError(""); setStatus("processing"); setStage(0); setProgress(0);
    setLogs([]); setResults(null); setCommentCsv(null); setPostCsv(null);
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
      if (data.stage    !== undefined) setStage(data.stage);
      if (data.progress !== undefined) setProgress(data.progress);
      if (data.status === "done") {
        clearInterval(pollRef.current);
        setStage(4); setProgress(100);
        setResults(data.results);
        setCommentCsv(data.comment_csv);
        setPostCsv(data.post_csv);
        setStatus("done");
        addLog("✅ Pipeline complete!");
      } else if (data.status === "error") {
        clearInterval(pollRef.current);
        setError(data.error || "Something went wrong");
        setStatus("error");
      }
    } catch (e) {}
  };

  const downloadCsv = (csvData, filename) => {
    if (!csvData) return;
    const blob = new Blob([csvData], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href  = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
  };

  const reset = () => {
    setUrl(""); setStatus("idle"); setStage(-1); setProgress(0);
    setLogs([]); setResults(null); setCommentCsv(null); setPostCsv(null); setError("");
    jobIdRef.current = null;
  };

  return (
    <div style={s.root}>
      <div style={s.grid} />

      <header style={s.header}>
        <div style={s.badge}>NLP Research Tool</div>
        <h1 style={s.title}><span style={s.sin}>සිංහල</span> Hate & Disinfo Detector</h1>
        <p style={s.subtitle}>Scrape · Clean · Classify · Download</p>
      </header>

      <main style={s.main}>

        {/* ── INPUT ── */}
        {status === "idle" && (
          <div style={s.card}>
            <label style={s.label}>YouTube Video URL</label>
            <input
              style={{ ...s.input, borderColor: error ? "#ff4d4d" : url && isValidUrl(url) ? "#00e5a0" : "#2a2a3a" }}
              placeholder="https://www.youtube.com/watch?v=..."
              value={url}
              onChange={e => { setUrl(e.target.value); setError(""); }}
              onKeyDown={e => e.key === "Enter" && startPipeline()}
            />
            {error && <p style={s.errTxt}>{error}</p>}

            <div style={s.optRow}>
              <span style={s.optLbl}>Max Comments</span>
              {[100, 250, 500, 1000].map(n => (
                <button key={n} style={{ ...s.chip, ...(maxComments === n ? s.chipOn : {}) }} onClick={() => setMax(n)}>{n}</button>
              ))}
            </div>

            <button
              style={{ ...s.procBtn, opacity: url && isValidUrl(url) ? 1 : 0.5 }}
              onClick={startPipeline}
              disabled={!url || !isValidUrl(url)}
            >
              Process Video <span>→</span>
            </button>
          </div>
        )}

        {/* ── PROCESSING ── */}
        {status === "processing" && (
          <div style={s.card}>
            <div style={s.stages}>
              {STAGES.map((st, i) => {
                const state = i < stage ? "done" : i === stage ? "active" : "wait";
                return (
                  <div key={st.id} style={{ ...s.stageRow, ...(state === "active" ? s.stageActive : state === "done" ? s.stageDone : s.stageWait) }}>
                    <span style={s.stageIco}>{state === "done" ? "✓" : st.icon}</span>
                    <div>
                      <div style={s.stageName}>{st.label}</div>
                      {state === "active" && <div style={s.stageDesc}>{st.desc}</div>}
                    </div>
                  </div>
                );
              })}
            </div>

            <div style={s.progWrap}>
              <div style={s.progBar}><div style={{ ...s.progFill, width: `${progress}%` }} /></div>
              <span style={s.progTxt}>{progress}%</span>
            </div>

            <div style={s.logs} ref={logsRef}>
              {logs.map((l, i) => (
                <div key={i} style={s.logLine}>
                  <span style={s.logTime}>{l.time}</span>
                  <span style={s.logMsg}>{l.msg}</span>
                </div>
              ))}
              <div style={s.cursor}>▋</div>
            </div>
          </div>
        )}

        {/* ── RESULTS ── */}
        {status === "done" && results && (
          <div style={s.card}>
            {/* Video info */}
            <div style={s.videoInfo}>
              <div style={s.videoIdBadge}>Video ID: #{results.video_id}</div>
              <div style={s.videoTitle}>{results.title}</div>
              <div style={s.videoMeta}>
                <span style={s.channelTag}>📺 {results.channel}</span>
                <span style={{ ...s.titleLabelTag, backgroundColor: results.title_label === "HATE" ? "#ff4d4d22" : results.title_label === "DISINFO" ? "#ffaa0022" : "#00e5a022", color: results.title_label === "HATE" ? "#ff4d4d" : results.title_label === "DISINFO" ? "#ffaa00" : "#00e5a0", borderColor: results.title_label === "HATE" ? "#ff4d4d44" : results.title_label === "DISINFO" ? "#ffaa0044" : "#00e5a044" }}>
                  Title: {results.title_label}
                </span>
              </div>
            </div>

            {/* Stats */}
            <div style={s.statsGrid}>
              {[
                { label: "Total",   value: results.total,   color: "#a0a0c0" },
                { label: "Hate",    value: results.hate,    color: "#ff4d4d" },
                { label: "Disinfo", value: results.disinfo, color: "#ffaa00" },
                { label: "Normal",  value: results.normal,  color: "#00e5a0" },
              ].map(st => (
                <div key={st.label} style={{ ...s.statCard, borderColor: st.color + "44" }}>
                  <div style={{ ...s.statVal, color: st.color }}>{st.value}</div>
                  <div style={s.statLbl}>{st.label}</div>
                  <div style={s.statBarWrap}>
                    <div style={{ height: "100%", width: `${results.total > 0 ? (st.value / results.total * 100).toFixed(0) : 0}%`, backgroundColor: st.color, borderRadius: "2px" }} />
                  </div>
                  <div style={{ fontSize: "11px", color: st.color, fontWeight: 600 }}>
                    {results.total > 0 ? (st.value / results.total * 100).toFixed(1) : 0}%
                  </div>
                </div>
              ))}
            </div>

            {/* Download buttons */}
            <div style={s.dlSection}>
              <div style={s.dlLabel}>Download Datasets</div>
              <div style={s.dlRow}>
                <button style={s.dlBtn} onClick={() => downloadCsv(commentCsv, `comment_dataset_video${results.video_id}.csv`)}>
                  <div style={s.dlBtnTitle}>⬇ Comment Dataset</div>
                  <div style={s.dlBtnDesc}>Video ID · Author · Likes · Label · Hate Words</div>
                </button>
                <button style={{ ...s.dlBtn, background: "linear-gradient(135deg, #ffaa00, #ff6600)" }} onClick={() => downloadCsv(postCsv, `post_dataset_video${results.video_id}.csv`)}>
                  <div style={s.dlBtnTitle}>⬇ Post Dataset</div>
                  <div style={s.dlBtnDesc}>Video ID · Channel · Title · Title Label</div>
                </button>
              </div>
            </div>

            <button style={s.resetBtn} onClick={reset}>↺ Analyze Another Video</button>
          </div>
        )}

        {/* ── ERROR ── */}
        {status === "error" && (
          <div style={{ ...s.card, borderColor: "#ff4d4d33", textAlign: "center" }}>
            <div style={{ fontSize: "36px", marginBottom: "12px" }}>⚠</div>
            <p style={{ color: "#ff4d4d", marginBottom: "20px" }}>{error}</p>
            <button style={s.resetBtn} onClick={reset}>Try Again</button>
          </div>
        )}

      </main>

      <footer style={s.footer}>XLM-RoBERTa · BIO Token Classification · Sinhala NLP Research</footer>
    </div>
  );
}

const s = {
  root:       { minHeight: "100vh", backgroundColor: "#0a0a12", color: "#e0e0f0", fontFamily: "'DM Mono','Fira Code',monospace", display: "flex", flexDirection: "column", alignItems: "center", padding: "40px 20px", position: "relative", overflow: "hidden" },
  grid:       { position: "fixed", inset: 0, backgroundImage: "linear-gradient(#1a1a2e22 1px,transparent 1px),linear-gradient(90deg,#1a1a2e22 1px,transparent 1px)", backgroundSize: "40px 40px", pointerEvents: "none" },
  header:     { textAlign: "center", marginBottom: "40px", position: "relative", zIndex: 1 },
  badge:      { display: "inline-block", padding: "4px 14px", border: "1px solid #00e5a044", borderRadius: "20px", fontSize: "11px", color: "#00e5a0", letterSpacing: "2px", marginBottom: "16px", textTransform: "uppercase" },
  title:      { fontSize: "clamp(28px,5vw,48px)", fontWeight: "700", margin: "0 0 8px", letterSpacing: "-1px", color: "#ffffff" },
  sin:        { color: "#00e5a0" },
  subtitle:   { color: "#606080", fontSize: "13px", letterSpacing: "4px", textTransform: "uppercase", margin: 0 },
  main:       { width: "100%", maxWidth: "680px", position: "relative", zIndex: 1 },
  card:       { background: "#10101e", border: "1px solid #1e1e30", borderRadius: "16px", padding: "32px", marginBottom: "16px" },
  label:      { display: "block", fontSize: "11px", letterSpacing: "2px", color: "#606080", textTransform: "uppercase", marginBottom: "10px" },
  input:      { width: "100%", boxSizing: "border-box", background: "#0a0a12", border: "1px solid #2a2a3a", borderRadius: "8px", padding: "14px 16px", color: "#e0e0f0", fontSize: "13px", outline: "none", fontFamily: "inherit", marginBottom: "8px" },
  errTxt:     { color: "#ff4d4d", fontSize: "12px", margin: "4px 0 0" },
  optRow:     { display: "flex", alignItems: "center", gap: "8px", margin: "20px 0", flexWrap: "wrap" },
  optLbl:     { fontSize: "11px", color: "#606080", letterSpacing: "1px" },
  chip:       { padding: "6px 14px", border: "1px solid #2a2a3a", borderRadius: "20px", background: "transparent", color: "#606080", fontSize: "12px", cursor: "pointer", fontFamily: "inherit" },
  chipOn:     { border: "1px solid #00e5a0", color: "#00e5a0", background: "#00e5a011" },
  procBtn:    { width: "100%", padding: "16px", background: "linear-gradient(135deg,#00e5a0,#00b8ff)", border: "none", borderRadius: "10px", color: "#0a0a12", fontSize: "15px", fontWeight: "700", fontFamily: "inherit", letterSpacing: "1px", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: "10px" },
  stages:     { display: "flex", flexDirection: "column", gap: "12px", marginBottom: "24px" },
  stageRow:   { display: "flex", alignItems: "flex-start", gap: "14px", padding: "12px 14px", borderRadius: "10px", border: "1px solid transparent" },
  stageActive:{ border: "1px solid #00e5a033", background: "#00e5a008" },
  stageDone:  { border: "1px solid #ffffff11", background: "#ffffff04" },
  stageWait:  { opacity: 0.3 },
  stageIco:   { fontSize: "18px", minWidth: "24px" },
  stageName:  { fontSize: "14px", fontWeight: "600", color: "#e0e0f0" },
  stageDesc:  { fontSize: "12px", color: "#00e5a0", marginTop: "4px" },
  progWrap:   { display: "flex", alignItems: "center", gap: "12px", marginBottom: "20px" },
  progBar:    { flex: 1, height: "4px", background: "#1e1e30", borderRadius: "2px", overflow: "hidden" },
  progFill:   { height: "100%", background: "linear-gradient(90deg,#00e5a0,#00b8ff)", borderRadius: "2px", transition: "width 0.5s ease" },
  progTxt:    { fontSize: "12px", color: "#00e5a0", minWidth: "36px" },
  logs:       { background: "#0a0a12", border: "1px solid #1e1e30", borderRadius: "8px", padding: "16px", maxHeight: "180px", overflowY: "auto" },
  logLine:    { display: "flex", gap: "12px", fontSize: "12px", marginBottom: "6px" },
  logTime:    { color: "#404060", minWidth: "70px" },
  logMsg:     { color: "#a0a0c0" },
  cursor:     { color: "#00e5a0", fontSize: "14px" },
  videoInfo:  { background: "#0a0a12", border: "1px solid #1e1e30", borderRadius: "10px", padding: "16px", marginBottom: "20px" },
  videoIdBadge: { display: "inline-block", padding: "3px 10px", background: "#00e5a011", border: "1px solid #00e5a033", borderRadius: "20px", fontSize: "11px", color: "#00e5a0", marginBottom: "8px" },
  videoTitle: { fontSize: "15px", fontWeight: "600", color: "#ffffff", marginBottom: "8px", lineHeight: 1.4 },
  videoMeta:  { display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" },
  channelTag: { fontSize: "12px", color: "#606080" },
  titleLabelTag: { fontSize: "11px", padding: "3px 10px", borderRadius: "20px", border: "1px solid", fontWeight: "600", letterSpacing: "1px" },
  statsGrid:  { display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: "12px", marginBottom: "24px" },
  statCard:   { background: "#0a0a12", border: "1px solid #1e1e30", borderRadius: "10px", padding: "16px" },
  statVal:    { fontSize: "32px", fontWeight: "700", lineHeight: 1, marginBottom: "4px" },
  statLbl:    { fontSize: "11px", color: "#606080", letterSpacing: "1px", textTransform: "uppercase", marginBottom: "10px" },
  statBarWrap:{ height: "3px", background: "#1e1e30", borderRadius: "2px", overflow: "hidden", marginBottom: "6px" },
  dlSection:  { marginBottom: "16px" },
  dlLabel:    { fontSize: "11px", color: "#606080", letterSpacing: "2px", textTransform: "uppercase", marginBottom: "10px" },
  dlRow:      { display: "flex", gap: "12px" },
  dlBtn:      { flex: 1, padding: "16px", background: "linear-gradient(135deg,#00e5a0,#00b8ff)", border: "none", borderRadius: "10px", color: "#0a0a12", cursor: "pointer", fontFamily: "inherit", textAlign: "left" },
  dlBtnTitle: { fontSize: "14px", fontWeight: "700", marginBottom: "4px" },
  dlBtnDesc:  { fontSize: "10px", opacity: 0.7, letterSpacing: "0.5px" },
  resetBtn:   { width: "100%", padding: "14px", background: "transparent", border: "1px solid #2a2a3a", borderRadius: "10px", color: "#a0a0c0", fontSize: "13px", fontFamily: "inherit", cursor: "pointer" },
  footer:     { marginTop: "40px", fontSize: "11px", color: "#303050", letterSpacing: "2px", textTransform: "uppercase", position: "relative", zIndex: 1 },
};
