# Architecture

## Overview

```
Satellite imagery (Sentinel-2, via Planetary Computer, real) ─┐
Weather data (Open-Meteo API, real)                           ├─▶ Ingestion ─▶ Risk Scoring ─▶ DB ─▶ API ─▶ React Dashboard
Ground sensors (simulated; real = LoRaWAN IoT)                ─┘                                    └──▶ Alert Dispatch
                                                                                                       │
Nepal glacier inventory (OpenStreetMap Overpass, real, ~3,300) ─▶ Glacier search/browse ──────────────┘
```

Backend: Python / FastAPI / SQLAlchemy (SQLite in this prototype).
Frontend: React (Vite) / Leaflet / Recharts.

## Data model (`backend/app/models.py`)

- **Watershed** — a monitored valley (e.g. Langtang-Trishuli / Rasuwa).
- **GlacialLake** — a lake or ice mass within a watershed, with a `hazard_type`
  (`glof`, `ice_avalanche`, `debris_flow`).
- **SatelliteObservation** — one derived measurement per lake per pass:
  surface area (m²) and a terrain-change index (0–1).
- **SensorReading** — one ground-sensor reading per watershed: water level,
  seismic activity.
- **RiskScore** — a computed composite score (0–100) with its four component
  values, timestamped.
- **Alert** — a dispatched alert record.
- **Glacier** — one entry from Nepal's full OpenStreetMap glacier inventory
  (~3,300 features), used for search/browse. Distinct from `GlacialLake`,
  which is the small, actively risk-scored subset with documented GLOF
  history.

## Ingestion layer (`backend/app/ingestion/`)

- **`satellite.py` — live by default (`SATELLITE_MODE=live`).** Pulls real
  Sentinel-2 L2A imagery from Microsoft's Planetary Computer: an anonymous
  STAC search finds the latest low-cloud scene near each lake, an anonymous
  SAS token signs read access, and `rasterio` does a small windowed read
  (~2km around the lake, not the full scene) to compute NDWI-based water
  fraction (→ `surface_area_m2`) and a brightness-shift terrain-change proxy.
  No account or API key needed at this scale. A scene is only reprocessed
  when the STAC search returns a `source_scene_id` different from the last
  one ingested for that lake — Sentinel-2 revisits any point roughly every
  5 days (less in monsoon cloud cover), so most 5-minute scheduler ticks
  correctly find nothing new and reuse the existing observation. Any
  failure (network, no scene found, read error) falls back to the demo
  random-walk step for that tick so the scheduler never breaks.
  `SATELLITE_MODE=demo` forces the old synthetic random-walk behavior
  offline; tests force this via an autouse fixture (`tests/conftest.py`).
- **`sensors.py`** — still simulated; no ground hardware exists yet (see
  `DEPLOYMENT.md`).
- **`weather.py`** — real in all modes: Open-Meteo's free, keyless forecast
  and archive APIs, which is why the rainfall component in the Rasuwa case
  study is genuine, not simulated.
- **`import_glaciers.py`** — a one-time, idempotent import (run at startup)
  of Nepal's `natural=glacier`-tagged features from OpenStreetMap's Overpass
  API into the `Glacier` table, powering search, the directory page, and
  `/glaciers/stats`. Chosen over the official Randolph Glacier Inventory
  (RGI) because RGI is shapefile-only and may sit behind an Earthdata login
  — not worth the dependency weight or the login-wall risk for a prototype.
  Requires a descriptive `User-Agent` header; Overpass returns 406 without
  one. A failure here is logged and does not block startup.
  - Fetches full polygon geometry (`out geom;`), not just centroids, for
    both simple ways (96% of the inventory) and multipolygon relations
    (~4% — large glacier complexes like Ngozumpa, Nepal's longest glacier,
    which OSM mappers split into outer/inner member ways rather than one
    simple shape). `geo.py` computes an approximate area for both cases: a
    shoelace formula scaled by km-per-degree at the glacier's latitude
    (`polygon_area_km2`), and outer-minus-inner-ring area for multipolygons
    (`multipolygon_area_km2`). This is a flat-earth approximation, not
    survey-grade — but validated against reality: the computed Nepal-wide
    total (~4,167 km²) lands close to published ICIMOD estimates
    (~3,800–4,200 km²), and Ngozumpa comes out at 62 km², in range of
    published figures.
  - District attribution (which of Nepal's 77 districts each glacier falls
    in) was investigated and deliberately left out: it needs a real spatial
    join against district boundary polygons, which is a materially bigger
    and more fragile piece of work than area computation, and bulk
    reverse-geocoding via Nominatim is against that service's usage policy
    at this volume. Documented gap, not a silent omission.

