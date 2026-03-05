const API = "http://127.0.0.1:8000/api";

export async function fetchJSON(url) {
  const r = await fetch(url);
  const ct = r.headers.get("content-type") || "";
  const text = await r.text();

  if (!r.ok) {
    throw new Error(`HTTP ${r.status} for ${url}\n${text.slice(0, 180)}`);
  }
  if (!ct.includes("application/json")) {
    throw new Error(
      `Expected JSON but got ${ct || "unknown content-type"} from ${url}\n` +
        `This usually means proxy/route issue. First bytes: ${text.slice(0, 30)}`,
    );
  }
  return JSON.parse(text);
}

export async function addManualAlias(from, to) {
  await fetch(`${API}/manual_aliases`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ from, to }),
  });
}

export async function deleteManualAlias(term) {
  await fetch(`${API}/manual_aliases?term=${encodeURIComponent(term)}`, {
    method: "DELETE",
  });
}

export async function loadDashboardData() {
  const [metrics, drift, triggers, lexTop, variantGroups, manualMap] =
    await Promise.all([
      fetchJSON(`${API}/metrics`),
      fetchJSON(`${API}/drift_history`),
      fetchJSON(`${API}/triggers`),
      fetchJSON(`${API}/lexicon_top?limit=200`),
      fetchJSON(`${API}/variant_groups?min_variants=1`),
      fetchJSON(`${API}/manual_aliases`),
    ]);

  return { metrics, drift, triggers, lexTop, variantGroups, manualMap };
}