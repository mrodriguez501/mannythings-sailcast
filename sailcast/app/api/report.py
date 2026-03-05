"""Sailing report API: location, 3-day forecast, hourly wind, alerts, tides, LLM recommendation."""
from fastapi import APIRouter, HTTPException

from app.services.weather import get_all_weather_data
from app.services.retrieval import get_club_guidance
from app.services.llm import generate_report
from app.cache.hourly_cache import get_cached_report, set_cached_report

router = APIRouter()


@router.get("/report")
async def api_report():
    """
    Return full sailing report: location, 3-day forecast, 2-day hourly wind,
    weather alerts, tide predictions, and LLM recommendation. Cached per UTC hour.
    """
    try:
        cached = get_cached_report()
        if cached is not None:
            return cached

        data = await get_all_weather_data()
        guidance = get_club_guidance(data["hourly"])
        recommendation = await generate_report(
            forecast_3day=data["forecast_3day"],
            hourly=data["hourly"],
            alerts=data["alerts"],
            tides=data["tides"],
            guidance=guidance,
        )

        response = {
            "location": data["location"],
            "forecast_3day": data["forecast_3day"],
            "hourly": data["hourly"],
            "alerts": data["alerts"],
            "marine_forecast": data["marine_forecast"],
            "tides": data["tides"],
            "recommendation": recommendation,
        }
        set_cached_report(response)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
