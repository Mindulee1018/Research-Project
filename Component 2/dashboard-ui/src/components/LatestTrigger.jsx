import Pill from "./Pill.jsx";

export default function LatestTrigger({ latestTrigger }) {
  return (
    <div className="card shadow-sm">
      <div className="card-body">
        <div className="fw-bold mb-2">Latest Trigger</div>

        {!latestTrigger ? (
          <div className="text-muted small">No triggers yet.</div>
        ) : (
          <>
            <div className="d-flex flex-wrap gap-2 mb-2">
              <Pill>Batch: {latestTrigger.batch_no}</Pill>
              <Pill>Vote count: {latestTrigger.vote_count}</Pill>
              <Pill>JSD: {latestTrigger.jsd ?? "-"}</Pill>
              <Pill>
                new_terms_in_hate: {latestTrigger.new_terms_in_hate ?? "-"}
              </Pill>
            </div>

            <div className="text-muted small mb-1">New terms:</div>
            <div className="border rounded p-2 small mb-3">
              {(latestTrigger.new_terms || []).length
                ? latestTrigger.new_terms.join(", ")
                : "None"}
            </div>

            <div className="text-muted small mb-1">Votes:</div>
            <pre className="border rounded p-2 small mb-0" style={{ overflow: "auto" }}>
              {JSON.stringify(latestTrigger.votes, null, 2)}
            </pre>
          </>
        )}
      </div>
    </div>
  );
}