import { useMemo } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export default function LexiconTop({ lexTop, query, setQuery }) {
  const filteredLex = useMemo(() => {
    const q = query.trim();
    if (!q) return lexTop || [];
    return (lexTop || []).filter((x) => String(x.term).includes(q));
  }, [query, lexTop]);

  const chartData = useMemo(() => {
    return filteredLex.slice(0, 20).map((x) => ({
      term: x.term,
      weight: Number(x.weight || 0),
    }));
  }, [filteredLex]);

  return (
    <div className="card shadow-sm h-100">
      <div className="card-body">
        <div className="fw-bold mb-2">Top Terms by Weight (Lexicon)</div>

        <input
          className="form-control form-control-sm mb-2"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search Sinhala term…"
        />

        <div style={{ width: "100%", height: 280 }}>
          <ResponsiveContainer>
            <BarChart data={chartData}>
              <XAxis dataKey="term" hide />
              <YAxis />
              <Tooltip />
              <Bar dataKey="weight" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="text-muted small mt-2">
          Weight ≈ P(Hate|term) with smoothing. Showing top 20 matches.
        </div>
      </div>
    </div>
  );
}