"""
Forecast API Routes
Serves cached forecast data and AI-generated summaries to the frontend.
"""

from fastapi import APIRouter, HTTPException
from app.services.nws_service import nws_service
from app.services.openai_service import openai_service
from app.services.budget_tracker import budget_tracker

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


@router.get("/hourly")
async def get_hourly_forecast():
    """Return the cached 24-hour hourly wind forecast."""
    data = nws_service.get_cached_hourly()
    if data is None:
        raise HTTPException(status_code=503, detail="Forecast data not yet available")
    return data


@router.get("/7day")
async def get_7day_forecast():
    """Return the cached 7-day weather outlook."""
    data = nws_service.get_cached_7day()
    if data is None:
        raise HTTPException(status_code=503, detail="Forecast data not yet available")
    return data


@router.get("/alerts")
async def get_alerts():
    """Return active NWS alerts for the sailing area."""
    data = nws_service.get_cached_alerts()
    if data is None:
        raise HTTPException(status_code=503, detail="Alert data not yet available")
    return data


@router.get("/summary")
async def get_ai_summary():
    """Return the latest AI-generated weather summary and sailing advisory."""
    summary = openai_service.get_cached_summary()
    if summary is None:
        raise HTTPException(status_code=503, detail="AI summary not yet available")
    return summary


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
