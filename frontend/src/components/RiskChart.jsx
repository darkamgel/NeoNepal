import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function RiskChart({ riskHistory, eventDate, eventLabel }) {
  const data = riskHistory.map((r) => ({
    date: r.computed_at,
    label: formatDate(r.computed_at),
    score: r.score,
    terrain: r.terrain_change_component * 100,
    rainfall: r.rainfall_component * 100,
    sensor: r.sensor_component * 100,
  }));

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
        <XAxis dataKey="label" stroke="var(--chart-axis)" tick={{ fontSize: 12 }} />
        <YAxis domain={[0, 100]} stroke="var(--chart-axis)" tick={{ fontSize: 12 }} />
        <Tooltip
          contentStyle={{ background: "var(--card-bg)", border: "1px solid var(--border)" }}
        />
        <Legend />
        <ReferenceLine y={50} stroke="#d9622b" strokeDasharray="4 4" label="High threshold" />
        <ReferenceLine y={75} stroke="#c1272d" strokeDasharray="4 4" label="Critical threshold" />
        {eventDate && (
          <ReferenceLine
            x={formatDate(eventDate)}
            stroke="#c1272d"
            strokeWidth={2}
            label={{ value: eventLabel || "Event", position: "insideTopRight", fill: "#c1272d" }}
          />
        )}
        <Line type="monotone" dataKey="score" name="Composite risk score" stroke="#1a5fb4" strokeWidth={2.5} dot={false} />
        <Line type="monotone" dataKey="terrain" name="Terrain change" stroke="#8a5cf5" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
        <Line type="monotone" dataKey="rainfall" name="Rainfall anomaly" stroke="#2e9bd6" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
        <Line type="monotone" dataKey="sensor" name="Sensor signal" stroke="#e08a2b" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
      </LineChart>
    </ResponsiveContainer>
  );
}
