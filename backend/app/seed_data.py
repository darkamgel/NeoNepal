"""Seeds representative watersheds/lakes and an illustrative pre-event observation
trend for the Aug 26, 2026 Rasuwa disaster, so the dashboard has a real, named
case study from day one.

IMPORTANT: the Rasuwa lead-up observations here are SYNTHETIC (source="demo") —
a plausible illustrative trend, not the actual historical satellite record.
Replacing this with a real Sentinel-2 backtest is tracked as a stretch goal
(see docs/DEPLOYMENT.md).
"""

import datetime as dt

from .alerts.dispatch import maybe_dispatch_alert
from .db import Base, SessionLocal, engine
from .models import GlacialLake, RiskScore, SatelliteObservation, SensorReading, Watershed
from .risk.scoring import compute_risk

EVENT_DATE = dt.datetime(2026, 8, 26)


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Watershed).count() > 0:
            print("Database already seeded, skipping.")
            return

        rasuwa = Watershed(
            name="Langtang-Trishuli (Rasuwa)",
            district="Rasuwa",
            centroid_lat=28.2100,
            centroid_lon=85.5300,
            description=(
                "Site of the Aug 26, 2026 glacial collapse on Langtang Lirung "
                "that triggered debris avalanche and flash floods along a 72km "
                "stretch of the Trishuli River."
            ),
        )
        melamchi = Watershed(
            name="Melamchi (Sindhupalchok)",
            district="Sindhupalchok",
            centroid_lat=27.9330,
            centroid_lon=85.5500,
            description="Downstream valley with prior flood history (2021 Melamchi flood).",
        )
        imja = Watershed(
            name="Imja Valley (Solukhumbu)",
            district="Solukhumbu",
            centroid_lat=27.9000,
            centroid_lon=86.9330,
            description="Home to Imja Tsho, one of the Himalaya's most-studied GLOF-risk lakes.",
        )
        tsho_rolpa = Watershed(
            name="Rolwaling Valley (Dolakha)",
            district="Dolakha",
            centroid_lat=27.8670,
            centroid_lon=86.4670,
            description=(
                "Home to Tsho Rolpa, Nepal's largest glacial lake and one of ICIMOD's "
                "longest-monitored GLOF risk sites; a 1998 mitigation project lowered "
                "its water level after decades of rapid growth."
            ),
        )
        thulagi = Watershed(
            name="Thulagi / Dona Valley (Manang-Lamjung)",
            district="Lamjung",
            centroid_lat=28.4870,
            centroid_lon=84.4860,
            description="Home to Thulagi (Dona) glacial lake, near Manaslu, identified as potentially dangerous.",
        )
        lower_barun = Watershed(
            name="Barun Valley (Sankhuwasabha)",
            district="Sankhuwasabha",
            centroid_lat=27.7830,
            centroid_lon=87.0830,
            description="Home to Lower Barun glacial lake, in the Makalu-Barun region, with one of the highest documented expansion rates.",
        )
        dig_tsho = Watershed(
            name="Langmoche Valley (Solukhumbu)",
            district="Solukhumbu",
            centroid_lat=27.8700,
            centroid_lon=86.5800,
            description=(
                "Home to Dig Tsho, site of Nepal's best-documented historical GLOF "
                "(Aug 4, 1985), which destroyed a nearly-completed hydropower plant."
            ),
        )
        db.add_all([rasuwa, melamchi, imja, tsho_rolpa, thulagi, lower_barun, dig_tsho])
        db.flush()

        langtang_lirung = GlacialLake(
            watershed_id=rasuwa.id,
            name="Langtang Lirung glacier mass",
            lat=28.2500,
            lon=85.6600,
            hazard_type="ice_avalanche",
        )
        melamchi_lake = GlacialLake(
            watershed_id=melamchi.id,
            name="Upper Melamchi glacial source",
            lat=28.0500,
            lon=85.5800,
            hazard_type="debris_flow",
        )
        imja_tsho = GlacialLake(
            watershed_id=imja.id,
            name="Imja Tsho",
            lat=27.9000,
            lon=86.9330,
            hazard_type="glof",
        )
        tsho_rolpa_lake = GlacialLake(
            watershed_id=tsho_rolpa.id,
            name="Tsho Rolpa",
            lat=27.8670,
            lon=86.4670,
            hazard_type="glof",
        )
        thulagi_lake = GlacialLake(
            watershed_id=thulagi.id,
            name="Thulagi (Dona Tal)",
            lat=28.4870,
            lon=84.4860,
            hazard_type="glof",
        )
        lower_barun_lake = GlacialLake(
            watershed_id=lower_barun.id,
            name="Lower Barun",
            lat=27.7830,
            lon=87.0830,
            hazard_type="glof",
        )
        dig_tsho_lake = GlacialLake(
            watershed_id=dig_tsho.id,
            name="Dig Tsho",
            lat=27.8700,
            lon=86.5800,
            hazard_type="glof",
        )
        db.add_all(
            [
                langtang_lirung,
                melamchi_lake,
                imja_tsho,
                tsho_rolpa_lake,
                thulagi_lake,
                lower_barun_lake,
                dig_tsho_lake,
            ]
        )
        db.flush()

        # Illustrative 7-month lead-up to the Rasuwa event: terrain-change index
        # accelerates in the final weeks (proxy for the glacier destabilizing),
        # lake/mass surface area roughly stable until a late sharp shift.
        start = EVENT_DATE - dt.timedelta(days=210)
        n_points = 15
        for i in range(n_points):
            days_offset = int(210 * i / (n_points - 1))
            observed_at = start + dt.timedelta(days=days_offset)
            progress = i / (n_points - 1)  # 0 -> 1 approaching the event
            # Gentle baseline drift, sharp acceleration in the last ~20% of the window.
            terrain_change = 0.05 + 0.15 * progress**3
            surface_area = 180_000 + 4_000 * progress**2
            db.add(
                SatelliteObservation(
                    lake_id=langtang_lirung.id,
                    observed_at=observed_at,
                    surface_area_m2=round(surface_area, 1),
                    terrain_change_index=round(terrain_change, 4),
                    source="demo",
                )
            )

        # Simulated sensor readings for the same window: seismic noise floor
        # with a visible uptick in the final days.
        for i in range(30):
            days_before = 29 - i
            recorded_at = EVENT_DATE - dt.timedelta(days=days_before)
            progress = 1 - (days_before / 29)
            # Sharp late escalation: gentle seismic noise for most of the month,
            # crossing into a sharp precursor spike only in the final ~1-2 days —
            # illustrating why ground sensors matter (satellite alone plateaus
            # at "moderate"; the combined score only reaches "high" this late).
            seismic = 0.05 + 0.85 * progress**5
            water_level = 1.2 + 0.9 * progress**4
            db.add(
                SensorReading(
                    watershed_id=rasuwa.id,
                    recorded_at=recorded_at,
                    water_level_m=round(water_level, 2),
                    seismic_activity=round(min(seismic, 1.0), 3),
                    source="simulated",
                )
            )

        # Baseline low-risk history for the other watersheds so the map
        # shows contrast, not just one hot spot.
        for lake, watershed in [
            (melamchi_lake, melamchi),
            (imja_tsho, imja),
            (tsho_rolpa_lake, tsho_rolpa),
            (thulagi_lake, thulagi),
            (lower_barun_lake, lower_barun),
            (dig_tsho_lake, dig_tsho),
        ]:
            for i in range(6):
                observed_at = dt.datetime.utcnow() - dt.timedelta(days=30 * (5 - i))
                db.add(
                    SatelliteObservation(
                        lake_id=lake.id,
                        observed_at=observed_at,
                        surface_area_m2=round(90_000 + 500 * i, 1),
                        terrain_change_index=round(0.03 + 0.005 * i, 4),
                        source="demo",
                    )
                )
                db.add(
                    SensorReading(
                        watershed_id=watershed.id,
                        recorded_at=observed_at,
                        water_level_m=1.0,
                        seismic_activity=0.04,
                        source="simulated",
                    )
                )

        db.commit()
        print("Seeded 7 watersheds, 7 lakes, and illustrative observation history.")

        print("Backfilling historical risk scores (uses real historical rainfall)...")
        for watershed in (rasuwa, melamchi, imja, tsho_rolpa, thulagi, lower_barun, dig_tsho):
            _backfill_risk_history(db, watershed)
        print("Backfill complete.")
    finally:
        db.close()


def _backfill_risk_history(db, watershed: Watershed):
    """Recomputes risk scores at each historical satellite-observation
    timestamp for a watershed, so its risk-score history shows the trend the
    model would have produced over time rather than a single "now" point.
    Uses real historical rainfall (Open-Meteo archive API) combined with the
    (synthetic, for Rasuwa) satellite/sensor trend seeded above.
    """
    asof_dates = sorted(
        {obs.observed_at for lake in watershed.lakes for obs in lake.observations}
        | {reading.recorded_at for reading in watershed.sensor_readings}
    )
    for asof in asof_dates:
        components = compute_risk(db, watershed, asof=asof)
        risk_score = RiskScore(
            watershed_id=watershed.id,
            computed_at=asof,
            score=components.score,
            level=components.level,
            lake_growth_component=components.lake_growth,
            terrain_change_component=components.terrain_change,
            rainfall_component=components.rainfall,
            sensor_component=components.sensor,
        )
        db.add(risk_score)
        db.commit()
        db.refresh(risk_score)
        maybe_dispatch_alert(db, watershed, risk_score, at=asof)


if __name__ == "__main__":
    seed()
