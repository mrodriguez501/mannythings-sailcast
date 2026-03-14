"""
Report Builder

Single source of truth for the frontend report payload.
Reads from all service caches, assembles one JSON dict, writes it to disk,
and caches it in memory. The report route serves this as-is (merging
LLM advice at serve-time).

Output: server/app/data/report.json
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import settings
from app.services.marine_service import marine_service
from app.services.nws_service import nws_service

logger = logging.getLogger("sailcast.report_builder")

LOCAL_TZ = ZoneInfo("America/New_York")
REPORT_PATH = Path(__file__).resolve().parent.parent / "data" / "report.json"


def _map_hourly_period(p: dict) -> dict:
    return {
        "startTime": p.get("startTime"),
        "temp": p.get("temperature"),
        "temperatureUnit": p.get("temperatureUnit", "F"),
        "windSpeed": p.get("windSpeed"),
        "windDirection": p.get("windDirection"),
        "shortForecast": p.get("shortForecast"),
        "windGust": p.get("windGust"),
    }


def _map_7day_period(p: dict) -> dict:
    return {
        "name": p.get("name"),
        "startTime": p.get("startTime"),
        "temp": p.get("temperature"),
        "windSpeed": p.get("windSpeed"),
        "windDirection": p.get("windDirection"),
        "shortForecast": p.get("shortForecast"),
    }


def _map_alert(d: dict, ends_key: str = "ends") -> dict:
    return {
        "event": d.get("event"),
        "severity": d.get("severity"),
        "headline": d.get("headline"),
        "onset": d.get("onset"),
        "ends": d.get(ends_key),
    }


class ReportBuilder:
    """Builds, caches, and persists the frontend report payload."""

    def __init__(self):
        self._cache: dict | None = None

    def build_report(self) -> dict:
        """Assemble the report from all service caches.

        Writes to disk and caches in memory. Does NOT include LLM advice;
        that is merged at serve-time by the report route.
        """
        hourly_data = nws_service.get_cached_hourly()
        day7_data = nws_service.get_cached_7day()
        alerts_data = nws_service.get_cached_alerts()
        marine = marine_service.get_cached_marine()
        tides = marine_service.get_cached_tides() or []

        hourly = []
        if hourly_data and hourly_data.get("periods"):
            hourly = [_map_hourly_period(p) for p in hourly_data["periods"]]

        forecast_3day = []
        if day7_data and day7_data.get("periods"):
            forecast_3day = [_map_7day_period(p) for p in day7_data["periods"][:9]]

        alerts = []
        if alerts_data:
            if alerts_data.get("features"):
                alerts = [_map_alert(f.get("properties", {})) for f in alerts_data["features"]]
            elif alerts_data.get("alerts"):
                alerts = [_map_alert(a, ends_key="expires") for a in alerts_data["alerts"]]

        location = {
            "label": settings.LOCATION_LABEL,
            "name": f"{settings.NWS_OFFICE} {settings.NWS_GRIDPOINT_X},{settings.NWS_GRIDPOINT_Y}",
            "lat": str(getattr(settings, "NWS_GRIDPOINT_Y", "")),
            "lon": str(getattr(settings, "NWS_GRIDPOINT_X", "")),
        }

        report = {
            "location": location,
            "forecast_3day": forecast_3day,
            "hourly": hourly,
            "alerts": alerts,
            "marine_forecast": marine,
            "tides": tides,
            "generatedAt": datetime.now(LOCAL_TZ).isoformat(),
        }

        self._cache = report
        self._write_to_disk(report)
        logger.info(
            f"Report built: {len(hourly)} hourly, {len(forecast_3day)} 3-day, "
            f"{len(alerts)} alerts, {len(tides)} tides"
        )
        return report

    def get_cached_report(self) -> dict | None:
        return self._cache

    def _write_to_disk(self, report: dict) -> None:
        try:
            REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
            REPORT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
            logger.info(f"Report written to {REPORT_PATH}")
        except Exception as e:
            logger.error(f"Failed to write report to disk: {e}")


report_builder = ReportBuilder()
