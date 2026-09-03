# From Prototype to Real Deployment

This prototype demonstrates the architecture and shows a credible backtest
against the Aug 26, 2026 Rasuwa disaster. This document covers what
distinguishes it from a deployable system, honestly, for anyone evaluating
whether to fund or partner on the next phase.

## What's real vs. simulated in the prototype today

| Component | Prototype | Real deployment needs |
|---|---|---|
| Rainfall | **Real** — Open-Meteo forecast/archive APIs | Same, or a paid higher-resolution provider |
| Satellite lake area | **Real** — live Sentinel-2 via Planetary Computer (NDWI), zero credentials at prototype scale | Same pipeline; add a registered PC API key for production rate limits/reliability |
| Satellite terrain change | **Real imagery, weak proxy** — brightness-shift between real scenes, not true instability detection | SAR/InSAR-based change detection (see §2 below) |
| Nepal glacier search | **Real** — ~3,300 features from OpenStreetMap Overpass | Same, or supplement with the official RGI once the GDAL/login tradeoff is worth it |
| Ground sensors (water level, seismic) | Simulated | Physical IoT hardware |
| Alert delivery | Logged to a database table | SMS/IVR fan-out to real phone numbers |
| Risk model | Transparent weighted formula, hand-tuned saturation constants | Same approach, but weights/constants calibrated against real historical events with domain experts (ICIMOD glaciologists), not one illustrative case |

## 1. Data partnerships

- **ICIMOD** (International Centre for Integrated Mountain Development,
  Kathmandu) maintains the region's most complete glacial lake inventory
  and GLOF risk assessments — the natural technical partner and a source of
  validated historical data to calibrate the risk model beyond one case.
- **DHM** (Nepal's Department of Hydrology and Meteorology) operates the
  country's official hydromet monitoring network and would need to be a
  partner or the eventual system owner for any alert to carry official
  weight.
- **NDRRMA** (National Disaster Risk Reduction and Management Authority) is
  the natural integration point for alert delivery — piggybacking on
  channels people already trust beats standing up a parallel one.
- Cross-border data sharing with China (the Aug 2026 event also affected
  Tibet) would meaningfully extend upstream lead time for shared
  watersheds, but requires a diplomatic/institutional channel, not just a
  technical one.

## 2. Satellite ingestion — real, but with real limits

`ingestion/satellite.py` now pulls live Sentinel-2 imagery from Microsoft's
Planetary Computer (STAC search, anonymous SAS token, windowed `rasterio`
reads) and computes real NDWI-based lake area. This closes the biggest gap
from the original prototype, but real limits remain:

- **Cadence is imagery-limited, not clock-limited.** Sentinel-2 revisits any
  point roughly every 5 days; the 5-minute scheduler mostly finds nothing
  new. A production system doesn't get around this by polling more often —
  it needs either a paid high-revisit commercial provider (e.g. Planet Labs,
  daily) or to treat the multi-day cadence as inherent to optical satellite
  monitoring.
- **The terrain-change signal is a weak proxy.** It's currently a brightness
  shift between two real scenes — a real, honest signal, but not true
  ground-deformation detection. **The Rasuwa event itself was a
  glacier/rock-mass collapse, not a classic lake outburst** — optical
  lake-area monitoring alone would likely not have caught it with useful
  lead time. A production system needs Sentinel-1 SAR/InSAR-based
  ground-deformation detection as an independent, higher-fidelity signal
  for this hazard type; that's a materially larger engineering effort than
  the optical NDWI pipeline here (SAR processing, phase unwrapping,
  atmospheric correction).
- **Cloud cover in monsoon season** (precisely when risk is highest) limits
  optical revisit further — SAR's cloud-penetration makes it not optional
  for the highest-risk season, not just a nice-to-have.
- **Rate limits.** The prototype uses Planetary Computer's anonymous tier,
  fine for a handful of watersheds ticking every 5 minutes. Scaling to
  ICIMOD's full high-risk lake inventory should get a registered (still
  free) PC subscription key for headroom and reliability.

## 3. Ground sensor network

