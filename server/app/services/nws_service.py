"""
NWS Service
Fetches and parses National Weather Service forecast data.
Caches the latest results in memory for fast API responses.
"""

import logging
import re
from datetime import UTC, datetime, timedelta

import httpx

from app.config import settings

logger = logging.getLogger("sailcast.nws")

KMH_TO_MPH = 0.621371


def _parse_iso_duration(duration: str) -> int:
    """Parse an ISO 8601 duration like 'PT2H' into hours. Returns 1 if unparseable."""
    m = re.match(r"PT(\d+)H", duration)
    return int(m.group(1)) if m else 1


def _expand_gridpoint_series(values: list, uom: str = "") -> dict[str, float]:
    """Expand NWS gridpoint time-series data into a per-hour map.

    NWS raw gridpoint data uses ISO 8601 intervals like:
      "validTime": "2026-03-12T10:00:00+00:00/PT2H", "value": 50.0
    This means the value covers 2 hours starting at that time.

    Returns a dict mapping ISO hour strings (truncated to hour) to mph values.
    """
    hourly_map: dict[str, float] = {}
    is_kmh = "km" in uom.lower()
    for entry in values:
        valid_time = entry.get("validTime", "")
        val = entry.get("value")
        if val is None:
            continue
        parts = valid_time.split("/")
        if len(parts) != 2:
            continue
        start_iso, duration = parts
        try:
            start = datetime.fromisoformat(start_iso)
        except ValueError:
            continue
        hours = _parse_iso_duration(duration)
        mph = val * KMH_TO_MPH if is_kmh else val
        mph = round(mph, 1)
        for h in range(hours):
            hour_dt = start + timedelta(hours=h)
            key = hour_dt.strftime("%Y-%m-%dT%H")
            hourly_map[key] = mph
    return hourly_map


class NWSService:
    """Handles all NWS API interactions and data caching."""

    def __init__(self):
        self._hourly_cache: dict | None = None
        self._7day_cache: dict | None = None
        self._alerts_cache: dict | None = None
        self._gust_map: dict[str, float] = {}
        self._last_fetch: str | None = None

    def _headers(self) -> dict:
        """NWS API requires a User-Agent header."""
        return {
            "User-Agent": settings.NWS_USER_AGENT,
            "Accept": "application/geo+json",
        }

    async def fetch_gridpoint_gusts(self) -> dict[str, float]:
        """Fetch wind gust data from the raw NWS gridpoint endpoint.

        The hourly forecast endpoint returns windGust as null,
        but the raw gridpoint data has full gust time-series.
        """
        logger.info("Fetching gridpoint gust data from NWS...")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(settings.nws_gridpoint_url, headers=self._headers())
                response.raise_for_status()
                raw = response.json()

            props = raw.get("properties", {})
            gust_data = props.get("windGust", {})
            values = gust_data.get("values", [])
            uom = gust_data.get("uom", "")

            self._gust_map = _expand_gridpoint_series(values, uom)
            logger.info(f"Gridpoint gusts cached ({len(self._gust_map)} hourly values)")
            return self._gust_map

        except Exception as e:
            logger.warning(f"Failed to fetch gridpoint gusts: {e}")
            self._gust_map = {}
            return self._gust_map

    def _match_gust(self, start_time: str) -> str | None:
        """Look up a gust value for a given hourly period start time."""
        if not self._gust_map:
            return None
        try:
            dt = datetime.fromisoformat(start_time)
            dt_utc = dt.astimezone(tz=UTC)
            key = dt_utc.strftime("%Y-%m-%dT%H")
            mph = self._gust_map.get(key)
            if mph is not None:
                return f"{round(mph)} mph"
        except (ValueError, TypeError):
            pass
        return None

    async def fetch_hourly_forecast(self) -> dict:
        """Fetch the hourly forecast from NWS and cache it."""
        logger.info("Fetching hourly forecast from NWS...")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(settings.nws_forecast_url, headers=self._headers())
                response.raise_for_status()
                raw = response.json()

            periods = raw.get("properties", {}).get("periods", [])[:24]
            parsed = {
                "periods": [
                    {
                        "startTime": p["startTime"],
                        "endTime": p["endTime"],
                        "temperature": p["temperature"],
                        "temperatureUnit": p["temperatureUnit"],
                        "windSpeed": p["windSpeed"],
                        "windDirection": p["windDirection"],
                        "windGust": p.get("windGust") or self._match_gust(p["startTime"]),
                        "shortForecast": p["shortForecast"],
                        "isDaytime": p["isDaytime"],
                    }
                    for p in periods
                ],
                "fetchedAt": datetime.now(UTC).isoformat(),
            }

            self._hourly_cache = parsed
            self._last_fetch = parsed["fetchedAt"]
            logger.info(f"Hourly forecast cached ({len(periods)} periods)")
            return parsed

        except Exception as e:
            logger.error(f"Failed to fetch hourly forecast: {e}")
            raise

    async def fetch_7day_forecast(self) -> dict:
        """Fetch the 7-day forecast from NWS and cache it."""
        logger.info("Fetching 7-day forecast from NWS...")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(settings.nws_forecast_7day_url, headers=self._headers())
                response.raise_for_status()
                raw = response.json()

            periods = raw.get("properties", {}).get("periods", [])
            parsed = {
                "periods": [
                    {
                        "name": p["name"],
                        "startTime": p["startTime"],
                        "temperature": p["temperature"],
                        "temperatureUnit": p["temperatureUnit"],
                        "windSpeed": p["windSpeed"],
                        "windDirection": p["windDirection"],
                        "shortForecast": p["shortForecast"],
                        "detailedForecast": p["detailedForecast"],
                        "isDaytime": p["isDaytime"],
                    }
                    for p in periods
                ],
                "fetchedAt": datetime.now(UTC).isoformat(),
            }

            self._7day_cache = parsed
            logger.info(f"7-day forecast cached ({len(periods)} periods)")
            return parsed

        except Exception as e:
            logger.error(f"Failed to fetch 7-day forecast: {e}")
            raise

    async def fetch_alerts(self) -> dict:
        """Fetch active weather alerts from NWS and cache them."""
        logger.info("Fetching active alerts from NWS...")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(settings.nws_alerts_url, headers=self._headers())
                response.raise_for_status()
                raw = response.json()

            features = raw.get("features", [])
            parsed = {
                "alerts": [
                    {
                        "event": f["properties"]["event"],
                        "headline": f["properties"].get("headline", ""),
                        "description": f["properties"].get("description", ""),
                        "severity": f["properties"]["severity"],
                        "urgency": f["properties"]["urgency"],
                        "onset": f["properties"].get("onset"),
                        "expires": f["properties"].get("expires"),
                    }
                    for f in features
                ],
                "count": len(features),
                "fetchedAt": datetime.now(UTC).isoformat(),
            }

            self._alerts_cache = parsed
            logger.info(f"Alerts cached ({len(features)} active)")
            return parsed

        except Exception as e:
            logger.error(f"Failed to fetch alerts: {e}")
            raise

    def get_cached_hourly(self) -> dict | None:
        return self._hourly_cache

    def get_cached_7day(self) -> dict | None:
        return self._7day_cache

    def get_cached_alerts(self) -> dict | None:
        return self._alerts_cache

    def get_last_fetch_time(self) -> str | None:
        return self._last_fetch


# Singleton instance
nws_service = NWSService()
