import { useEffect, useRef, useState } from "react";
import Component1ModelStatus from "./Component1ModelStatus";  

const API_URL = "http://localhost:8000";

const STAGES = [
  {
    id: "scraping",
    label: "Scraping Comments",
    icon: "⬇",
    desc: "Fetching comments from YouTube...",
  },
  {
    id: "cleaning",
    label: "Cleaning Data",
    icon: "🧹",
    desc: "Removing noise, emojis & URLs...",
  },
  {
    id: "labeling",
    label: "Classifying Comments",
    icon: "🤖",
    desc: "Running XLM-R model predictions...",
  },
  {
    id: "saving",
    label: "Saving Results",
    icon: "💾",
    desc: "Generating CSV output...",
  },
];

export default function Component1PipelineCard() {
  const [url, setUrl] = useState("");
  const [maxComments, setMaxComments] = useState(500);
  const [status, setStatus] = useState("idle");
  const [stage, setStage] = useState(-1);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState([]);
  const [results, setResults] = useState(null);
  const [csvData, setCsvData] = useState(null);
  const [error, setError] = useState("");
  const [showModel, setShowModel] = useState(false);  // ← ADD HERE


  const logsRef = useRef(null);
  const pollRef = useRef(null);
  const jobIdRef = useRef(null);

  const addLog = (msg) => {
    setLogs((prev) => [
      ...prev,
      {
        msg,
        time: new Date().toLocaleTimeString(),
      },
    ]);
  };

  useEffect(() => {
    if (logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [logs]);

  useEffect(() => {
    return () => clearInterval(pollRef.current);
  }, []);

  const isValidUrl = (value) =>
    value.includes("youtube.com") || value.includes("youtu.be");

  const reset = () => {
    clearInterval(pollRef.current);
    setUrl("");
    setMaxComments(500);
    setStatus("idle");
    setStage(-1);
    setProgress(0);
    setLogs([]);
    setResults(null);
    setCsvData(null);
    setError("");
    jobIdRef.current = null;
  };

  const startPipeline = async () => {
    if (!isValidUrl(url)) {
      setError("Please enter a valid YouTube URL.");
      return;
    }

    setError("");
    setStatus("processing");
    setStage(0);
    setProgress(0);
    setLogs([]);
    setResults(null);
    setCsvData(null);

    addLog("Starting pipeline...");

    try {
      const res = await fetch(`${API_URL}/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          youtube_url: url,
          max_comments: maxComments,
        }),
      });

      if (!res.ok) {
        throw new Error("Failed to start pipeline");
      }

      const data = await res.json();
      jobIdRef.current = data.job_id;
      addLog(`Job started: ${data.job_id}`);

      clearInterval(pollRef.current);
      pollRef.current = setInterval(pollStatus, 2000);
    } catch (e) {
      setError("Could not connect to Component 1 backend.");
      setStatus("error");
    }
  };

  const pollStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/status/${jobIdRef.current}`);
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
        addLog("Pipeline complete.");
      } else if (data.status === "error") {
        clearInterval(pollRef.current);
        setError(data.error || "Something went wrong.");
        setStatus("error");
      }
    } catch {
      // keep polling
    }
  };

  const downloadCsv = () => {
    if (!csvData) return;

    const blob = new Blob([csvData], {
      type: "text/csv;charset=utf-8;",
    });

    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `sinhala_analysis_${Date.now()}.csv`;
    link.click();
  };

  return (
    <div className="card border-0 shadow-sm h-100">
      <div className="card-body p-4">
        {showModel && <Component1ModelStatus onClose={() => setShowModel(false)} />}
        <div className="mb-4">
          <span className="badge rounded-pill bg-success-subtle text-success border border-success-subtle mb-2">
            Component 1
          </span>

          <h4 className="mb-1 fw-bold text-dark text-center">
            <span className="text-success">සිංහල</span> Hate Detector
          </h4>

          <div
            className="text-muted small text-uppercase text-center"
            style={{ letterSpacing: "0.12em" }}
          >
            Scrape · Clean · Classify · Download
          </div>
          <div className="text-center mt-2">
            <button
              type="button"
              className="btn btn-sm rounded-pill btn-outline-secondary"
              onClick={() => setShowModel(true)}
          >
    🧠 Model Status
  </button>
</div>
        </div>

        {status === "idle" && (
          <>
            <div className="mb-3">
              <label className="form-label small text-uppercase text-muted fw-semibold">
                YouTube Video URL
              </label>
              <input
                type="text"
                className={`form-control form-control-lg ${
                  error
                    ? "is-invalid"
                    : url && isValidUrl(url)
                    ? "border-success"
                    : ""
                }`}
                placeholder="https://www.youtube.com/watch?v=..."
                value={url}
                onChange={(e) => {
                  setUrl(e.target.value);
                  setError("");
                }}
                onKeyDown={(e) => e.key === "Enter" && startPipeline()}
              />
              {error && <div className="invalid-feedback d-block">{error}</div>}
            </div>

            <div className="mb-4">
              <div className="small text-muted mb-2 text-uppercase fw-semibold">
                Max Comments
              </div>
              <div className="d-flex flex-wrap gap-2">
                {[100, 250, 500, 1000].map((n) => (
                  <button
                    key={n}
                    type="button"
                    className={`btn btn-sm rounded-pill ${
                      maxComments === n
                        ? "btn-success"
                        : "btn-outline-secondary"
                    }`}
                    onClick={() => setMaxComments(n)}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>

            <button
              type="button"
              className="btn btn-primary btn-lg w-100 fw-semibold"
              onClick={startPipeline}
              disabled={!url || !isValidUrl(url)}
            >
              Process Video →
            </button>
          </>
        )}

        {status === "processing" && (
          <>
            <div className="d-flex flex-column gap-3 mb-4">
              {STAGES.map((s, i) => {
                const state =
                  i < stage ? "done" : i === stage ? "active" : "waiting";

                return (
                  <div
                    key={s.id}
                    className={`rounded-4 p-3 border ${
                      state === "active"
                        ? "border-primary bg-primary bg-opacity-10"
                        : state === "done"
                        ? "border-success bg-success bg-opacity-10"
                        : "border-light bg-light"
                    }`}
                    style={{
                      opacity: state === "waiting" ? 0.75 : 1,
                    }}
                  >
                    <div className="d-flex align-items-start gap-3">
                      <div
                        className={`d-flex align-items-center justify-content-center rounded-circle fw-bold ${
                          state === "active"
                            ? "bg-primary text-white"
                            : state === "done"
                            ? "bg-success text-white"
                            : "bg-secondary-subtle text-secondary"
                        }`}
                        style={{ width: 40, height: 40, flexShrink: 0 }}
                      >
                        {state === "done" ? "✓" : s.icon}
                      </div>

                      <div className="flex-grow-1">
                        <div className="fw-semibold text-dark">{s.label}</div>
                        {state === "active" && (
                          <div className="small text-primary mt-1">{s.desc}</div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="d-flex align-items-center gap-3 mb-3">
              <div className="progress flex-grow-1" style={{ height: "10px" }}>
                <div
                  className="progress-bar progress-bar-striped progress-bar-animated bg-primary"
                  role="progressbar"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="small text-primary fw-semibold">{progress}%</div>
            </div>

            <div
              ref={logsRef}
              className="border rounded-4 p-3 bg-light"
              style={{ maxHeight: "220px", overflowY: "auto" }}
            >
              {logs.map((l, i) => (
                <div key={i} className="d-flex gap-3 mb-2 small">
                  <span
                    className="text-muted"
                    style={{ minWidth: "74px", flexShrink: 0 }}
                  >
                    {l.time}
                  </span>
                  <span className="text-dark">{l.msg}</span>
                </div>
              ))}
              <div className="text-primary small fw-semibold">▋</div>
            </div>
          </>
        )}

        {status === "done" && results && (
          <>
            <div className="mb-4">
              <span className="badge rounded-pill bg-success-subtle text-success border border-success-subtle mb-2">
                Analysis Complete
              </span>
              <h5 className="mb-0 fw-bold text-dark">Results Summary</h5>
            </div>

            <div className="row g-3 mb-4">
              {[
                { label: "Total Comments", value: results.total, cls: "text-primary" },
                { label: "Hate Speech", value: results.hate, cls: "text-danger" },
                { label: "Disinformation", value: results.disinfo, cls: "text-warning" },
                { label: "Normal", value: results.normal, cls: "text-success" },
              ].map((item) => (
                <div key={item.label} className="col-12 col-md-6">
                  <div className="rounded-4 border bg-light p-3 h-100">
                    <div className={`fs-3 fw-bold ${item.cls}`}>{item.value}</div>
                    <div className="small text-muted text-uppercase mb-2 fw-semibold">
                      {item.label}
                    </div>
                    <div className="progress mb-2" style={{ height: "6px" }}>
                      <div
                        className={`progress-bar ${
                          item.label === "Hate Speech"
                            ? "bg-danger"
                            : item.label === "Disinformation"
                            ? "bg-warning"
                            : item.label === "Normal"
                            ? "bg-success"
                            : "bg-primary"
                        }`}
                        role="progressbar"
                        style={{
                          width:
                            results.total > 0
                              ? `${((item.value / results.total) * 100).toFixed(0)}%`
                              : "0%",
                        }}
                      />
                    </div>
                    <div className={`small fw-semibold ${item.cls}`}>
                      {results.total > 0
                        ? ((item.value / results.total) * 100).toFixed(1)
                        : 0}
                      %
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="d-flex flex-wrap gap-2">
              <button
                type="button"
                className="btn btn-success"
                onClick={downloadCsv}
              >
                ⬇ Download CSV
              </button>

              <button
                type="button"
                className="btn btn-outline-secondary"
                onClick={reset}
              >
                ↺ Analyze Another
              </button>
            </div>
          </>
        )}

        {status === "error" && (
          <div className="text-center border border-danger-subtle bg-danger bg-opacity-10 rounded-4 p-4">
            <div className="fs-2 mb-2">⚠</div>
            <div className="text-danger mb-3 fw-semibold">
              {error || "Something went wrong."}
            </div>
            <button
              type="button"
              className="btn btn-outline-secondary"
              onClick={reset}
            >
              Try Again
            </button>
          </div>
        )}
      </div>
    </div>
  );
}