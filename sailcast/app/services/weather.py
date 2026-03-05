"""
Weather service: NWS (points, 3-day forecast, hourly wind, alerts, marine) and NOAA tides.
Location: DCA area (38.8512, -77.0402) by default; override via env.
Marine zone ANZ535 = Tidal Potomac from Key Bridge to Indian Head (marine.weather.gov/MapClick.php?TextType=1&zoneid=ANZ535).
"""
import os
import re
from datetime import datetime, timedelta, timezone
import httpx

NWS_USER_AGENT = os.environ.get("NWS_USER_AGENT", "SailCast/1.0 (sailing club forecast)")

# Location: lat/lon for NWS, display name, NOAA tide station (Washington DC / Potomac)
LOCATION_LAT = os.environ.get("LOCATION_LAT", "38.8512")
LOCATION_LON = os.environ.get("LOCATION_LON", "-77.0402")
LOCATION_NAME = os.environ.get("LOCATION_NAME", "DCA / Washington DC")
NOAA_TIDE_STATION = os.environ.get("NOAA_TIDE_STATION", "8594900")  # Washington, Potomac River DC

# Marine zone (ANZ535 = Tidal Potomac from Key Bridge to Indian Head)
MARINE_ZONE_ID = os.environ.get("MARINE_ZONE_ID", "ANZ535")


def get_location() -> dict:
    """Return location info for display and API calls."""
    return {
        "lat": float(LOCATION_LAT),
        "lon": float(LOCATION_LON),
        "name": LOCATION_NAME,
        "noaa_station": NOAA_TIDE_STATION,
    }


