export const RISK_COLORS = {
  low: "#2e7d46",
  moderate: "#c98a12",
  high: "#d9622b",
  critical: "#c1272d",
};

export const RISK_LABELS = {
  low: "Low",
  moderate: "Moderate",
  high: "High",
  critical: "Critical",
};

export function colorForLevel(level) {
  return RISK_COLORS[level] || "#6b7280";
}
