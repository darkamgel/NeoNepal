import { CircleMarker, MapContainer, Marker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { colorForLevel, RISK_LABELS } from "../riskLevels";
import OsmTileLayer from "./OsmTileLayer";

const NEPAL_CENTER = [28.0, 85.8];

const searchedGlacierIcon = L.divIcon({
  className: "searched-glacier-icon",
  html: '<div class="searched-glacier-dot"></div>',
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

export default function MapView({ watersheds, selectedId, onSelect, searchedGlacier, mapRef }) {
  return (
    <MapContainer center={NEPAL_CENTER} zoom={8} style={{ height: "100%", width: "100%" }} ref={mapRef}>
      <OsmTileLayer />
      {watersheds.map((w) => {
        const level = w.latest_risk?.level || "low";
        const isSelected = w.id === selectedId;
        return (
          <CircleMarker
            key={w.id}
            center={[w.centroid_lat, w.centroid_lon]}
            radius={isSelected ? 16 : 12}
            pathOptions={{
              color: isSelected ? "#1a1a1a" : colorForLevel(level),
              weight: isSelected ? 3 : 2,
              fillColor: colorForLevel(level),
              fillOpacity: 0.75,
            }}
            eventHandlers={{ click: () => onSelect(w.id) }}
          >
            <Popup>
              <strong>{w.name}</strong>
              <br />
              {w.district}
              <br />
              Risk: {RISK_LABELS[level]}
              {w.latest_risk ? ` (${w.latest_risk.score.toFixed(1)}/100)` : " (not yet scored)"}
            </Popup>
          </CircleMarker>
        );
      })}
      {searchedGlacier && (
        <Marker position={[searchedGlacier.lat, searchedGlacier.lon]} icon={searchedGlacierIcon}>
          <Popup>
            <strong>{searchedGlacier.name}</strong>
            <br />
            Not part of the actively risk-monitored set.
          </Popup>
        </Marker>
      )}
    </MapContainer>
  );
}
