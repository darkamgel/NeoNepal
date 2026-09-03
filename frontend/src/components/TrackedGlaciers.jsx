import TrackedGlacierCard from "./TrackedGlacierCard";

export default function TrackedGlaciers({ watchList }) {
  const { tracked, untrack } = watchList;

  return (
    <div className="tracked-glaciers">
      <h2>Tracked Glaciers</h2>
      <p className="muted">
        Real risk history builds here as you re-analyze a tracked glacier over time — each
        analysis records a genuine satellite observation, so revisiting later shows an actual
        trend instead of starting from zero. This list is saved in your browser, not shared with
        other viewers.
      </p>

      {tracked.length === 0 ? (
        <p className="muted">
          Nothing tracked yet — open the Glacier Directory, select a glacier, and click "Track
          this glacier."
        </p>
      ) : (
        <div className="tracked-grid">
          {tracked.map((g) => (
            <TrackedGlacierCard key={g.id} glacier={g} onUntrack={untrack} />
          ))}
        </div>
      )}
    </div>
  );
}
