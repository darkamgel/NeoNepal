import { useEffect, useRef, useState } from "react";
import "./App.css";
import { api } from "./api/client";
import { useWatchList } from "./hooks/useWatchList";
import AlertLog from "./components/AlertLog";
import CaseStudy from "./components/CaseStudy";
import GlacierDirectory from "./components/GlacierDirectory";
import GlacierSearch from "./components/GlacierSearch";
import MapView from "./components/MapView";
import TrackedGlaciers from "./components/TrackedGlaciers";
import WatershedDetail from "./components/WatershedDetail";

export default function App() {
  const watchList = useWatchList();
  const [watersheds, setWatersheds] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [riskHistory, setRiskHistory] = useState([]);
  const [rasuwaHistory, setRasuwaHistory] = useState([]);
  const [tab, setTab] = useState("dashboard");
  const [isRunningCycle, setIsRunningCycle] = useState(false);
  const [error, setError] = useState(null);
  const [searchedGlacier, setSearchedGlacier] = useState(null);
  const mapRef = useRef(null);

  function handleSelectGlacier(glacier) {
    setSearchedGlacier(glacier);
    mapRef.current?.flyTo([glacier.lat, glacier.lon], 12, { duration: 1 });
  }

  async function refreshWatershedsAndAlerts() {
    try {
      const [w, a] = await Promise.all([api.listWatersheds(), api.listAlerts()]);
      setWatersheds(w);
      setAlerts(a);
      setError(null);
      if (selectedId === null && w.length > 0) {
        setSelectedId(w[0].id);
      }
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    refreshWatershedsAndAlerts();
  }, []);

  useEffect(() => {
    if (selectedId === null) return;
    api.getRiskHistory(selectedId).then(setRiskHistory).catch((e) => setError(e.message));
  }, [selectedId]);

  async function handleRunCycle() {
    setIsRunningCycle(true);
    try {
      await api.triggerCycle();
      await refreshWatershedsAndAlerts();
      if (selectedId !== null) {
        setRiskHistory(await api.getRiskHistory(selectedId));
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setIsRunningCycle(false);
    }
  }

  const selectedWatershed = watersheds.find((w) => w.id === selectedId) || null;
  const rasuwa = watersheds.find((w) => w.name.includes("Rasuwa")) || null;
  const rasuwaAlerts = alerts.filter((a) => rasuwa && a.watershed_id === rasuwa.id);

  useEffect(() => {
    if (rasuwa) {
      api.getRiskHistory(rasuwa.id).then(setRasuwaHistory).catch((e) => setError(e.message));
    }
  }, [rasuwa?.id]);

  return (
    <div className="app">
      <header className="app-header">
        <h1>NeoNepal — Glacial Hazard Early Warning</h1>
        <nav className="tabs">
          <button className={tab === "dashboard" ? "active" : ""} onClick={() => setTab("dashboard")}>
            Live Dashboard
          </button>
          <button className={tab === "case-study" ? "active" : ""} onClick={() => setTab("case-study")}>
            Rasuwa Case Study
          </button>
          <button className={tab === "glaciers" ? "active" : ""} onClick={() => setTab("glaciers")}>
            Glacier Directory
          </button>
          <button className={tab === "tracked" ? "active" : ""} onClick={() => setTab("tracked")}>
            Tracked Glaciers
          </button>
        </nav>
      </header>

      {error && <div className="error-banner">Error: {error}</div>}

      {tab === "tracked" ? (
        <main className="glacier-directory-layout">
          <TrackedGlaciers watchList={watchList} />
        </main>
      ) : tab === "glaciers" ? (
        <main className="glacier-directory-layout">
          <GlacierDirectory watchList={watchList} />
        </main>
      ) : tab === "dashboard" ? (
        <main className="dashboard-layout">
          <div className="map-pane">
            <MapView
              watersheds={watersheds}
              selectedId={selectedId}
              onSelect={setSelectedId}
              searchedGlacier={searchedGlacier}
              mapRef={mapRef}
            />
          </div>
          <aside className="side-pane">
            <GlacierSearch onSelect={handleSelectGlacier} />
            <hr className="divider" />
            <WatershedDetail
              watershed={selectedWatershed}
              riskHistory={riskHistory}
              onRunCycle={handleRunCycle}
              isRunningCycle={isRunningCycle}
            />
            <h3>Alert log</h3>
            <AlertLog alerts={alerts} />
          </aside>
        </main>
      ) : (
        <main className="case-study-layout">
          <CaseStudy watershed={rasuwa} riskHistory={rasuwaHistory} alerts={rasuwaAlerts} />
        </main>
      )}
    </div>
  );
}
