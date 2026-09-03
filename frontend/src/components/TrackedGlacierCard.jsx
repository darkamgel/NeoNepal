import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAnalyzeGlacier } from "../hooks/useAnalyzeGlacier";
import RiskBadge from "./RiskBadge";
import RiskChart from "./RiskChart";

export default function TrackedGlacierCard({ glacier, onUntrack }) {
  const [history, setHistory] = useState([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const { risk, isAnalyzing, error, analyze } = useAnalyzeGlacier(glacier.id);

  async function refreshHistory() {
    setIsLoadingHistory(true);
    try {
      setHistory(await api.getGlacierRiskHistory(glacier.id));
    } finally {
      setIsLoadingHistory(false);
    }
  }

  useEffect(() => {
    refreshHistory();
  }, [glacier.id]);

  async function handleAnalyze() {
    const result = await analyze();
    if (result) refreshHistory();
  }

  const latest = risk || history[history.length - 1];

  return (
    <div className="tracked-card">
      <div className="detail-header">
        <div>
          <h3>{glacier.name || "Unnamed glacier"}</h3>
          <p className="muted small">
            {glacier.lat.toFixed(4)}, {glacier.lon.toFixed(4)}
          </p>
        </div>
        {latest && <RiskBadge level={latest.level} score={latest.score} />}
      </div>

      <div className="tracked-card-actions">
        <button className="primary-button" onClick={handleAnalyze} disabled={isAnalyzing}>
          {isAnalyzing ? "Analyzing..." : "Analyze now"}
        </button>
        <button className="secondary-button" onClick={() => onUntrack(glacier.id)}>
          Untrack
        </button>
      </div>

      {error && <div className="error-banner">Error: {error}</div>}

      {isLoadingHistory ? (
        <p className="muted small">Loading history...</p>
      ) : history.length > 0 ? (
        <RiskChart riskHistory={history} showSensor={false} />
      ) : (
        <p className="muted small">
          No observations yet — click "Analyze now" to record the first one.
        </p>
      )}
    </div>
  );
}
