import ModerationStatsChart from "../ui/ModerationStatsChart.jsx";

export default function Statistics({ posts, goHome }) {
  return (
    <div style={{ background: "#f0f2f5", minHeight: "100vh", padding: "30px" }}>
      
      <div style={{ marginBottom: 20 }}>
        <button
          onClick={goHome}
          style={{
            background: "#1877f2",
            color: "white",
            border: "none",
            padding: "8px 16px",
            borderRadius: "8px",
            fontWeight: "bold",
            cursor: "pointer"
          }}
        >
          ← Back to Feed
        </button>
      </div>

      <h2 style={{ marginBottom: 20 }}>
        Moderation Statistics Dashboard
      </h2>

      <ModerationStatsChart posts={posts} />

    </div>
  );
}