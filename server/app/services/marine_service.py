"""
Marine forecast (NWS) and tide predictions (NOAA CO-OPS).

Advisory/alert detection uses the reliable NWS alerts JSON API.
Forecast text (period-by-period) is scraped from the NWS marine HTML page
with a safeguard that detects format changes and falls back gracefully.
"""

import logging
import re
from datetime import UTC, datetime, timedelta

import httpx

from app.config import settings

logger = logging.getLogger("sailcast.marine")


_PERIOD_LABELS = ("TODAY", "TONIGHT", "THIS AFTERNOON", "THIS EVENING", "THIS MORNING")
_BREAK_LABELS = (
    "REST OF THIS AFTERNOON",
    "REST OF TONIGHT",
    "REST OF TODAY",
    "TONIGHT",
    "TODAY",
    "THIS AFTERNOON",
    "THIS EVENING",
    "THIS MORNING",
    "MON ",
    "MON NIGHT",
    "TUE ",
    "TUE NIGHT",
    "WED ",
    "WED NIGHT",
    "THU ",
    "THU NIGHT",
    "FRI ",
    "FRI NIGHT",
    "SAT ",
    "SAT NIGHT",
    "SUN ",
    "SUN NIGHT",
)

_MARINE_BASE_URL = "https://marine.weather.gov/"


