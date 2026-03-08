import { useEffect, useState } from "react";
import { fetchStats, fetchTopRisk, fetchTopQueue, fetchTopCommunities } from "../../../../Component 4/disinfo-risk-ui/src/api";
import "../../../../Component 4/disinfo-risk-ui/src/App.css";
import NetworkGraph from "../components/NetworkGraph";

function Table({ title, columns, rows }) {
  return (
    <div className="card">
      <h2>{title}</h2>
      <div className="tableWrap">
        <table>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key}>{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} style={{ opacity: 0.7 }}>
                  No data
                </td>
              </tr>
            ) : (
              rows.map((r, idx) => (
                <tr key={idx}>
                  {columns.map((c) => (
                    <td key={c.key}>{r[c.key] ?? ""}</td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function App() {
  const [stats, setStats] = useState(null);
  const [riskRows, setRiskRows] = useState([]);
  const [queueRows, setQueueRows] = useState([]);
  const [commRows, setCommRows] = useState([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      setError("");
      const [s, r, q, c] = await Promise.all([
        fetchStats(),
        fetchTopRisk(20),
        fetchTopQueue(20),
        fetchTopCommunities(10),
      ]);
      setStats(s);
      setRiskRows(r);
      setQueueRows(q);
      setCommRows(c);
    } catch (e) {
      setError(e?.message || "Failed to load data");
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="page">
      <header className="header">
        <div>
          <h1>Monitoring Hate Disinformation Spreader Risk</h1>
          <p className="subtitle">
            Graph analytics + GraphSAGE risk + active-learning prioritization
          </p>
        </div>
        <button className="btn" onClick={load}>Refresh</button>
      </header>

      {error && (
        <div className="error">
          <b>Error:</b> {error}
          <div style={{ marginTop: 8, opacity: 0.8 }}>
            Ensure FastAPI is running and artifacts exist (run pipeline).
          </div>
        </div>
      )}

      <div className="statsRow">
        <div className="stat">
          <div className="statLabel">User nodes</div>
          <div className="statValue">{stats?.user_nodes ?? "-"}</div>
        </div>
        <div className="stat">
          <div className="statLabel">User edges</div>
          <div className="statValue">{stats?.user_edges ?? "-"}</div>
        </div>
        <div className="stat">
          <div className="statLabel">Communities</div>
          <div className="statValue">{stats?.communities ?? "-"}</div>
        </div>
        <div className="stat">
          <div className="statLabel">Comments</div>
          <div className="statValue">{stats?.comments ?? "-"}</div>
        </div>
      </div>

      <div className="grid">
        <Table
          title="Top Risk Users"
          columns={[
            { key: "user_id", label: "User" },
            { key: "risk_level", label: "Risk" },
            { key: "risk_score", label: "Risk Score" },
            { key: "influence_score", label: "Influence" },
            { key: "exposure_score", label: "Exposure" },
            { key: "gnn_risk_score", label: "GNN Risk" },
          ]}
          rows={riskRows}
        />

        <Table
          title="Moderator Priority Queue (Influence × Ambiguity)"
          columns={[
            { key: "user_id", label: "User" },
            { key: "priority_score", label: "Priority" },
            { key: "uncertainty", label: "Ambiguity" },
            { key: "influence_score", label: "Influence" },
            { key: "risk_score", label: "Risk Score" },
           // { key: "priority_reason", label: "Reason" },
          ]}
          rows={queueRows}
        />

        <Table
          title="Community Summary"
          columns={[
            { key: "community_id", label: "Community" },
            { key: "users", label: "Users" },
            { key: "mean_risk", label: "Mean Risk" },
            { key: "mean_influence", label: "Mean Influence" },
            { key: "mean_exposure", label: "Mean Exposure" },
          ]}
          rows={commRows}
        />

        <div className="card">
        <h2>Interaction Network</h2>
        <NetworkGraph />
      </div>
      <p style={{ fontSize: "13px", color: "#4b5563", marginTop: "-6px", marginBottom: "12px" }}>
    This graph represents the interaction network of users derived from shared engagement, temporal co-activity, and topic similarity. 
    Each node is a user, node size reflects the user’s overall risk score, and node color reflects risk level. 
    Edges indicate meaningful relationships between users in the network, allowing moderators to visually identify influential spreaders and tightly connected communities.
  </p>
      </div>
    </div>
  );
}