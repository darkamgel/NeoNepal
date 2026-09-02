import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

// Single sequential hue (matches this app's existing --accent) — bar length
// already encodes rank/magnitude, so one flat color is correct here rather
// than a per-bar gradient.
const BAR_COLOR = "#1a5fb4";

function shortName(g) {
  const label = g.name || `Unnamed glacier`;
  return label.length > 28 ? label.slice(0, 26) + "…" : label;
}

function TooltipContent({ active, payload }) {
  if (!active || !payload?.length) return null;
  const g = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <strong>{g.name || "Unnamed glacier"}</strong>
      <div>{g.area_km2.toFixed(1)} km²</div>
    </div>
  );
}

export default function TopGlaciersChart({ glaciers }) {
  const data = glaciers.map((g) => ({ ...g, label: shortName(g) }));

  return (
    <ResponsiveContainer width="100%" height={340}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 40, left: 8, bottom: 4 }}>
        <XAxis type="number" stroke="var(--chart-axis)" tick={{ fontSize: 11 }} />
        <YAxis
          type="category"
          dataKey="label"
          width={150}
          stroke="var(--chart-axis)"
          tick={{ fontSize: 11 }}
        />
        <Tooltip content={<TooltipContent />} cursor={{ fill: "var(--bg)" }} />
        <Bar dataKey="area_km2" fill={BAR_COLOR} radius={[0, 4, 4, 0]} maxBarSize={22} />
      </BarChart>
    </ResponsiveContainer>
  );
}
