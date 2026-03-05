"""Weather forecast API - returns raw hourly forecast data."""
from fastapi import APIRouter, HTTPException

from app.services.weather import get_hourly_forecast

router = APIRouter()


@router.get("/forecast")
async def api_forecast():
    """Return normalized hourly forecast JSON from external weather API."""
    try:
        data = await get_hourly_forecast()
        return data
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
