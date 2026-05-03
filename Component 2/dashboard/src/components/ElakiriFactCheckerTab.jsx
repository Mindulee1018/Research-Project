import { useState, useEffect, useRef } from "react";

const ELAKIRI_API = "http://localhost:8003";

const STAGES = [
  { id: "fetching",  label: "Processing Input",                icon: "📋", desc: "Fetching post or processing text claim..." },
  { id: "searching", label: "Searching 3 News Sources",        icon: "📰", desc: "Ada Derana · Sunday Observer · Daily Mirror · thePapare" },
  { id: "nli",       label: "NLI Fact Verification",           icon: "🧠", desc: "Running SUPPORTS / REFUTES / NEUTRAL per source..." },
];

export default function ElakiriFactCheckerTab() {
  const [inputType, setInputType] = useState("url");      // "url" or "text"
  const [inputValue, setInputValue] = useState("");
  const [status,   setStatus]   = useState("idle");
  const [stage,    setStage]    = useState(-1);
  const [progress, setProgress] = useState(0);
  const [logs,     setLogs]     = useState([]);
  const [results,  setResults]  = useState(null);
  const [error,    setError]    = useState("");

  const logsRef  = useRef(null);
  const pollRef  = useRef(null);
  const jobIdRef = useRef(null);

  const addLog = (msg) => setLogs(prev => [...prev, { msg, time: new Date().toLocaleTimeString() }]);

  useEffect(() => {
    if (logsRef.current) logsRef.current.scrollTop = logsRef.current.scrollHeight;
  }, [logs]);

  useEffect(() => () => clearInterval(pollRef.current), []);

  const isValidInput = () => {
    if (inputType === "url") return inputValue.includes("elakiri.com");
    return inputValue.trim().length >= 5;
  };

  const reset = () => {
    clearInterval(pollRef.current);
    setInputValue(""); setStatus("idle"); setStage(-1); setProgress(0);
    setLogs([]); setResults(null); setError("");
    jobIdRef.current = null;
  };

  const startFactCheck = async () => {
    if (!isValidInput()) {
      setError(inputType === "url"
        ? "Please enter a valid Elakiri post URL."
        : "Please enter a longer text claim (at least 5 characters)."
      );
      return;
    }

    setError(""); setStatus("processing"); setStage(0); setProgress(0);
    setLogs([]); setResults(null);
    addLog("🚀 Starting NLI fact-check...");

    try {
      const res = await fetch(`${ELAKIRI_API}/elakiri-factcheck`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_type: inputType, input_value: inputValue }),
      });
      if (!res.ok) throw new Error("Failed to start");
      const data = await res.json();
      if (data.error) { setError(data.error); setStatus("error"); return; }
      jobIdRef.current = data.job_id;
      addLog(`📋 Job started: ${data.job_id}`);
      pollRef.current = setInterval(pollStatus, 2000);
    } catch {
      setError("Could not connect to server. Make sure it's running on port 8003!");
      setStatus("error");
    }
  };

  const pollStatus = async () => {
    try {
      const res  = await fetch(`${ELAKIRI_API}/status/${jobIdRef.current}`);
      const data = await res.json();
      if (data.log)     addLog(data.log);
      if (data.stage    !== undefined) setStage(data.stage);
      if (data.progress !== undefined) setProgress(data.progress);
      if (data.status === "done") {
        clearInterval(pollRef.current);
        setStage(3); setProgress(100);
        setResults(data.results);
        setStatus("done");
        addLog("✅ Fact-check complete!");
      } else if (data.status === "error") {
        clearInterval(pollRef.current);
        setError(data.error || "Something went wrong.");
        setStatus("error");
      }
    } catch {}
  };

  const vColor = (v) =>
    v === "NOT DISINFO" ? "success" :
    v === "DISINFO"     ? "danger"  :
    v === "UNVERIFIED"  ? "secondary" : "warning";

  const vIcon = (v) =>
    v === "NOT DISINFO" ? "✅" :
    v === "DISINFO"     ? "❌" :
    v === "UNVERIFIED"  ? "❓" :
    v === "NO ARTICLES" ? "⚪" : "⚠️";

  const vLabel = (v) =>
    v === "NOT DISINFO" ? "NOT FAKE ✅" :
    v === "DISINFO"     ? "FAKE / DISINFO ❌" :
    v === "UNVERIFIED"  ? "UNVERIFIED ❓" :
    v === "NO ARTICLES" ? "No Articles Found" : "UNCERTAIN ⚠️";

  const nliColor = (label) =>
    label === "entailment"    ? "success" :
    label === "contradiction" ? "danger"  : "secondary";

  const nliBadge = (label) =>
    label === "entailment"    ? "✅ SUPPORTS"  :
    label === "contradiction" ? "❌ REFUTES"   : "⚪ NEUTRAL";

  return (
    <div className="card border-0 shadow-sm h-100">
      <div className="card-body p-4">

        {/* Header */}
        <div className="mb-4">
          <span className="badge rounded-pill bg-warning-subtle text-warning border border-warning-subtle mb-2">
            NLI Sports Fact Checker
          </span>
          <h4 className="mb-1 fw-bold text-dark text-center">
            <span className="text-warning">🧠</span> Sports Fact Checker
          </h4>
          <div className="text-muted small text-uppercase text-center" style={{ letterSpacing: "0.12em" }}>
            Ada Derana · Sunday Observer · Daily Mirror · thePapare
          </div>
        </div>

        {/* How it works */}
        <div className="rounded-4 p-3 mb-4 border border-warning-subtle bg-warning bg-opacity-10">
          <div className="small text-warning fw-semibold mb-1">🧠 FEVER NLI Methodology</div>
          <div className="small text-muted">
            Paste an <strong>Elakiri post URL</strong> or directly enter a <strong>text claim</strong>.
            The system extracts keywords, searches three Sri Lankan news sources, and uses
            <strong> NLI</strong> to classify each as
            <strong className="text-success"> SUPPORTS</strong> /
            <strong className="text-danger"> REFUTES</strong> /
            <strong className="text-secondary"> NEUTRAL</strong>.
          </div>
        </div>

        {/* ── IDLE ── */}
        {status === "idle" && (
          <>
            {/* Input type toggle */}
            <div className="mb-3">
              <label className="form-label small text-uppercase text-muted fw-semibold">
                Input Type
              </label>
              <div className="d-flex gap-2">
                <button
                  type="button"
                  className={`btn flex-fill rounded-pill ${inputType === "url" ? "btn-warning text-dark" : "btn-outline-secondary"}`}
                  onClick={() => { setInputType("url"); setInputValue(""); setError(""); }}
                >
                  🔗 Elakiri Post URL
                </button>
                <button
                  type="button"
                  className={`btn flex-fill rounded-pill ${inputType === "text" ? "btn-warning text-dark" : "btn-outline-secondary"}`}
                  onClick={() => { setInputType("text"); setInputValue(""); setError(""); }}
                >
                  💬 Direct Text Claim
                </button>
              </div>
            </div>

            {/* Input field */}
            <div className="mb-3">
              <label className="form-label small text-uppercase text-muted fw-semibold">
                {inputType === "url" ? "Elakiri Post URL" : "Text Claim to Verify"}
              </label>
              {inputType === "url" ? (
                <input
                  type="text"
                  className={`form-control form-control-lg ${
                    error ? "is-invalid" :
                    inputValue && isValidInput() ? "border-warning" : ""
                  }`}
                  placeholder="https://www.elakiri.com/threads/..."
                  value={inputValue}
                  onChange={e => { setInputValue(e.target.value); setError(""); }}
                  onKeyDown={e => e.key === "Enter" && startFactCheck()}
                />
              ) : (
                <textarea
                  className={`form-control ${
                    error ? "is-invalid" :
                    inputValue && isValidInput() ? "border-warning" : ""
                  }`}
                  rows="3"
                  placeholder="e.g. Pathum Nissanka sold to Kolkata Knight Riders for IPL 2026"
                  value={inputValue}
                  onChange={e => { setInputValue(e.target.value); setError(""); }}
                />
              )}
              {error && <div className="invalid-feedback d-block">{error}</div>}
              {inputType === "text" && (
                <div className="form-text small">
                  💡 Tip: Use English keywords (player names, team names, events) for best search results.
                </div>
              )}
            </div>

            <button
              type="button"
              className="btn btn-warning btn-lg w-100 fw-semibold text-dark"
              onClick={startFactCheck}
              disabled={!isValidInput()}
              style={{ opacity: isValidInput() ? 1 : 0.5 }}
            >
              🧠 Fact Check {inputType === "url" ? "This Post" : "This Claim"} →
            </button>
          </>
        )}

        {/* ── PROCESSING ── */}
        {status === "processing" && (
          <>
            <div className="d-flex flex-column gap-3 mb-4">
              {STAGES.map((s, i) => {
                const state = i < stage ? "done" : i === stage ? "active" : "waiting";
                return (
                  <div key={s.id}
                    className={`rounded-4 p-3 border ${
                      state === "active"  ? "border-warning bg-warning bg-opacity-10" :
                      state === "done"    ? "border-success bg-success bg-opacity-10" :
                                           "border-light bg-light"
                    }`}
                    style={{ opacity: state === "waiting" ? 0.75 : 1 }}
                  >
                    <div className="d-flex align-items-start gap-3">
                      <div className={`d-flex align-items-center justify-content-center rounded-circle fw-bold ${
                        state === "active" ? "bg-warning text-dark" :
                        state === "done"   ? "bg-success text-white" :
                                            "bg-secondary-subtle text-secondary"
                      }`} style={{ width: 40, height: 40, flexShrink: 0 }}>
                        {state === "done" ? "✓" : s.icon}
                      </div>
                      <div className="flex-grow-1">
                        <div className="fw-semibold text-dark">{s.label}</div>
                        {state === "active" && <div className="small text-warning mt-1">{s.desc}</div>}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="d-flex align-items-center gap-3 mb-3">
              <div className="progress flex-grow-1" style={{ height: "10px" }}>
                <div className="progress-bar progress-bar-striped progress-bar-animated bg-warning"
                  style={{ width: `${progress}%` }} />
              </div>
              <div className="small text-warning fw-semibold">{progress}%</div>
            </div>

            <div ref={logsRef} className="border rounded-4 p-3 bg-light" style={{ maxHeight: "180px", overflowY: "auto" }}>
              {logs.map((l, i) => (
                <div key={i} className="d-flex gap-3 mb-2 small">
                  <span className="text-muted" style={{ minWidth: "74px", flexShrink: 0 }}>{l.time}</span>
                  <span className="text-dark">{l.msg}</span>
                </div>
              ))}
              <div className="text-warning small fw-semibold">▋</div>
            </div>
          </>
        )}

        {/* ── RESULTS ── */}
        {status === "done" && results && (
          <>
            {/* Post / Claim info */}
            <div className="rounded-4 border p-3 mb-3 bg-light">
              <div className="small text-muted text-uppercase fw-semibold mb-1">
                {results.input_type === "url" ? "📋 Elakiri Post" : "💬 Text Claim"}
              </div>
              <div className="fw-semibold text-dark mb-2">{results.post_title}</div>
              {results.post_content && results.input_type === "url" && (
                <div className="small text-muted mb-2">{results.post_content}...</div>
              )}
              <div className="d-flex flex-wrap gap-1 mb-2">
                {results.keywords?.map((kw, i) => (
                  <span key={i} className="badge bg-secondary-subtle text-secondary border">🔑 {kw}</span>
                ))}
              </div>
              <div className="small text-muted">
                <strong>Claim:</strong> "{results.claim_checked}"
              </div>
            </div>

            {/* Final verdict */}
            <div className={`rounded-4 border border-${vColor(results.final_verdict)}-subtle bg-${vColor(results.final_verdict)} bg-opacity-10 p-4 text-center mb-3`}>
              <div className={`fs-2 fw-bold text-${vColor(results.final_verdict)} mb-1`}>
                {vLabel(results.final_verdict)}
              </div>
              <div className={`badge bg-${vColor(results.final_verdict)} mb-2`}>
                {results.final_confidence}
              </div>
              <div className="small text-muted">{results.final_explanation}</div>
            </div>

            {/* Per source breakdown */}
            <div className="mb-3">
              <div className="small text-uppercase text-muted fw-semibold mb-3">
                📰 Per Source Breakdown
              </div>

              {results.per_source && Object.entries(results.per_source).map(([source, data], i) => (
                <div key={i} className={`rounded-4 border border-${vColor(data.verdict)}-subtle p-3 mb-2`}>

                  <div className="d-flex align-items-center justify-content-between mb-2">
                    <div className="fw-semibold">{source}</div>
                    <span className={`badge bg-${vColor(data.verdict)}`}>
                      {vIcon(data.verdict)} {data.verdict === "NO ARTICLES" ? "No Articles" : data.verdict}
                    </span>
                  </div>

                  {data.verdict === "NO ARTICLES" && (
                    <div className="small text-muted">⚪ No relevant articles found on this source</div>
                  )}

                  {data.verdict !== "NO ARTICLES" && (
                    <>
                      <div className="small text-muted mb-2">{data.explanation}</div>
                      {data.articles?.slice(0, 3).map((a, j) => (
                        <div key={j} className={`d-flex align-items-center gap-2 p-2 rounded-3 bg-${nliColor(a.label)} bg-opacity-10 mb-1`}>
                          <span className={`badge bg-${nliColor(a.label)} flex-shrink-0`}>
                            {nliBadge(a.label)}
                          </span>
                          <div className="small text-dark text-truncate flex-grow-1">
                            {a.title}
                          </div>
                          <div className="small text-muted flex-shrink-0">
                            {a.score?.toFixed(2)}
                          </div>
                        </div>
                      ))}
                    </>
                  )}
                </div>
              ))}
            </div>

            <button type="button" className="btn btn-outline-secondary w-100" onClick={reset}>
              ↺ Check Another
            </button>
          </>
        )}

        {/* ── ERROR ── */}
        {status === "error" && (
          <div className="text-center border border-danger-subtle bg-danger bg-opacity-10 rounded-4 p-4">
            <div className="fs-2 mb-2">⚠</div>
            <div className="text-danger mb-3 fw-semibold">{error}</div>
            <button type="button" className="btn btn-outline-secondary" onClick={reset}>Try Again</button>
          </div>
        )}

      </div>
    </div>
  );
}