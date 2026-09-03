import RiskBadge from "./RiskBadge";
import RiskChart from "./RiskChart";

export default function WatershedDetail({ watershed, riskHistory, onRunCycle, isRunningCycle }) {
  if (!watershed) return <p className="muted">Select a watershed on the map.</p>;

  const level = watershed.latest_risk?.level || "low";

  return (
    <div>
      <div className="detail-header">
        <div>
          <h2>{watershed.name}</h2>
          <p className="muted">{watershed.district}</p>
        </div>
        <RiskBadge level={level} score={watershed.latest_risk?.score} />
      </div>
      <p>{watershed.description}</p>

      <button onClick={onRunCycle} disabled={isRunningCycle} className="primary-button">
        {isRunningCycle ? "Running cycle..." : "Run risk-recompute cycle now"}
      </button>
      <p className="muted small">
        Checks for newer real Sentinel-2 imagery and live rainfall, then recomputes risk —
        normally runs automatically every 5 minutes. Ground sensor readings are still simulated.
        New satellite imagery usually only arrives every few days, so most checks will find no
        change in the satellite component.
      </p>

      {riskHistory.length > 0 ? (
        <RiskChart riskHistory={riskHistory} />
      ) : (
        <p className="muted">No risk history yet — run a cycle to generate the first score.</p>
      )}
    </div>
  );
}
