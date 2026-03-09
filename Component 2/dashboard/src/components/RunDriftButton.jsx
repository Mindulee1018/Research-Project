import { useState } from "react";

const API_URL = "http://127.0.0.1:8001";

export default function RunDriftButton({ onDone }) {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [output, setOutput] = useState("");

  const handleRun = async () => {
    try {
      setLoading(true);
      setMessage("");
      setOutput("");

      const res = await fetch(`${API_URL}/api/run-main`, {
        method: "POST",
      });

      const data = await res.json();

      setMessage(data.message || "Done.");
      setOutput([data.stdout, data.stderr].filter(Boolean).join("\n"));

      // ✅ refresh dashboard after drift finishes
      if (onDone) {
        setTimeout(() => onDone(), 500);
      }

    } catch (err) {
      setMessage("Failed to run python -m src.main");
      setOutput(String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card border-0 shadow-sm h-100">
      <div className="card-body">
        <div className="d-flex align-items-start justify-content-between gap-3 flex-wrap">
          <div>
            <h5 className="mb-1">Run Drift Processing</h5>
            <div className="text-muted small"></div>
          </div>

          <button
            className="btn btn-primary"
            onClick={handleRun}
            disabled={loading}
          >
            {loading ? "Running..." : "Run Drift Now"}
          </button>
        </div>

        {message && (
          <div
            className={`alert mt-3 mb-0 py-2 ${
              message.toLowerCase().includes("failed")
                ? "alert-danger"
                : "alert-info"
            }`}
          >
            <div className="small">{message}</div>
          </div>
        )}

        {output && (
          <pre
            className="mt-3 p-3 bg-light border rounded small mb-0"
            style={{
              whiteSpace: "pre-wrap",
              maxHeight: "260px",
              overflowY: "auto",
            }}
          >
            {output}
          </pre>
        )}
      </div>
    </div>
  );
}