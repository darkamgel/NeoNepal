import { TileLayer } from "react-leaflet";

// The OSM tile URL + attribution was previously copy-pasted identically
// into both MapView.jsx and GlacierDetailPanel.jsx.
export default function OsmTileLayer() {
  return (
    <TileLayer
      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    />
  );
}
