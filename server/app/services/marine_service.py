"""
Marine forecast (NWS) and tide predictions (NOAA CO-OPS).

Advisory/alert detection uses the reliable NWS alerts JSON API.
Forecast text comes from the NWS Text Products API (Coastal Waters
Forecast / CWF), which provides structured plaintext for each marine zone.
"""

import logging
import re
from datetime import UTC, datetime, timedelta

import httpx

from app.config import settings

logger = logging.getLogger("sailcast.marine")


def _extract_zone_block(product_text: str, zone_id: str) -> str:
    """Extract the forecast block for a specific zone from a CWF product.

    CWF products contain multiple zones separated by "$$".  Each zone block
    starts with a line like "ANZ535-140800-" and ends at the next "$$".
    """
    pattern = re.compile(
        rf"^{re.escape(zone_id)}-.*?$(.*?)^\$\$",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(product_text)
    return m.group(1).strip() if m else ""


def _parse_cwf_periods(zone_text: str) -> list[dict]:
    """Parse period forecasts from CWF plaintext for a single zone.

    Periods start with a leading dot: ".SAT...W winds 10 to 15 kt."
    Stop capturing at the next period or a blank line (trailing notes).
    """
    period_re = re.compile(r"^\.([A-Z][A-Z \t]+?)\.{3}(.+?)(?=^\.|^\s*$|\Z)", re.MULTILINE | re.DOTALL)
    periods: list[dict] = []
    for m in period_re.finditer(zone_text):
        name = m.group(1).strip()
        body = " ".join(m.group(2).split())
        if name and body:
            periods.append({"name": name, "forecast": body})
    return periods


def _parse_cwf_text(product_text: str, zone_id: str) -> dict:
    """Parse a CWF product for the target zone.

    Returns the same shape as the old HTML parser:
      - forecast_text: raw zone block text
      - periods: list of {name, forecast} dicts
      - parse_ok: True if structured periods were extracted
    """
    zone_text = _extract_zone_block(product_text, zone_id)
    if not zone_text:
        return {"forecast_text": "", "periods": [], "parse_ok": False}

    periods = _parse_cwf_periods(zone_text)
    parse_ok = len(periods) >= 2 and any("kt" in p.get("forecast", "").lower() for p in periods)

    return {"forecast_text": zone_text, "periods": periods, "parse_ok": parse_ok}


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

    async def _fetch_cwf_product(self) -> str:
        """Fetch the latest Coastal Waters Forecast product text from the NWS API."""
        list_url = settings.nws_marine_cwf_url
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(list_url, headers=self._api_headers())
            resp.raise_for_status()
            products = resp.json().get("@graph", [])

        if not products:
            logger.warning("No CWF products returned by NWS API")
            return ""

        product_url = products[0].get("@id", "")
        if not product_url:
            return ""

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(product_url, headers=self._api_headers())
            resp.raise_for_status()
            return resp.json().get("productText", "")

    async def fetch_marine_forecast(self) -> dict:
        """Fetch NWS marine zone forecast text and alerts.

        Forecast text comes from the NWS Text Products API (CWF).
        Alerts come from the reliable NWS alerts JSON API.
        """
        zone_id = settings.MARINE_ZONE_ID
        page_url = f"https://marine.weather.gov/MapClick.php?TextType=1&zoneid={zone_id}"

        marine_alerts = await self.fetch_marine_alerts()

        product_text = ""
        try:
            product_text = await self._fetch_cwf_product()
        except Exception as e:
            logger.warning(f"CWF product fetch failed: {e}")

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

        parsed = (
            _parse_cwf_text(product_text, zone_id)
            if product_text
            else {"forecast_text": "", "periods": [], "parse_ok": False}
        )

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
            logger.warning("CWF product parse failed for zone %s", zone_id)

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
