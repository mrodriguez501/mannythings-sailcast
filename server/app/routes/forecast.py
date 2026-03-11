"""
Forecast API Routes
Serves cached forecast data and AI-generated summaries to the frontend.
"""

from fastapi import APIRouter, HTTPException
from app.services.nws_service import nws_service
from app.services.openai_service import openai_service
from app.services.budget_tracker import budget_tracker

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


def _require_cached(data, detail: str = "Data not yet available"):
    if data is None:
        raise HTTPException(status_code=503, detail=detail)
    return data


@router.get("/hourly")
async def get_hourly_forecast():
    """Return the cached 24-hour hourly wind forecast."""
    return _require_cached(nws_service.get_cached_hourly(), "Forecast data not yet available")


@router.get("/7day")
async def get_7day_forecast():
    """Return the cached 7-day weather outlook."""
    return _require_cached(nws_service.get_cached_7day(), "Forecast data not yet available")


@router.get("/alerts")
async def get_alerts():
    """Return active NWS alerts for the sailing area."""
    return _require_cached(nws_service.get_cached_alerts(), "Alert data not yet available")


@router.get("/summary")
async def get_ai_summary():
    """Return the latest AI-generated weather summary and sailing advisory."""
    return _require_cached(openai_service.get_cached_summary(), "AI summary not yet available")


@router.get("/budget")
async def get_budget_status():
    """Return current OpenAI API budget and usage status."""
    return budget_tracker.get_status()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    budget = budget_tracker.get_status()
    return {
        "status": "ok",
        "hourly_data": nws_service.get_cached_hourly() is not None,
        "7day_data": nws_service.get_cached_7day() is not None,
        "alerts_data": nws_service.get_cached_alerts() is not None,
        "ai_summary": openai_service.get_cached_summary() is not None,
        "budget_remaining_monthly": budget["remaining"]["monthly_budget"],
        "budget_remaining_daily": budget["remaining"]["daily_budget"],
    }
