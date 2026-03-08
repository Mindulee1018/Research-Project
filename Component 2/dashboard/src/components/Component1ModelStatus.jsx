import { useState } from "react";

const MODEL_STATS = {
  model:        "XLM-RoBERTa Base",
  version:      "v2 (Augmented)",
  hfRepo:       "Imaya2002/sinhala-hate-classifier-v2",
  tokenRepo:    "Imaya2002/sinhala-hate-word-detector",
  trainSamples: 1257,
  testSamples:  132,
  augmented:    300,
  kappa:        0.51,
  epochs:       5,
  batchSize:    16,
  maxLen:       128,
  accuracy:     0.77,
  macroF1:      0.74,
  classes: [
    { name: "HATE",    precision: 0.85, recall: 0.68, f1: 0.75, support: 84, color: "#ff4d4d" },
    { name: "DISINFO", precision: 0.67, recall: 0.62, f1: 0.65, support: 16, color: "#ffaa00" },
    { name: "NORMAL",  precision: 0.74, recall: 0.89, f1: 0.81, support: 89, color: "#00e5a0" },
  ],
  thresholds: [
    { label: "HATE Classify",    value: 0.65 },
    { label: "DISINFO Classify", value: 0.60 },
    { label: "HATE Token",       value: 0.55 },
  ],
  dataset: [
    { label: "HATE",    original: 194, augmented: 494 },
    { label: "DISINFO", original: 127, augmented: 127 },
    { label: "NORMAL",  original: 637, augmented: 636 },
  ],
};