## On-demand analysis for any glacier

The Live Dashboard's risk scoring only ever existed for the 7 curated
watersheds, which have accumulated sensor/satellite history. The Glacier
Directory's "Analyze risk" button (`GlacierDetailPanel.jsx`) instead calls
`POST /glaciers/{id}/analyze`, which works for any of the ~3,300 glaciers:

- `models.py`: `SatelliteObservation.lake_id` is nullable, and a nullable
  `glacier_id` FK was added — a row is attached to exactly one of the two.
  `ingestion/satellite.py`'s live/demo ingestion functions were generalized
  to take `(lat, lon)` plus whichever id applies, so the NDWI/dedup/
  terrain-change math is written once and reused unchanged in both paths.
- `risk/scoring.py::compute_adhoc_risk` scores a `Glacier` the same way a
  curated lake is scored, except there is no ground sensor at an arbitrary
  location. Rather than silently counting the missing sensor as a
  confirmed 0 (understating risk), `RiskComponents.sensor_available=False`
  triggers renormalizing the other 3 weights to sum to 1 — a genuinely
  different (and more honest) number than "sensor says 0."
- Each analysis persists its satellite observation, so a second analysis
  of the same glacier — even days later — produces a real terrain-change
  comparison instead of the "no prior observation" default. There's no
  historical trend chart for these yet (unlike the curated watersheds'
  `/risk-history`), since that would need the same accumulation the 7
  curated watersheds already have.

## Risk scoring (`backend/app/risk/scoring.py`)

Deliberately a transparent weighted formula, not a black-box model — a
reviewer (NGO, government, funder) can see exactly why a watershed is
flagged:

```
score = 100 * (0.30*terrain_change + 0.25*lake_growth + 0.20*rainfall + 0.25*sensor)
```

Every component is independently queryable and each has a documented
saturation assumption (e.g. 10% lake-area growth over the lookback window
maps to a lake_growth component of 1.0). All four scoring functions accept
an `asof` timestamp, so the exact same code path is used for live scoring
and for historical backfill/backtesting — there is no separate "replay"
implementation to keep in sync.

`scheduler.py` runs this on an interval (`APScheduler`, default 5 minutes)
across all watersheds, persists a `RiskScore` row, and calls
`alerts/dispatch.py` when the level crosses `high`/`critical`. It's also
exposed as `POST /cycle/run` for demoing without waiting on the interval.

## Alerting (`backend/app/alerts/dispatch.py`)

Prototype: logs the alert and writes an `Alert` row, debounced per
watershed (won't re-fire the same level within an hour of the last alert
at that watershed). Production would fan this out over SMS/IVR — see
`DEPLOYMENT.md`.

## API (`backend/app/api/`)

REST endpoints for watersheds (with latest risk), risk-score history,
satellite observations, sensor readings (including a manual POST endpoint
that demonstrates the path a real LoRaWAN gateway would use), alerts, the
manual cycle trigger, and glacier search/browse (`routes_glaciers.py`).

## Frontend (`frontend/src/`)

- `MapView.jsx` — Leaflet map, watersheds as risk-colored markers, plus a
  distinct grey marker for a searched (non-monitored) glacier.
- `GlacierSearch.jsx` — debounced search box over the full Nepal glacier
  inventory; selecting a result flies the map to it.
- `GlacierDirectory.jsx` / `GlacierDetailPanel.jsx` / `TopGlaciersChart.jsx`
  — the third tab: stat cards, a top-10-by-area bar chart, and a
  searchable/sortable paginated table over all ~3,300 glaciers. Selecting a
  row renders that glacier's real outline (`geometry_geojson`) on a small
  Leaflet map via react-leaflet's `GeoJSON` component.
- `RiskChart.jsx` — Recharts line chart of the composite score and its
  components over time, with threshold reference lines.
- `WatershedDetail.jsx` / `AlertLog.jsx` — the live-dashboard sidebar.
- `CaseStudy.jsx` — the Rasuwa, Aug 26 2026 backtest narrative, built from
  the same `/risk-history` endpoint as the live dashboard.

## Why this shape

The core design bet is that **the scoring logic must be identical for live
operation and historical backtesting** (the `asof` parameter threading
through every component function), because a pitch that claims "this model
would have caught it" is only credible if the historical numbers came from
the same code path a live deployment would run — not a separately-tuned
replay.
