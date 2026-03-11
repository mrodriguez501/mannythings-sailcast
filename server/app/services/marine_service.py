"""
Marine forecast (NWS) and tide predictions (NOAA CO-OPS).
Caches results for the report API.
"""
import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger("sailcast.marine")


def _parse_marine_html(html: str) -> str:
    """Extract and clean forecast text from NWS marine zone HTML."""
    text = ""
    for m in re.finditer(r"<td[^>]*>(.*?)</td>", html, re.DOTALL | re.IGNORECASE):
        cell = m.group(1)
        if "TODAY" in cell.upper() and ("TONIGHT" in cell.upper() or "kt" in cell):
            block = re.sub(r"<[^>]+>", " ", cell)
            block = block.replace("&nbsp;", " ").replace("&#160;", " ")
            block = re.sub(r"\s+", " ", block).strip()
            text = block[:2500]
            break
    if not text:
        block = re.sub(r"<[^>]+>", " ", html)
        block = block.replace("&nbsp;", " ").replace("&#160;", " ")
        block = re.sub(r"\s+", " ", block).strip()
        if "TODAY" in block.upper():
            idx = block.upper().find("TODAY")
            text = block[idx : idx + 2500].strip()
        else:
            text = block[:2500].strip() if block else ""
    for label in ("TONIGHT", "THU ", "THU NIGHT", "FRI ", "FRI NIGHT", "SAT ", "SUN "):
        text = re.sub(rf"\s+({re.escape(label)})", r"\n\1", text, flags=re.IGNORECASE)
    return text


class MarineService:
    def __init__(self):
        self._marine_cache: Optional[dict] = None
        self._tides_cache: Optional[list] = None

    def _headers(self) -> dict:
        return {"User-Agent": settings.NWS_USER_AGENT}

    async def fetch_marine_forecast(self) -> dict:
        """Fetch NWS marine zone forecast text (ANZ535 = Tidal Potomac)."""
        zone_id = settings.MARINE_ZONE_ID
        url = f"https://marine.weather.gov/MapClick.php?TextType=1&zoneid={zone_id}"
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(
                    url,
                    headers={**self._headers(), "Accept": "text/html"},
                )
                resp.raise_for_status()
                html = resp.text
        except Exception as e:
            logger.warning(f"Marine forecast fetch failed: {e}")
            self._marine_cache = {
                "zone_id": zone_id,
                "name": "",
                "forecast_text": "",
                "error": "Could not load marine forecast.",
                "url": url,
            }
            return self._marine_cache

        name = "Tidal Potomac from Key Bridge to Indian Head MD"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                z = await client.get(
                    f"https://api.weather.gov/zones/marine/{zone_id}",
                    headers={**self._headers(), "Accept": "application/json"},
                )
                z.raise_for_status()
                data = z.json()
                name = data.get("properties", {}).get("name") or name
        except Exception:
            pass

        forecast_text = _parse_marine_html(html)

        self._marine_cache = {
            "zone_id": zone_id,
            "name": name,
            "forecast_text": forecast_text or "Marine forecast not available.",
            "url": url,
        }
        logger.info("Marine forecast cached")
        return self._marine_cache

    async def fetch_tides(self) -> list:
        """Fetch 2-day tide predictions from NOAA CO-OPS (station 8594900 = Washington DC)."""
        station = settings.NOAA_TIDE_STATION
        now = datetime.now(timezone.utc)
        begin = now.strftime("%Y%m%d")
        end = (now + timedelta(days=2)).strftime("%Y%m%d")
        url = (
            "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
            f"?product=predictions&station={station}&datum=MLLW"
            f"&units=english&time_zone=lst_ldt&format=json"
            f"&begin_date={begin}&end_date={end}&interval=hilo"
        )
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            predictions = data.get("predictions", [])
            self._tides_cache = [
                {"t": p.get("t"), "v": p.get("v"), "type": p.get("type")}
                for p in predictions
            ]
            logger.info(f"Tides cached ({len(self._tides_cache)} points)")
            return self._tides_cache
        except Exception as e:
            logger.warning(f"Tide fetch failed: {e}")
            self._tides_cache = []
            return []

    def get_cached_marine(self) -> Optional[dict]:
        return self._marine_cache

    def get_cached_tides(self) -> Optional[list]:
        return self._tides_cache


marine_service = MarineService()