export default function Component1ModelStatus({ onClose }) {
  const [tab, setTab] = useState("metrics");

  return (
    <div style={m.overlay} onClick={onClose}>
      <div style={m.modal} onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div style={m.modalHeader}>
          <div>
            <div style={m.modalBadge}>🧠 Model Status</div>
            <h2 style={m.modalTitle}>XLM-RoBERTa Evaluation</h2>
            <p style={m.modalSub}>{MODEL_STATS.hfRepo}</p>
          </div>
          <button style={m.closeBtn} onClick={onClose}>✕</button>
        </div>

        {/* Summary cards */}
        <div style={m.summaryRow}>
          {[
            { label: "Accuracy",  value: "77%",   color: "#00b8ff" },
            { label: "Macro F1",  value: "0.74",  color: "#00e5a0" },
            { label: "Train Set", value: "1,257", color: "#a78bfa" },
            { label: "Kappa",     value: "0.51",  color: "#ffaa00" },
          ].map(c => (
            <div key={c.label} style={m.sumCard}>
              <div style={{ ...m.sumVal, color: c.color }}>{c.value}</div>
              <div style={m.sumLbl}>{c.label}</div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div style={m.tabs}>
          {["metrics", "dataset", "config"].map(t => (
            <button key={t} style={{ ...m.tab, ...(tab === t ? m.tabOn : {}) }} onClick={() => setTab(t)}>
              {t === "metrics" ? "📊 Metrics" : t === "dataset" ? "📁 Dataset" : "⚙️ Config"}
            </button>
          ))}
        </div>

        {/* Tab: Metrics */}
        {tab === "metrics" && (
          <div style={m.tabContent}>
            <div style={m.sectionTitle}>Per-Class Performance</div>
            <div style={m.tableWrap}>
              <table style={m.table}>
                <thead>
                  <tr>
                    {["Class", "Precision", "Recall", "F1-Score", "Support"].map(h => (
                      <th key={h} style={m.th}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {MODEL_STATS.classes.map(c => (
                    <tr key={c.name}>
                      <td style={m.td}>
                        <span style={{ ...m.classBadge, color: c.color, borderColor: c.color + "44", background: c.color + "11" }}>
                          {c.name}
                        </span>
                      </td>
                      <td style={m.td}>{c.precision.toFixed(2)}</td>
                      <td style={m.td}>{c.recall.toFixed(2)}</td>
                      <td style={m.td}>
                        <div style={m.f1Wrap}>
                          <span style={{ color: c.color, fontWeight: 700 }}>{c.f1.toFixed(2)}</span>
                          <div style={m.f1Bar}>
                            <div style={{ width: `${c.f1 * 100}%`, height: "100%", background: c.color, borderRadius: "2px" }} />
                          </div>
                        </div>
                      </td>
                      <td style={m.td}>{c.support}</td>
                    </tr>
                  ))}
                  <tr style={m.totalRow}>
                    <td style={m.td}><strong>Macro Avg</strong></td>
                    <td style={m.td}>0.75</td>
                    <td style={m.td}>0.73</td>
                    <td style={m.td}><strong style={{ color: "#00e5a0" }}>0.74</strong></td>
                    <td style={m.td}>189</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div style={m.sectionTitle}>Confidence Thresholds</div>
            <div style={m.threshRow}>
              {MODEL_STATS.thresholds.map(t => (
                <div key={t.label} style={m.threshCard}>
                  <div style={m.threshVal}>{t.value}</div>
                  <div style={m.threshLbl}>{t.label}</div>
                </div>
              ))}
            </div>

            
          </div>
        )}

        {/* Tab: Dataset */}
        {tab === "dataset" && (
          <div style={m.tabContent}>
            <div style={m.sectionTitle}>Dataset Composition</div>
            <div style={m.tableWrap}>
              <table style={m.table}>
                <thead>
                  <tr>
                    {["Label", "Count", "Source"].map(h => (
                      <th key={h} style={m.th}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {MODEL_STATS.dataset.map((d) => (
                    <tr key={d.label}>
                      <td style={m.td}>
                        <span style={{
                          ...m.classBadge,
                          color: d.label === "HATE" ? "#ff4d4d" : d.label === "DISINFO" ? "#ffaa00" : "#00e5a0",
                          borderColor: (d.label === "HATE" ? "#ff4d4d" : d.label === "DISINFO" ? "#ffaa00" : "#00e5a0") + "44",
                          background:  (d.label === "HATE" ? "#ff4d4d" : d.label === "DISINFO" ? "#ffaa00" : "#00e5a0") + "11",
                        }}>{d.label}</span>
                      </td>
                      <td style={m.td}><strong style={{ color: "#00e5a0" }}>{d.augmented}</strong></td>
                      <td style={m.td}>{d.label === "HATE" ? "Youtube Comments" : "Youtube Comments"}</td>
                    </tr>
                  ))}
                  <tr style={m.totalRow}>
                    <td style={m.td}><strong>Total</strong></td>
                    <td style={m.td}><strong style={{ color: "#00e5a0" }}>1,257</strong></td>
                    <td style={m.td}>—</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div style={m.infoGrid}>
              {[
                { label: "Train Samples",  value: "1,257", icon: "🏋️" },
                { label: "Test Samples",   value: "132",   icon: "🧪" },
                { label: "Cohen's Kappa",  value: "0.51",  icon: "📐" },
                { label: "Annotators",     value: "2",     icon: "👥" },
                { label: "Hate Lexicon",   value: "287+",  icon: "📚" },
              ].map(i => (
                <div key={i.label} style={m.infoCard}>
                  <div style={m.infoIcon}>{i.icon}</div>
                  <div style={m.infoVal}>{i.value}</div>
                  <div style={m.infoLbl}>{i.label}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab: Config */}
        {tab === "config" && (
          <div style={m.tabContent}>
            <div style={m.sectionTitle}>Training Configuration</div>
            <div style={m.configGrid}>
              {[
                { label: "Base Model",    value: "xlm-roberta-base" },
                { label: "Epochs",        value: "5" },
                { label: "Batch Size",    value: "16" },
                { label: "Max Token Len", value: "128" },
                { label: "Warmup Steps",  value: "100" },
                { label: "Weight Decay",  value: "0.01" },
                { label: "Precision",     value: "FP16" },
                { label: "Optimizer",     value: "AdamW" },
                { label: "Platform",      value: "Colab T4 GPU" },
                { label: "Framework",     value: "HuggingFace 4.44.0" },
              ].map(c => (
                <div key={c.label} style={m.configCard}>
                  <div style={m.configLbl}>{c.label}</div>
                  <div style={m.configVal}>{c.value}</div>
                </div>
              ))}
            </div>

            <div style={m.sectionTitle}>Class Weights (Imbalance Handling)</div>
            <div style={m.weightsRow}>
              {[
                { label: "HATE",    weight: "0.85", color: "#ff4d4d" },
                { label: "DISINFO", weight: "3.30", color: "#ffaa00" },
                { label: "NORMAL",  weight: "0.66", color: "#00e5a0" },
              ].map(w => (
                <div key={w.label} style={m.weightCard}>
                  <div style={{ ...m.weightVal, color: w.color }}>{w.weight}</div>
                  <div style={m.weightLbl}>{w.label}</div>
                </div>
              ))}
            </div>

            <div style={m.repoBox}>
              <div style={m.sectionTitle}>HuggingFace Repositories</div>
              <div style={m.repoItem}>
                <span style={m.repoIcon}>🤖</span>
                <div>
                  <div style={m.repoType}>Classifier (PyTorch)</div>
                  <div style={m.repoName}>{MODEL_STATS.hfRepo}</div>
                </div>
              </div>
              <div style={{ ...m.repoItem, borderBottom: "none" }}>
                <span style={m.repoIcon}>🏷️</span>
                <div>
                  <div style={m.repoType}>Token Classifier (ONNX)</div>
                  <div style={m.repoName}>{MODEL_STATS.tokenRepo}</div>
                </div>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

const m = {
  overlay:        { position: "fixed", inset: 0, background: "#000000cc", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center", padding: "20px" },
  modal:          { background: "#10101e", border: "1px solid #2a2a3a", borderRadius: "20px", width: "100%", maxWidth: "720px", maxHeight: "85vh", overflowY: "auto", fontFamily: "'DM Mono','Fira Code',monospace" },
  modalHeader:    { display: "flex", justifyContent: "space-between", alignItems: "flex-start", padding: "28px 28px 0", marginBottom: "20px" },
  modalBadge:     { display: "inline-block", padding: "3px 10px", border: "1px solid #a78bfa44", borderRadius: "20px", fontSize: "11px", color: "#a78bfa", marginBottom: "8px" },
  modalTitle:     { fontSize: "22px", fontWeight: "700", color: "#ffffff", margin: "0 0 4px" },
  modalSub:       { fontSize: "11px", color: "#404060", margin: 0 },
  closeBtn:       { background: "transparent", border: "1px solid #2a2a3a", borderRadius: "8px", color: "#606080", fontSize: "16px", cursor: "pointer", padding: "6px 12px", fontFamily: "inherit" },
  summaryRow:     { display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "12px", padding: "0 28px 20px" },
  sumCard:        { background: "#0a0a12", border: "1px solid #1e1e30", borderRadius: "10px", padding: "14px", textAlign: "center" },
  sumVal:         { fontSize: "24px", fontWeight: "700", marginBottom: "4px" },
  sumLbl:         { fontSize: "10px", color: "#606080", letterSpacing: "1px", textTransform: "uppercase" },
  tabs:           { display: "flex", gap: "4px", padding: "0 28px", marginBottom: "4px", borderBottom: "1px solid #1e1e30" },
  tab:            { padding: "10px 16px", background: "transparent", border: "none", color: "#606080", fontSize: "12px", cursor: "pointer", fontFamily: "inherit", borderBottom: "2px solid transparent", marginBottom: "-1px" },
  tabOn:          { color: "#a78bfa", borderBottom: "2px solid #a78bfa" },
  tabContent:     { padding: "20px 28px 28px" },
  sectionTitle:   { fontSize: "11px", letterSpacing: "2px", color: "#606080", textTransform: "uppercase", marginBottom: "12px", marginTop: "20px" },
  tableWrap:      { overflowX: "auto", marginBottom: "8px" },
  table:          { width: "100%", borderCollapse: "collapse", fontSize: "13px" },
  th:             { padding: "10px 12px", textAlign: "left", fontSize: "10px", color: "#606080", letterSpacing: "1px", textTransform: "uppercase", borderBottom: "1px solid #1e1e30" },
  td:             { padding: "10px 12px", borderBottom: "1px solid #1e1e3044", color: "#c0c0d0" },
  totalRow:       { background: "#0a0a1288" },
  classBadge:     { padding: "3px 10px", borderRadius: "20px", border: "1px solid", fontSize: "11px", fontWeight: "600", letterSpacing: "1px" },
  f1Wrap:         { display: "flex", alignItems: "center", gap: "8px" },
  f1Bar:          { flex: 1, height: "4px", background: "#1e1e30", borderRadius: "2px", overflow: "hidden" },
  threshRow:      { display: "flex", gap: "12px", marginBottom: "8px" },
  threshCard:     { flex: 1, background: "#0a0a12", border: "1px solid #1e1e30", borderRadius: "10px", padding: "14px", textAlign: "center" },
  threshVal:      { fontSize: "22px", fontWeight: "700", color: "#00b8ff", marginBottom: "4px" },
  threshLbl:      { fontSize: "10px", color: "#606080", letterSpacing: "1px" },
  improvementBox: { background: "#0a0a12", border: "1px solid #1e1e30", borderRadius: "12px", padding: "16px", marginTop: "16px" },
  impTitle:       { fontSize: "12px", color: "#a0a0c0", marginBottom: "12px", fontWeight: "600" },
  impGrid:        { display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: "10px" },
  impCard:        { background: "#10101e", borderRadius: "8px", padding: "12px" },
  impLabel:       { fontSize: "10px", color: "#606080", letterSpacing: "1px", marginBottom: "6px", textTransform: "uppercase" },
  impRow:         { display: "flex", alignItems: "center", gap: "8px" },
  impBefore:      { fontSize: "14px", color: "#404060" },
  impArrow:       { color: "#606080", fontSize: "12px" },
  impAfter:       { fontSize: "18px", fontWeight: "700" },
  infoGrid:       { display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: "10px", marginTop: "16px" },
  infoCard:       { background: "#0a0a12", border: "1px solid #1e1e30", borderRadius: "10px", padding: "14px", textAlign: "center" },
  infoIcon:       { fontSize: "20px", marginBottom: "6px" },
  infoVal:        { fontSize: "18px", fontWeight: "700", color: "#a78bfa", marginBottom: "4px" },
  infoLbl:        { fontSize: "10px", color: "#606080", letterSpacing: "1px" },
  configGrid:     { display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: "8px", marginBottom: "8px" },
  configCard:     { background: "#0a0a12", border: "1px solid #1e1e30", borderRadius: "8px", padding: "12px", display: "flex", justifyContent: "space-between", alignItems: "center" },
  configLbl:      { fontSize: "11px", color: "#606080" },
  configVal:      { fontSize: "12px", color: "#a78bfa", fontWeight: "600" },
  weightsRow:     { display: "flex", gap: "12px", marginBottom: "16px" },
  weightCard:     { flex: 1, background: "#0a0a12", border: "1px solid #1e1e30", borderRadius: "10px", padding: "14px", textAlign: "center" },
  weightVal:      { fontSize: "24px", fontWeight: "700", marginBottom: "4px" },
  weightLbl:      { fontSize: "10px", color: "#606080", letterSpacing: "1px", textTransform: "uppercase" },
  repoBox:        { background: "#0a0a12", border: "1px solid #1e1e30", borderRadius: "12px", padding: "16px" },
  repoItem:       { display: "flex", alignItems: "center", gap: "12px", padding: "10px 0", borderBottom: "1px solid #1e1e3044" },
  repoIcon:       { fontSize: "20px" },
  repoType:       { fontSize: "10px", color: "#606080", letterSpacing: "1px", marginBottom: "2px" },
  repoName:       { fontSize: "12px", color: "#a78bfa" },
};