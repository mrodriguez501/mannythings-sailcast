"""
NWS Service
Fetches and parses National Weather Service forecast data.
Caches the latest results in memory for fast API responses.
"""

import logging
from datetime import UTC, datetime

import httpx

from app.config import settings

logger = logging.getLogger("sailcast.nws")


class NWSService:
    """Handles all NWS API interactions and data caching."""

    def __init__(self):
        self._hourly_cache: dict | None = None
        self._7day_cache: dict | None = None
        self._alerts_cache: dict | None = None
        self._last_fetch: str | None = None

    def _headers(self) -> dict:
        """NWS API requires a User-Agent header."""
        return {
            "User-Agent": settings.NWS_USER_AGENT,
            "Accept": "application/geo+json",
        }

    async def fetch_hourly_forecast(self) -> dict:
        """Fetch the hourly forecast from NWS and cache it."""
        logger.info("Fetching hourly forecast from NWS...")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(settings.nws_forecast_url, headers=self._headers())
                response.raise_for_status()
                raw = response.json()

            # Parse into a simplified format: next 24 hours
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
                        "windGust": p.get("windGust"),
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
