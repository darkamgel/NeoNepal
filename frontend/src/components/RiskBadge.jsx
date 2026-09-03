import { colorForLevel, RISK_LABELS } from "../riskLevels";

// Previously duplicated (same className, same style shape) in
// WatershedDetail.jsx and GlacierDetailPanel.jsx.
export default function RiskBadge({ level, score }) {
  return (
    <span className="risk-badge" style={{ background: colorForLevel(level) }}>
      {RISK_LABELS[level]}
      {score != null ? ` · ${score.toFixed(1)}/100` : ""}
    </span>
  );
}
