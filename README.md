# NeoNepal — Glacial Hazard Early Warning System

A prototype early-warning system for glacial hazards (GLOF-style lake
outbursts, glacier/slope instability, precipitation-triggered debris flows)
in Himalayan watersheds, built after the Aug 26, 2026 Rasuwa disaster.

Includes a working backtest against that event: replaying the model's
scoring logic over the weeks leading up to it shows a rising risk trend
that crosses the "high" alert threshold about 24 hours before the flood —
see the "Rasuwa Case Study" tab in the dashboard.

Risk scoring runs on **real data**: live Sentinel-2 satellite imagery
(Microsoft Planetary Computer, NDWI-based lake area — zero credentials
needed) and live rainfall (Open-Meteo), recomputed every 5 minutes. Ground
sensor readings are still simulated (no physical hardware deployed). You
can also search all ~3,300 glaciers OpenStreetMap has tagged for Nepal, not
just the actively risk-scored watersheds.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for how it's built and
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for what a real deployment
requires beyond this prototype.

## Running it

### Backend

```bash
cd backend
python3.11 -m venv .venv   # needs Python 3.10+ (uses `X | None` type syntax)
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

On first run this seeds the database (7 watersheds — the Rasuwa disaster
site plus 6 other real, named, documented high-risk glacial lakes across
Nepal — with illustrative Rasuwa history and a historical risk-score/alert
backfill using real Open-Meteo rainfall data), imports Nepal's ~3,300-entry
OpenStreetMap glacier inventory for search, and starts a background
scheduler that recomputes risk every 5 minutes using live satellite and
weather data. API docs: http://localhost:8000/docs

Set `SATELLITE_MODE=demo` to force the old synthetic random-walk satellite
data instead (useful offline; this is what tests use automatically).
Startup is resilient to either external data source being briefly
unreachable — it logs a warning and continues rather than crashing.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the printed local URL (default http://localhost:5173). If the backend
runs on a different host/port, set `VITE_API_BASE_URL` in a `.env` file in
`frontend/`. Use the sidebar search box to look up any glacier in Nepal by
name — selecting one flies the map to it.

### Tests

```bash
cd backend
pytest
```

Fully offline — satellite ingestion is forced to demo mode for the test
session (`tests/conftest.py`), so nothing depends on network access.

## Project layout

```
backend/app/
  models.py            SQLAlchemy models (Watershed, GlacialLake, RiskScore, Alert, Glacier, ...)
  seed_data.py          Seeds 7 real watersheds + illustrative Rasuwa history + backfill
  import_glaciers.py    One-time import of Nepal's OSM glacier inventory
  ingestion/             Satellite (live Sentinel-2 + demo fallback), weather (real), sensors (simulated)
  risk/scoring.py       Transparent weighted risk-scoring model
  risk/scheduler.py     Periodic recompute + manual trigger
  alerts/dispatch.py    Alert logging/dispatch
  api/                  FastAPI routes, including glacier search
frontend/src/
  components/           MapView, GlacierSearch, RiskChart, WatershedDetail, AlertLog, CaseStudy
docs/
  ARCHITECTURE.md       System design
  DEPLOYMENT.md         What real deployment requires (partnerships, hardware, cost)
```
