import { colorForLevel } from "../riskLevels";

export default function AlertLog({ alerts }) {
  if (alerts.length === 0) {
    return <p className="muted">No alerts triggered yet.</p>;
  }
  return (
    <ul className="alert-log">
      {alerts.map((a) => (
        <li key={a.id} className="alert-item" style={{ borderLeftColor: colorForLevel(a.level) }}>
          <div className="alert-item-header">
            <span className="alert-level" style={{ color: colorForLevel(a.level) }}>
              {a.level.toUpperCase()}
            </span>
            <span className="alert-time">{new Date(a.triggered_at).toLocaleString()}</span>
          </div>
          <p>{a.message}</p>
        </li>
      ))}
    </ul>
  );
}
