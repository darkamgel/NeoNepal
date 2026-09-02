import datetime as dt

from pydantic import BaseModel, ConfigDict


class LakeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    lat: float
    lon: float
    hazard_type: str


class RiskScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    computed_at: dt.datetime
    score: float
    level: str
    lake_growth_component: float
    terrain_change_component: float
    rainfall_component: float
    sensor_component: float


class WatershedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    district: str
    centroid_lat: float
    centroid_lon: float
    description: str | None = None
    lakes: list[LakeOut] = []


class WatershedWithRiskOut(WatershedOut):
    latest_risk: RiskScoreOut | None = None


class SatelliteObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    observed_at: dt.datetime
    surface_area_m2: float | None
    terrain_change_index: float | None
    source: str


class SensorReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    recorded_at: dt.datetime
    water_level_m: float | None
    seismic_activity: float | None
    source: str


class SensorReadingIn(BaseModel):
    water_level_m: float
    seismic_activity: float


class GlacierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str | None
    lat: float
    lon: float
    osm_id: int
    osm_type: str
    area_km2: float | None
    wikipedia: str | None


class GlacierDetailOut(GlacierOut):
    wikidata: str | None
    geometry_geojson: str | None


class GlacierStatsOut(BaseModel):
    total_count: int
    named_count: int
    with_area_count: int
    total_area_km2: float
    largest: list[GlacierOut]


class GlacierRiskOut(BaseModel):
    glacier_id: int
    score: float
    level: str
    terrain_change_component: float
    lake_growth_component: float
    rainfall_component: float
    sensor_available: bool
    observation_count: int
    computed_at: dt.datetime


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    watershed_id: int
    triggered_at: dt.datetime
    risk_score: float
    level: str
    message: str
    channel: str
