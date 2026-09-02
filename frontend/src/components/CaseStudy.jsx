import RiskChart from "./RiskChart";

const EVENT_DATE = "2026-08-26T00:00:00";

export default function CaseStudy({ watershed, riskHistory, alerts }) {
  if (!watershed) return <p className="muted">Loading case study...</p>;

  const historicalAlerts = alerts
    .filter((a) => new Date(a.triggered_at) <= new Date(EVENT_DATE))
    .sort((a, b) => new Date(a.triggered_at) - new Date(b.triggered_at));
  const firstAlert = historicalAlerts[0];
  const leadTimeHours = firstAlert
    ? Math.round((new Date(EVENT_DATE) - new Date(firstAlert.triggered_at)) / 36e5)
    : null;

  return (
    <div>
      <h2>Case study: Rasuwa, August 26 2026</h2>
      <p>
        A glacial collapse on Langtang Lirung triggered a debris avalanche and flash floods along
        a 72km stretch of the Trishuli River, killing over 1,000 people with almost no warning.
      </p>
      <p className="callout">
        <strong>Important:</strong> the satellite/sensor readings shown below for the months
        leading up to the event are <em>synthetic and illustrative</em> — a plausible trend, not
        the actual historical record. Only the rainfall series is real (Open-Meteo archive data
        for this location). A real backtest against actual archival Sentinel-2 imagery from that
        period is the next step for validating this model — see docs/DEPLOYMENT.md. (Live
        Sentinel-2 ingestion is now running going forward, from today onward — see the "Run
        cycle" button on the Live Dashboard tab — but that doesn't retroactively validate the
        trend shown here.)
      </p>

      {firstAlert ? (
        <div className="highlight-box">
          This model's replayed timeline would have flagged this watershed as{" "}
          <strong>{firstAlert.level.toUpperCase()}</strong> risk on{" "}
          <strong>{new Date(firstAlert.triggered_at).toLocaleDateString()}</strong> —{" "}
          <strong>{leadTimeHours} hours</strong> before the event — after already showing a
          steadily rising "moderate" signal for the preceding month.
        </div>
      ) : (
        <div className="highlight-box">
          This model's replayed timeline shows an elevated but sub-alert-threshold trend leading
          up to the event.
        </div>
      )}

      <RiskChart riskHistory={riskHistory} eventDate={EVENT_DATE} eventLabel="Flood, Aug 26" />
    </div>
  );
}
