import { useEffect, useState } from "react";
import { GeoJSON, MapContainer } from "react-leaflet";
import { api } from "../api/client";
import { useAnalyzeGlacier } from "../hooks/useAnalyzeGlacier";
import OsmTileLayer from "./OsmTileLayer";
import RiskBadge from "./RiskBadge";

export default function GlacierDetailPanel({ glacierId, onClose, watchList }) {
  const [glacier, setGlacier] = useState(null);
  const [error, setError] = useState(null);
  const { risk, isAnalyzing, error: analyzeError, analyze } = useAnalyzeGlacier(glacierId);

  useEffect(() => {
    setGlacier(null);
    setError(null);
    api.getGlacier(glacierId).then(setGlacier).catch((e) => setError(e.message));
  }, [glacierId]);

  if (error) return <div className="detail-panel">Error: {error}</div>;
  if (!glacier) return <div className="detail-panel">Loading...</div>;

  const geometry = glacier.geometry_geojson ? JSON.parse(glacier.geometry_geojson) : null;
  const tracked = watchList?.isTracked(glacier.id);

  return (
    <div className="detail-panel">
      <div className="detail-panel-header">
        <h3>{glacier.name || "Unnamed glacier"}</h3>
        <button className="close-button" onClick={onClose}>
          ×
        </button>
      </div>

      <dl className="glacier-attrs">
        <dt>Area</dt>
        <dd>{glacier.area_km2 != null ? `${glacier.area_km2.toFixed(2)} km²` : "Not available"}</dd>
        <dt>Coordinates</dt>
        <dd>
          {glacier.lat.toFixed(4)}, {glacier.lon.toFixed(4)}
        </dd>
        <dt>OSM type</dt>
        <dd>
          {glacier.osm_type} · <a href={`https://www.openstreetmap.org/${glacier.osm_type}/${glacier.osm_id}`} target="_blank" rel="noreferrer">view on OSM</a>
        </dd>
        {glacier.wikipedia && (
          <>
            <dt>Wikipedia</dt>
            <dd>
              <a
                href={`https://en.wikipedia.org/wiki/${encodeURIComponent(glacier.wikipedia.split(":").pop())}`}
                target="_blank"
                rel="noreferrer"
              >
                {glacier.wikipedia}
              </a>
            </dd>
          </>
        )}
      </dl>

      {geometry ? (
        <div className="glacier-outline-map">
          <MapContainer center={[glacier.lat, glacier.lon]} zoom={12} style={{ height: "100%", width: "100%" }}>
            <OsmTileLayer />
            <GeoJSON data={geometry} style={{ color: "#1a5fb4", weight: 2, fillOpacity: 0.25 }} />
          </MapContainer>
        </div>
      ) : (
        <p className="muted small">
          No outline available — this glacier is mapped as a complex multi-part feature in
          OpenStreetMap without a simple usable shape.
        </p>
      )}

      {watchList && (
        <button
          className="secondary-button"
          onClick={() => (tracked ? watchList.untrack(glacier.id) : watchList.track(glacier))}
        >
          {tracked ? "Untrack this glacier" : "Track this glacier"}
        </button>
      )}

      <div className="analyze-section">
        <button className="primary-button" onClick={analyze} disabled={isAnalyzing}>
          {isAnalyzing ? "Analyzing (real satellite + weather fetch)..." : "Analyze risk"}
        </button>
        <p className="muted small">
          Computes a real, on-demand score from live satellite imagery and weather for this exact
          location.{" "}
          {tracked
            ? "Tracked — see the Tracked Glaciers tab for its accumulated history."
            : "Track this glacier to build a real history from repeated analyses."}{" "}
          No ground sensor coverage at this location.
        </p>

        {analyzeError && <div className="error-banner">Error: {analyzeError}</div>}

        {risk && (
          <div className="risk-result">
            <div className="detail-header">
              <RiskBadge level={risk.level} score={risk.score} />
            </div>
            <dl className="glacier-attrs">
              <dt>Terrain change</dt>
              <dd>{(risk.terrain_change_component * 100).toFixed(0)}%</dd>
              <dt>Lake/ice growth</dt>
              <dd>{(risk.lake_growth_component * 100).toFixed(0)}%</dd>
              <dt>Rainfall anomaly</dt>
              <dd>{(risk.rainfall_component * 100).toFixed(0)}%</dd>
              <dt>Ground sensors</dt>
              <dd className="muted">No coverage — score renormalized across the 3 available signals</dd>
              <dt>Observations on record</dt>
              <dd>
                {risk.observation_count}
                {risk.observation_count < 2 && " (first look — analyze again later for a real trend)"}
              </dd>
            </dl>
          </div>
        )}
      </div>
    </div>
  );
}
