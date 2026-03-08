import { useEffect, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { fetchNetworkGraph } from "../../../../Component 4/disinfo-risk-ui/src/api"; // adjust path if needed

const riskColors = {
  HIGH: "#ef4444",
  MEDIUM: "#f59e0b",
  LOW: "#3b82f6",
};

export default function NetworkGraph() {
  const [graphData, setGraphData] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchNetworkGraph(25, 3);
        setGraphData(data);
      } catch (err) {
        console.error("Failed to load network graph:", err);
      }
    }
    load();
  }, []);

  if (!graphData) return <div>Loading graph...</div>;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 300px",
        gap: "12px",
        alignItems: "start",
      }}
    >
      <div
        style={{
          height: 560,
          background: "#ffffff",
          border: "1px solid #d1d5db",
          borderRadius: "12px",
          overflow: "hidden",
          padding: "8px",
        }}
      >
        <div style={{ display: "flex", gap: "18px", padding: "6px 8px 10px", fontSize: "13px", color: "#111827" }}>
          <div><span style={{ display: "inline-block", width: 12, height: 12, background: "#ef4444", borderRadius: "50%", marginRight: 6 }}></span>High Risk</div>
          <div><span style={{ display: "inline-block", width: 12, height: 12, background: "#f59e0b", borderRadius: "50%", marginRight: 6 }}></span>Medium Risk</div>
          <div><span style={{ display: "inline-block", width: 12, height: 12, background: "#3b82f6", borderRadius: "50%", marginRight: 6 }}></span>Low Risk</div>
        </div>

        <ForceGraph2D
          graphData={graphData}
          backgroundColor="#ffffff"
          nodeLabel={(node) =>
            `${node.id}
Risk: ${node.risk_level}
Score: ${Number(node.risk_score).toFixed(3)}
Community: ${node.community}`
          }
          nodeCanvasObject={(node, ctx) => {
            const color = riskColors[node.risk_level] || "#3b82f6";
            const size = Math.max(4, node.risk_score * 28);

            ctx.beginPath();
            ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
            ctx.fillStyle = color;
            ctx.fill();

            ctx.lineWidth = selectedNode?.id === node.id ? 3 : 1;
            ctx.strokeStyle = selectedNode?.id === node.id ? "#111827" : "#ffffff";
            ctx.stroke();
          }}
          linkColor={() => "rgba(148, 163, 184, 0.25)"}
          linkWidth={(link) => Math.max(0.5, Math.min(1.8, (link.weight || 1) * 0.25))}
          cooldownTicks={150}
          d3AlphaDecay={0.025}
          d3VelocityDecay={0.4}
          onNodeClick={(node) => setSelectedNode(node)}
        />
      </div>

      <div
        style={{
          background: "#ffffff",
          border: "1px solid #d1d5db",
          borderRadius: "12px",
          padding: "14px",
          minHeight: "200px",
        }}
      >
        <h3 style={{ marginTop: 0, fontSize: "15px", color: "#111827" }}>User Details</h3>

        {selectedNode ? (
          <div style={{ fontSize: "13px", color: "#374151", lineHeight: 1.6 }}>
            <div><b>User:</b> {selectedNode.id}</div>
            <div><b>Risk Level:</b> {selectedNode.risk_level}</div>
            <div><b>Risk Score:</b> {Number(selectedNode.risk_score).toFixed(3)}</div>
            <div><b>Influence Score:</b> {Number(selectedNode.influence_score).toFixed(3)}</div>
            <div><b>Exposure Score:</b> {Number(selectedNode.exposure_score).toFixed(3)}</div>
            <div><b>GNN Risk Score:</b> {Number(selectedNode.gnn_risk_score).toFixed(3)}</div>
            <div><b>Community:</b> {selectedNode.community}</div>
          </div>
        ) : (
          <div style={{ fontSize: "13px", color: "#6b7280" }}>
            Click a node to inspect the user’s network risk profile.
          </div>
        )}
      </div>
    </div>
  );
}