- Real hardware: solar-powered LoRaWAN water-level and seismic/tilt sensors
  (e.g. Dragino or similar off-the-shelf LoRaWAN nodes), roughly
  $200–500/node in hardware, plus a gateway (~$300–800) per valley with
  line-of-sight to the nodes.
- Rasuwa-scale deployment (a handful of high-risk valleys, 3-5 sensors
  each): rough order-of-magnitude hardware cost in the low tens of
  thousands of USD, before installation, solar/battery maintenance, and
  physical access logistics (many sites are multi-day treks from a road).
- Satellite backhaul (e.g. a low-cost IoT satellite modem) is worth
  budgeting for gateway connectivity, since cellular coverage is patchy in
  exactly the terrain that matters.

## 4. Alert delivery

- SMS/IVR through a local telecom (Ncell, NTC) or an aggregator like
  Twilio with local number support — needs a commercial agreement, not
  just an API key, to reach the volume and reliability required for a
  life-safety system.
- Should integrate with, not replace, NDRRMA's existing siren/ward-office
  alert infrastructure where it exists.
- Message design and last-mile trust matter as much as latency — an alert
  from an unfamiliar sender may be ignored; routing through an
  already-trusted authority's number/channel is likely more effective than
  a new one.

## 5. Hosting & compliance

- Postgres + PostGIS instead of SQLite for concurrent writes and proper
  geospatial queries; models in this prototype are already written against
  a plain ORM so this is a connection-string change, not a rewrite.
- Data residency: sensor and imagery data covering Nepali territory likely
  has requirements around where it can be hosted — confirm with DHM/NDRRMA
  before picking a cloud region.
- Uptime matters for a life-safety system in a way it doesn't for a demo —
  budget for redundancy (multi-region or on-prem failover) before this
  carries real alerting responsibility.
- **Move the scheduler out of the web-serving processes.** The prototype's
  periodic risk recompute runs in-process (`risk/scheduler.py`), guarded by
  a single-machine file lock (`scheduler_lock.py`) so it doesn't fire once
  per worker process. That's a stopgap, not the real fix — production
  should run it as its own worker/cron process (e.g. a separate `celery
  beat`/cron entry calling the same `run_cycle` function), decoupled from
  however many API-serving processes are running.
- **Rate limiting needs a shared backend at real scale.** The prototype's
  per-IP limiter on `/cycle/run` and `/glaciers/{id}/analyze`
  (`rate_limit.py`) is in-memory and process-local — correct for a single
  process, but the effective limit silently multiplies by worker count
  under multiple processes, and doesn't stop a distributed abuser. Move to
  a shared store (Redis, or an API gateway's built-in rate limiting) before
  this is public-facing at scale.

## 6. Model validation

The single-case backtest in this prototype (Rasuwa, Aug 2026) is a
proof-of-concept, not a validated model. Before any real alert threshold is
trusted:

- Backtest against every documented Himalayan GLOF/glacial-collapse event
  with available historical satellite imagery, not just one.
- Establish false-positive/false-negative rates with domain experts —
  "the model would have caught it" is a much weaker claim than "the model
  catches most and its false-alarm rate is acceptable to the communities
  who'll be evacuated on its say-so."

## Suggested phased rollout

1. **Pilot**: 1–2 valleys (Rasuwa most obviously), SAR/InSAR added alongside
   the existing optical pipeline + a small real sensor network, alerts to a
   research/NGO team only (no public alerting yet), 6–12 months of live
   validation.
2. **Supervised alerting**: same valleys, alerts routed through NDRRMA with
   a human-in-the-loop review before public dispatch.
3. **Scale**: expand to ICIMOD's full high-risk lake inventory, automate
   alerting where validated, integrate cross-border data sharing where
   diplomatically feasible.

## Rough budget range (pilot phase, 1-2 valleys)

Sensor hardware + installation: $20k–50k. Satellite/cloud infrastructure
(GEE is free for eligible use; compute/hosting): $5k–15k/year. Alert
delivery agreements: highly variable, likely $5k–20k/year depending on
volume commitments. Engineering time for the live satellite pipeline and
model validation work is the largest real cost and isn't estimated here —
it depends entirely on who's hired and for how long.
