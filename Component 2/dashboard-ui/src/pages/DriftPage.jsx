import { useState } from "react";

import TriggerTimeline from "../components/TriggerTimeline.jsx";
import LatestTrigger from "../components/LatestTrigger.jsx";
import VariantGroups from "../components/VariantGroups.jsx";
import ManualMerge from "../components/ManualMerge.jsx";

import { addManualAlias, deleteManualAlias } from "../lib/api.js";

export default function DriftPage({
  triggers,
  latestTrigger,
  variantGroups,
  manualMap,
  checkedGroups,
  toggleGroupChecked,

  // refresh + errors
  onRefresh,
  err,
}) {
  // Trigger Timeline controls
  const [tlQuery, setTlQuery] = useState("");
  const [tlLimit, setTlLimit] = useState(10);
  const [tlExpanded, setTlExpanded] = useState({});
  const [tlOnlyFlagged, setTlOnlyFlagged] = useState(false);

  // Variant Groups controls
  const [vgQuery, setVgQuery] = useState("");
  const [vgOnlyUnchecked, setVgOnlyUnchecked] = useState(false);
  const [vgPage, setVgPage] = useState(1);

  // Manual Merge inputs
  const [manualFrom, setManualFrom] = useState("");
  const [manualTo, setManualTo] = useState("");

  const toggleTlExpanded = (batchNo) => {
    setTlExpanded((prev) => ({ ...prev, [batchNo]: !prev[batchNo] }));
  };

  return (
    <div>
      <div className="d-flex align-items-center gap-3">
        <div>
          <h3 className="mb-0">Drift Details</h3>
          <div className="text-muted small">
            Triggers + review actions (votes, new terms, merges)
          </div>
        </div>

        <button className="btn btn-outline-primary btn-sm ms-auto" onClick={onRefresh}>
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

      {/* Trigger timeline */}
      <div className="row g-3 mt-2">
        <div className="col-12">
          <TriggerTimeline
            triggers={triggers}
            tlQuery={tlQuery}
            setTlQuery={setTlQuery}
            tlOnlyFlagged={tlOnlyFlagged}
            setTlOnlyFlagged={setTlOnlyFlagged}
            tlLimit={tlLimit}
            setTlLimit={setTlLimit}
            tlExpanded={tlExpanded}
            toggleTlExpanded={toggleTlExpanded}
          />
        </div>
      </div>

      {/* Latest Trigger */}
      <div className="row g-3 mt-0">
        <div className="col-12">
          <LatestTrigger latestTrigger={latestTrigger} />
        </div>
      </div>

      {/* Variant Groups */}
      <div className="row g-3 mt-0">
        <div className="col-12">
          <VariantGroups
            variantGroups={variantGroups}
            vgQuery={vgQuery}
            setVgQuery={setVgQuery}
            vgOnlyUnchecked={vgOnlyUnchecked}
            setVgOnlyUnchecked={setVgOnlyUnchecked}
            checkedGroups={checkedGroups}
            toggleGroupChecked={toggleGroupChecked}
            vgPage={vgPage}
            setVgPage={setVgPage}
          />
        </div>
      </div>

      {/* Manual Merge */}
      <div className="row g-3 mt-0">
        <div className="col-12">
          <ManualMerge
            manualFrom={manualFrom}
            setManualFrom={setManualFrom}
            manualTo={manualTo}
            setManualTo={setManualTo}
            manualMap={manualMap}
            onAdd={async () => {
              await addManualAlias(manualFrom, manualTo);
              setManualFrom("");
              setManualTo("");
              onRefresh();
            }}
            onRemove={async (term) => {
              await deleteManualAlias(term);
              onRefresh();
            }}
          />
        </div>
      </div>
    </div>
  );
}