"""
Build a single /api/report response from existing NWS + OpenAI caches
for the SailCast static frontend.
"""
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.services.nws_service import nws_service
from app.services.openai_service import openai_service

router = APIRouter()


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


def _map_alert(f: dict) -> dict:
    props = f.get("properties", {})
    return {
        "event": props.get("event"),
        "severity": props.get("severity"),
        "headline": props.get("headline"),
        "onset": props.get("onset"),
        "ends": props.get("ends"),
    }


@router.get("/report")
async def api_report():
    """Single report payload for the SailCast static UI at /."""
    hourly_data = nws_service.get_cached_hourly()
    day7_data = nws_service.get_cached_7day()
    alerts_data = nws_service.get_cached_alerts()
    summary_data = openai_service.get_cached_summary()

    if hourly_data is None:
        raise HTTPException(
            status_code=503,
            detail="Forecast data not yet available (scheduler may still be loading).",
        )

    periods = hourly_data.get("periods", [])
    hourly = [_map_hourly_period(p) for p in periods]
    forecast_3day = []
    if day7_data and day7_data.get("periods"):
        forecast_3day = [_map_7day_period(p) for p in day7_data["periods"][:9]]
    alerts = []
    if alerts_data and alerts_data.get("features"):
        alerts = [_map_alert(f) for f in alerts_data["features"]]

    recommendation = ""
    if summary_data and isinstance(summary_data, dict):
        recommendation = (
            summary_data.get("summary", "")
            or summary_data.get("text", "")
            or str(summary_data)
        )
    elif isinstance(summary_data, str):
        recommendation = summary_data

    location = {
        "name": getattr(settings, "LOCATION_NAME", None)
        or f"{settings.NWS_OFFICE} {settings.NWS_GRIDPOINT_X},{settings.NWS_GRIDPOINT_Y}",
        "lat": str(getattr(settings, "NWS_GRIDPOINT_Y", "")),
        "lon": str(getattr(settings, "NWS_GRIDPOINT_X", "")),
    }

    return {
        "location": location,
        "forecast_3day": forecast_3day,
        "hourly": hourly,
        "alerts": alerts,
        "marine_forecast": None,
        "tides": [],
        "recommendation": recommendation or "No recommendation available.",
    }