async def _nws_get(client: httpx.AsyncClient, url: str) -> dict:
    resp = await client.get(
        url,
        headers={"User-Agent": NWS_USER_AGENT, "Accept": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()


async def get_points_forecast() -> list[dict]:
    """
    3-day forecast from NWS: points/{lat},{lon} → forecast URL → periods.
    Each period: name, startTime, endTime, temperature, windSpeed, windDirection, shortForecast, etc.
    """
    points_url = f"https://api.weather.gov/points/{LOCATION_LAT},{LOCATION_LON}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        points = await _nws_get(client, points_url)
        forecast_url = points.get("properties", {}).get("forecast")
        if not forecast_url:
            return []
        forecast = await _nws_get(client, forecast_url)
    periods = forecast.get("properties", {}).get("periods", [])
    return [
        {
            "name": p.get("name"),
            "startTime": p.get("startTime"),
            "endTime": p.get("endTime"),
            "temp": p.get("temperature"),
            "windSpeed": p.get("windSpeed"),
            "windDirection": p.get("windDirection"),
            "shortForecast": p.get("shortForecast"),
            "detailedForecast": p.get("detailedForecast"),
        }
        for p in periods
    ]


async def get_hourly_forecast() -> list[dict]:
    """
    Hourly (2-day) wind forecast: points → forecastHourly URL → periods.
    """
    points_url = f"https://api.weather.gov/points/{LOCATION_LAT},{LOCATION_LON}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        points = await _nws_get(client, points_url)
        hourly_url = points.get("properties", {}).get("forecastHourly")
        if not hourly_url:
            return []
        data = await _nws_get(client, hourly_url)
    periods = data.get("properties", {}).get("periods", [])[:48]  # 2 days
    return [
        {
            "startTime": p.get("startTime"),
            "endTime": p.get("endTime"),
            "temp": p.get("temperature"),
            "windSpeed": p.get("windSpeed"),
            "windGust": p.get("windGust"),
            "shortForecast": p.get("shortForecast"),
            "windDirection": p.get("windDirection"),
        }
        for p in periods
    ]


async def get_alerts() -> list[dict]:
    """
    Active weather alerts for the location (e.g. small craft advisories).
    GET alerts/active?point=lat,lon
    """
    url = f"https://api.weather.gov/alerts/active?point={LOCATION_LAT},{LOCATION_LON}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        data = await _nws_get(client, url)
    features = data.get("features", [])
    return [
        {
            "event": f.get("properties", {}).get("event"),
            "severity": f.get("properties", {}).get("severity"),
            "headline": f.get("properties", {}).get("headline"),
            "description": (f.get("properties", {}).get("description") or "")[:500],
            "onset": f.get("properties", {}).get("onset"),
            "ends": f.get("properties", {}).get("ends"),
        }
        for f in features
    ]


async def get_marine_forecast() -> dict:
    """
    Fetch NWS marine zone forecast text-only from marine.weather.gov/MapClick.php?TextType=1&zoneid=ANZ535.
    Returns zone name and clean forecast text (winds, waves, visibility, etc.).
    """
    url = f"https://marine.weather.gov/MapClick.php?TextType=1&zoneid={MARINE_ZONE_ID}"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": NWS_USER_AGENT, "Accept": "text/html"},
            )
            resp.raise_for_status()
            html = resp.text
    except Exception:
        return {"zone_id": MARINE_ZONE_ID, "name": "", "forecast_text": "", "error": "Could not load marine forecast.", "url": url}

    name = "Tidal Potomac from Key Bridge to Indian Head MD"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            z = await _nws_get(client, f"https://api.weather.gov/zones/marine/{MARINE_ZONE_ID}")
            name = z.get("properties", {}).get("name") or name
    except Exception:
        pass

    # Text-only page: forecast is in a table cell containing "TODAY" / "TONIGHT". Extract and clean.
    forecast_text = ""
    # Find the <td> that contains the forecast (has period labels like TODAY, TONIGHT)
    for m in re.finditer(r"<td[^>]*>(.*?)</td>", html, re.DOTALL | re.IGNORECASE):
        cell = m.group(1)
        if "TODAY" in cell.upper() and ("TONIGHT" in cell.upper() or "kt" in cell):
            block = re.sub(r"<[^>]+>", " ", cell)
            block = block.replace("&nbsp;", " ").replace("&#160;", " ")
            block = re.sub(r"\s+", " ", block).strip()
            forecast_text = block[:2500] if len(block) > 2500 else block
            break
    if not forecast_text:
        block = re.sub(r"<[^>]+>", " ", html)
        block = block.replace("&nbsp;", " ").replace("&#160;", " ")
        block = re.sub(r"\s+", " ", block).strip()
        if "TODAY" in block.upper():
            idx = block.upper().find("TODAY")
            forecast_text = block[idx : idx + 2500].strip()
        else:
            forecast_text = block[:2500].strip() if block else ""

    # Restore line breaks before period labels for readability
    for label in ("TONIGHT", "THU ", "THU NIGHT", "FRI ", "FRI NIGHT", "SAT ", "SUN "):
        forecast_text = re.sub(rf"\s+({re.escape(label)})", r"\n\1", forecast_text, flags=re.IGNORECASE)

    return {
        "zone_id": MARINE_ZONE_ID,
        "name": name,
        "forecast_text": forecast_text or "Marine forecast not available.",
        "url": url,
    }


async def get_tides() -> list[dict]:
    """
    2-day tide predictions from NOAA CO-OPS (high/low).
    Station 8594900 = Washington, Potomac River DC.
    """
    now = datetime.now(timezone.utc)
    begin = now.strftime("%Y%m%d")
    end = (now + timedelta(days=2)).strftime("%Y%m%d")
    url = (
        "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
        f"?product=predictions&station={NOAA_TIDE_STATION}&datum=MLLW"
        f"&units=english&time_zone=lst_ldt&format=json"
        f"&begin_date={begin}&end_date={end}&interval=hilo"
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    predictions = data.get("predictions", [])
    return [
        {"t": p.get("t"), "v": p.get("v"), "type": p.get("type")}
        for p in predictions
    ]


async def get_all_weather_data() -> dict:
    """
    Fetch location, 3-day forecast, hourly wind, alerts, marine forecast, and tides in one place.
    """
    import asyncio
    loc = get_location()
    forecast_3day, hourly, alerts, marine, tides = await asyncio.gather(
        get_points_forecast(),
        get_hourly_forecast(),
        get_alerts(),
        get_marine_forecast(),
        get_tides(),
    )
    return {
        "location": loc,
        "forecast_3day": forecast_3day,
        "hourly": hourly,
        "alerts": alerts,
        "marine_forecast": marine,
        "tides": tides,
    }
