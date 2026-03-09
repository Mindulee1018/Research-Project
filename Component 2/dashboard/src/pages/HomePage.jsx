import KPI from "../components/KPI.jsx";
import StatusCard from "../components/StatusCard.jsx";
import DriftChart from "../components/DriftChart.jsx";
import Component1PipelineCard from "../components/Component1PipelineCard.jsx";
import RunDriftButton from "../components/RunDriftButton.jsx";
import ModerationStatsChart from "../components/ModerationStatsChart.jsx";

export default function HomePage({
  metrics,
  action,
  statusColor,
  thresholds,
  driftChartData,
  onRefresh,
  err,
  moderationStats
}) {
  return (
    <div>
      {/* Header */}
      <div className="d-flex align-items-center gap-3">
        <div>
          <h3 className="mb-0">Home</h3>
          <div className="text-muted small">
            Summary (KPI + Model status + Drift overview)
          </div>
        </div>

        <button
          className="btn btn-outline-primary btn-sm ms-auto"
          onClick={onRefresh}
        >
          Refresh
        </button>
      </div>

      {err && (
        <div className="alert alert-danger mt-3 mb-0 py-2">
          <div className="small" style={{ whiteSpace: "pre-wrap" }}>
            {err}
          </div>
        </div>
      )}

      <div className="row g-3 mt-0">
        <div className="col-12">
          <Component1PipelineCard />
        </div>
      </div>

      <div className="row g-3 mt-3">
        <div className="col-12">
          <RunDriftButton />
        </div>
      </div>

      {/* KPI row */}
      <div className="row g-3 mt-2">
        <div className="col-12 col-md-6 col-lg-3">
          <KPI
            title="Latest Batch"
            value={metrics?.latest_batch}
            hint="Most recent processed batch"
          />
        </div>
        <div className="col-12 col-md-6 col-lg-3">
          <KPI
            title="Batches Seen"
            value={metrics?.batches_seen}
            hint="Total batches in history"
            accent="#16a34a"
          />
        </div>
        <div className="col-12 col-md-6 col-lg-3">
          <KPI
            title="Trigger Events"
            value={metrics?.trigger_count}
            hint="Batches requiring review"
            accent="#ef4444"
          />
        </div>
        <div className="col-12 col-md-6 col-lg-3">
          <KPI
            title="Lexicon Size"
            value={metrics?.lexicon_size}
            hint="Unique terms tracked"
            accent="#f59e0b"
          />
        </div>
      </div>

      {/* Status + Drift */}
      <div className="row g-3 mt-0">
        <div className="col-12 col-lg-5">
          <StatusCard
            actionTitle={action.title}
            actionSteps={action.steps}
            statusColor={statusColor}
          />
        </div>

        <div className="col-12 col-lg-7">
          <DriftChart data={driftChartData} thresholds={thresholds} />
        </div>

        <div className="mt-4">
          <ModerationStatsChart stats={moderationStats} />
        </div>
      </div>
    </div>
  );
}