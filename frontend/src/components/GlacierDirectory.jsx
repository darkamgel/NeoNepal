import { useEffect, useState } from "react";
import { api } from "../api/client";
import GlacierDetailPanel from "./GlacierDetailPanel";
import TopGlaciersChart from "./TopGlaciersChart";

const PAGE_SIZE = 25;

export default function GlacierDirectory() {
  const [stats, setStats] = useState(null);
  const [glaciers, setGlaciers] = useState([]);
  const [sort, setSort] = useState("area_desc");
  const [page, setPage] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    api.getGlacierStats().then(setStats).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    setIsLoading(true);
    const request = searchQuery.trim()
      ? api.searchGlaciers(searchQuery.trim(), PAGE_SIZE)
      : api.listGlaciers({ sort, limit: PAGE_SIZE, offset: page * PAGE_SIZE });
    request
      .then(setGlaciers)
      .catch((e) => setError(e.message))
      .finally(() => setIsLoading(false));
  }, [sort, page, searchQuery]);

  function handleSearchChange(value) {
    setSearchQuery(value);
    setPage(0);
  }

  return (
    <div className="glacier-directory">
      <h2>Nepal Glacier Directory</h2>
      <p className="muted">
        Every glacier OpenStreetMap has mapped for Nepal — real coordinates and, where the
        underlying shape is available, a computed area (see <code>docs/ARCHITECTURE.md</code> for
        how the area figures are computed and their limits).
      </p>

      {error && <div className="error-banner">Error: {error}</div>}

      {stats && (
        <div className="stat-cards">
          <div className="stat-card">
            <div className="stat-value">{stats.total_count.toLocaleString()}</div>
            <div className="stat-label">Total glaciers</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.named_count.toLocaleString()}</div>
            <div className="stat-label">Named</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.total_area_km2.toLocaleString()} km²</div>
            <div className="stat-label">Total computed ice area</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.with_area_count.toLocaleString()}</div>
            <div className="stat-label">With computed area</div>
          </div>
        </div>
      )}

      {stats && (
        <>
          <h3>Largest glaciers by area</h3>
          <TopGlaciersChart glaciers={stats.largest} />
        </>
      )}

      <h3>Browse all glaciers</h3>
      <div className="directory-controls">
        <input
          type="text"
          placeholder="Search by name..."
          value={searchQuery}
          onChange={(e) => handleSearchChange(e.target.value)}
        />
        <select value={sort} onChange={(e) => setSort(e.target.value)} disabled={!!searchQuery}>
          <option value="area_desc">Largest first</option>
          <option value="name">Name (A-Z)</option>
        </select>
      </div>

      <div className="directory-layout">
        <table className="glacier-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Area (km²)</th>
              <th>Coordinates</th>
            </tr>
          </thead>
          <tbody>
            {glaciers.map((g) => (
              <tr key={g.id} onClick={() => setSelectedId(g.id)} className={selectedId === g.id ? "selected" : ""}>
                <td>{g.name || <span className="muted">Unnamed</span>}</td>
                <td>{g.area_km2 != null ? g.area_km2.toFixed(2) : "—"}</td>
                <td className="muted">
                  {g.lat.toFixed(3)}, {g.lon.toFixed(3)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {selectedId && (
          <GlacierDetailPanel glacierId={selectedId} onClose={() => setSelectedId(null)} />
        )}
      </div>

      {!searchQuery && (
        <div className="pagination">
          <button disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
            Previous
          </button>
          <span className="muted small">Page {page + 1}</span>
          <button disabled={isLoading || glaciers.length < PAGE_SIZE} onClick={() => setPage((p) => p + 1)}>
            Next
          </button>
        </div>
      )}
    </div>
  );
}
