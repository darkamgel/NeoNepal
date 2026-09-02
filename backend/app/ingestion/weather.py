"""Rainfall data via Open-Meteo (free, no API key required).

Falls back to a fixed low-anomaly value if the API is unreachable, so scoring
never breaks purely because of network access in a demo environment.
"""

import datetime as dt

import httpx

# Rough monsoon-season (Jun-Sep) average daily rainfall for the central
# Himalayan foothills, mm/day. Used only as a normalization baseline for the
# anomaly score — documented assumption, not a precise climatological figure.
_MONSOON_BASELINE_MM_DAY = 12.0

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Beyond this many days in the past, the forecast API's `past_days` window no
# longer reaches — switch to the archive API instead.
_ARCHIVE_CUTOFF_DAYS = 5


def _anomaly_from_values(values: list[float]) -> float:
    values = [v for v in values if v is not None]
    if not values:
        return 0.1
    avg = sum(values) / len(values)
    anomaly = avg / _MONSOON_BASELINE_MM_DAY
    return round(min(max(anomaly, 0.0), 1.0), 3)


def fetch_rainfall_anomaly(
    lat: float, lon: float, asof: dt.datetime | None = None, past_days: int = 7
) -> float:
    """Returns a 0-1 anomaly score: average daily rainfall vs. baseline for
    the `past_days` window ending at `asof` (default: now).
    """
    asof = asof or dt.datetime.utcnow()
    age_days = (dt.datetime.utcnow() - asof).days

    try:
        if age_days <= _ARCHIVE_CUTOFF_DAYS:
            resp = httpx.get(
                _FORECAST_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "precipitation_sum",
                    "past_days": max(past_days, age_days + 1),
                    "forecast_days": 1,
                    "timezone": "Asia/Kathmandu",
                },
                timeout=10.0,
            )
        else:
            end_date = asof.date()
            start_date = end_date - dt.timedelta(days=past_days)
            resp = httpx.get(
                _ARCHIVE_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "daily": "precipitation_sum",
                    "timezone": "Asia/Kathmandu",
                },
                timeout=10.0,
            )
        resp.raise_for_status()
        data = resp.json()
        values = data.get("daily", {}).get("precipitation_sum", [])
        return _anomaly_from_values(values)
    except (httpx.HTTPError, ValueError, KeyError):
        return 0.1