def _strip_html(raw: str) -> str:
    """Remove script/style blocks, then HTML tags, then collapse whitespace."""
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = cleaned.replace("&nbsp;", " ").replace("&#160;", " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def _parse_forecast_periods(text: str) -> list[dict]:
    """Split cleaned forecast text into structured {name, forecast} period dicts."""
    period_re = re.compile(
        r"(?:^|\n)\s*(" + "|".join(re.escape(lbl.strip()) for lbl in _BREAK_LABELS) + r"[^:]*?):\s*",
        re.IGNORECASE,
    )
    parts = period_re.split(text)
    periods = []
    i = 1
    while i < len(parts) - 1:
        name = parts[i].strip().rstrip(":")
        body = parts[i + 1].strip()
        if name and body:
            periods.append({"name": name, "forecast": body})
        i += 2
    return periods


def _parse_marine_html(html: str) -> dict:
    """Extract forecast periods from NWS marine zone HTML.

    Returns a dict with:
      - forecast_text: raw cleaned text
      - periods: list of {name, forecast} dicts
      - parse_ok: True if we successfully extracted structured periods
    """
    text = ""
    for m in re.finditer(r"<td[^>]*>(.*?)</td>", html, re.DOTALL | re.IGNORECASE):
        cell = m.group(1)
        upper = cell.upper()
        has_period = any(lbl in upper for lbl in _PERIOD_LABELS)
        if has_period and ("kt" in cell.lower() or any(lbl in upper for lbl in _PERIOD_LABELS[1:])):
            text = _strip_html(cell)[:2500]
            break

    if not text:
        block = _strip_html(html)
        for lbl in _PERIOD_LABELS:
            idx = block.upper().find(lbl)
            if idx != -1:
                text = block[idx : idx + 2500].strip()
                break
        if not text:
            nws_marker = block.upper().find("NWS FORECAST FOR:")
            if nws_marker != -1:
                text = block[nws_marker : nws_marker + 2500].strip()

    for label in _BREAK_LABELS:
        text = re.sub(rf"\s+({re.escape(label)})", r"\n\1", text, flags=re.IGNORECASE)

    periods = _parse_forecast_periods(text)

    parse_ok = len(periods) >= 2 and any("kt" in p.get("forecast", "").lower() for p in periods)

    return {"forecast_text": text, "periods": periods, "parse_ok": parse_ok}


class MarineService:
    def __init__(self):
        self._marine_cache: dict | None = None
        self._tides_cache: list | None = None

    def _headers(self) -> dict:
        return {"User-Agent": settings.NWS_USER_AGENT}

    def _api_headers(self) -> dict:
        return {
            "User-Agent": settings.NWS_USER_AGENT,
            "Accept": "application/geo+json",
        }

    async def fetch_marine_alerts(self) -> list[dict]:
        """Fetch active marine alerts for the zone from the NWS JSON API.

        This is the reliable source for Small Craft Advisories and other
        marine warnings. Returns a list of structured alert dicts.
        """
        zone_id = settings.MARINE_ZONE_ID
        url = settings.nws_marine_alerts_url
        logger.info(f"Fetching marine alerts for zone {zone_id}...")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=self._api_headers())
                resp.raise_for_status()
                data = resp.json()

            features = data.get("features", [])
            alerts = []
            for f in features:
                props = f.get("properties", {})
                alerts.append(
                    {
                        "event": props.get("event", ""),
                        "headline": props.get("headline", ""),
                        "description": props.get("description", ""),
                        "instruction": props.get("instruction", ""),
                        "severity": props.get("severity", ""),
                        "urgency": props.get("urgency", ""),
                        "onset": props.get("onset"),
                        "ends": props.get("ends"),
                        "url": props.get("@id", ""),
                    }
                )
            logger.info(f"Marine alerts cached ({len(alerts)} active)")
            return alerts

        except Exception as e:
            logger.warning(f"Marine alerts fetch failed: {e}")
            return []

    async def fetch_marine_forecast(self) -> dict:
        """Fetch NWS marine zone forecast text and alerts.

        Forecast text is scraped from the NWS HTML page (with safeguard).
        Alerts come from the reliable JSON API.
        """
        zone_id = settings.MARINE_ZONE_ID
        page_url = f"https://marine.weather.gov/MapClick.php?TextType=1&zoneid={zone_id}"

        marine_alerts = await self.fetch_marine_alerts()

        html = ""
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(
                    page_url,
                    headers={**self._headers(), "Accept": "text/html"},
                )
                resp.raise_for_status()
                html = resp.text
        except Exception as e:
            logger.warning(f"Marine forecast HTML fetch failed: {e}")

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

        parsed = _parse_marine_html(html) if html else {"forecast_text": "", "periods": [], "parse_ok": False}

        advisories = [
            {
                "label": a["event"],
                "url": a.get("url", ""),
                "headline": a.get("headline", ""),
                "description": a.get("description", ""),
                "instruction": a.get("instruction", ""),
                "onset": a.get("onset"),
                "ends": a.get("ends"),
            }
            for a in marine_alerts
        ]

        if not parsed["parse_ok"]:
            logger.warning("Marine forecast HTML parse failed — format may have changed")

        self._marine_cache = {
            "zone_id": zone_id,
            "name": name,
            "forecast_text": parsed["forecast_text"] if parsed["parse_ok"] else "",
            "advisories": advisories,
            "periods": parsed["periods"] if parsed["parse_ok"] else [],
            "parse_ok": parsed["parse_ok"],
            "url": page_url,
        }
        logger.info(f"Marine forecast cached (parse_ok={parsed['parse_ok']}, {len(advisories)} advisories)")
        return self._marine_cache

    async def fetch_tides(self) -> list:
        """Fetch 2-day tide predictions from NOAA CO-OPS (station 8594900 = Washington DC)."""
        station = settings.NOAA_TIDE_STATION
        now = datetime.now(UTC)
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
            self._tides_cache = [{"t": p.get("t"), "v": p.get("v"), "type": p.get("type")} for p in predictions]
            logger.info(f"Tides cached ({len(self._tides_cache)} points)")
            return self._tides_cache
        except Exception as e:
            logger.warning(f"Tide fetch failed: {e}")
            self._tides_cache = []
            return []

    def get_cached_marine(self) -> dict | None:
        return self._marine_cache

    def get_cached_tides(self) -> list | None:
        return self._tides_cache


marine_service = MarineService()
