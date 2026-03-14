"""
Test Scenario API Routes

Serves mock /api/report payloads for different weather scenarios so
the frontend can be visually tested without live NWS data.

  GET /api/test/scenarios          → list available scenario names
  GET /api/test/report/{scenario}  → mock report JSON (same shape as /api/report)
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/test", tags=["test"])

LOCAL_TZ = ZoneInfo("America/New_York")


# ── helpers ───────────────────────────────────────────────────────

def _hourly(
    winds: list[int],
    gusts: list[int | None],
    temps: list[int],
    dirs: list[str] | None = None,
    forecasts: list[str] | None = None,
    start_hour: int = 6,
) -> list[dict]:
    now = datetime.now(LOCAL_TZ).replace(hour=start_hour, minute=0, second=0, microsecond=0)
    out = []
    for i in range(len(winds)):
        dt = now + timedelta(hours=i)
        out.append({
            "startTime": dt.isoformat(),
            "temp": temps[min(i, len(temps) - 1)],
            "temperatureUnit": "F",
            "windSpeed": f"{winds[i]} mph",
            "windDirection": (dirs or ["SW"] * len(winds))[min(i, len(dirs or winds) - 1)],
            "windGust": f"{gusts[i]} mph" if gusts[i] else None,
            "shortForecast": (forecasts or ["Sunny"] * len(winds))[min(i, len(forecasts or winds) - 1)],
        })
    return out


def _3day(entries: list[tuple[str, str, int, str]]) -> list[dict]:
    now = datetime.now(LOCAL_TZ).replace(hour=8, minute=0, second=0, microsecond=0)
    return [
        {
            "name": name,
            "startTime": (now + timedelta(days=i // 2)).isoformat(),
            "temp": temp,
            "windSpeed": wind,
            "windDirection": "SW",
            "shortForecast": fc,
        }
        for i, (name, fc, temp, wind) in enumerate(entries)
    ]


def _tides() -> list[dict]:
    now = datetime.now(LOCAL_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return [
        {"t": (now + timedelta(hours=h, minutes=m)).strftime("%Y-%m-%d %H:%M"), "v": v, "type": tp}
        for h, m, v, tp in [
            (5, 25, "2.22", "H"), (11, 42, "0.32", "L"),
            (17, 34, "2.43", "H"), (24, 33, "0.30", "L"),
        ]
    ]


def _location() -> dict:
    return {"label": "Potomac River, Washington DC (TEST)", "name": "LWX 97,74", "lat": "74", "lon": "97"}


DEFAULT_3DAY = _3day([
    ("Saturday", "Mostly Sunny", 65, "10 to 15 mph"),
    ("Sunday", "Partly Cloudy", 62, "8 to 12 mph"),
    ("Monday", "Sunny", 68, "6 to 10 mph"),
])


def _report(
    hourly, alerts=None, marine_advisories=None, recommendation="", advice=None,
) -> dict:
    marine = {
        "zone_id": "ANZ535",
        "name": "Tidal Potomac from Key Bridge to Indian Head MD",
        "advisories": marine_advisories or [],
        "periods": [],
        "parse_ok": True,
        "url": "https://marine.weather.gov/MapClick.php?TextType=1&zoneid=ANZ535",
    }
    return {
        "location": _location(),
        "forecast_3day": DEFAULT_3DAY,
        "hourly": hourly,
        "alerts": alerts or [],
        "marine_forecast": marine,
        "tides": _tides(),
        "recommendation": recommendation or "Test scenario — no AI recommendation.",
        **({"advice": advice} if advice else {}),
    }


# ── scenarios ─────────────────────────────────────────────────────

def _calm_day():
    winds = [5, 6, 7, 8, 8, 9, 10, 10, 9, 8, 7, 6, 5, 4, 4, 3, 3, 3, 2, 2, 2, 2, 2, 2]
    gusts = [None] * 24
    temps = [58, 59, 60, 62, 64, 66, 68, 70, 71, 72, 71, 70, 68, 66, 64, 62, 60, 58, 56, 55, 54, 53, 52, 51]
    return _report(
        hourly=_hourly(winds, gusts, temps, forecasts=["Sunny"] * 12 + ["Partly Cloudy"] * 12),
        advice={
            "safetyLevel": "SAFE",
            "summary": "Light winds and clear skies. Perfect day for sailing.",
            "advisory": "All boats cleared for sailing. No restrictions.",
            "keyConcerns": [],
            "sailingWindows": {
                "cruisingBoats": "8AM–8PM (winds well below 29 mph)",
                "daysailers": "8AM–8PM (winds well below 23 mph)",
                "reefRequired": "None",
            },
            "generatedAt": datetime.now(LOCAL_TZ).isoformat(),
            "model": "test-scenario",
        },
    )


def _high_winds():
    winds = [18, 22, 26, 30, 32, 34, 33, 31, 28, 25, 22, 18, 15, 12, 10, 8, 8, 7, 6, 6, 5, 5, 5, 5]
    gusts = [25, 30, 35, 40, 42, 45, 44, 40, 36, 32, 28, 24, 20, 16, 14, 12, 10, 10, 8, 8, 7, 7, 7, 7]
    temps = [52, 54, 56, 58, 60, 62, 63, 62, 60, 58, 56, 54, 52, 50, 48, 46, 44, 43, 42, 41, 40, 40, 39, 39]
    return _report(
        hourly=_hourly(winds, gusts, temps,
                       dirs=["SW"] * 8 + ["W"] * 8 + ["NW"] * 8,
                       forecasts=["Mostly Cloudy"] * 6 + ["Windy"] * 6 + ["Partly Cloudy"] * 12),
        advice={
            "safetyLevel": "UNSAFE",
            "summary": "Dangerous wind conditions. Sustained winds 30+ mph with gusts to 45 mph through midday.",
            "advisory": "UNSAFE — All boats must stay docked. Winds far exceed the 29 mph maximum.",
            "keyConcerns": ["Sustained winds exceed 29 mph", "Gusts to 45 mph", "No safe sailing window"],
            "sailingWindows": {
                "cruisingBoats": "None — winds exceed 29 mph",
                "daysailers": "None — winds exceed 23 mph",
                "reefRequired": "N/A",
            },
            "generatedAt": datetime.now(LOCAL_TZ).isoformat(),
            "model": "test-scenario",
        },
    )


def _moderate_winds():
    winds = [8, 10, 14, 17, 19, 21, 22, 20, 18, 15, 12, 10, 8, 7, 6, 5, 5, 5, 4, 4, 4, 3, 3, 3]
    gusts = [12, 15, 18, 22, 24, 26, 28, 26, 23, 20, 16, 14, 12, 10, 8, 7, 7, 7, 6, 6, 6, 5, 5, 5]
    temps = [60, 62, 64, 66, 68, 70, 72, 73, 72, 70, 68, 66, 64, 62, 60, 58, 57, 56, 55, 54, 53, 52, 51, 50]
    return _report(
        hourly=_hourly(winds, gusts, temps, forecasts=["Partly Cloudy"] * 12 + ["Mostly Cloudy"] * 12),
        advice={
            "safetyLevel": "CAUTION",
            "summary": "Moderate winds building midday to 22 mph with gusts to 28 mph. Morning is calm.",
            "advisory": "CAUTION — Daysailers must reef 10AM–3PM. Cruising boats OK all day.",
            "keyConcerns": ["Gusts exceed 23 mph midday", "Daysailers restricted 10AM–3PM"],
            "sailingWindows": {
                "cruisingBoats": "8AM–8PM (winds stay below 29 mph)",
                "daysailers": "8AM–10AM, 4PM–8PM (winds below 23 mph)",
                "reefRequired": "10AM–3PM (winds 17–23 mph, reef + lagoon + PFDs)",
            },
            "generatedAt": datetime.now(LOCAL_TZ).isoformat(),
            "model": "test-scenario",
        },
    )


def _small_craft_advisory():
    now = datetime.now(LOCAL_TZ)
    sca_onset = now.replace(hour=6, minute=0, second=0, microsecond=0).isoformat()
    sca_ends = now.replace(hour=18, minute=0, second=0, microsecond=0).isoformat()

    winds = [12, 14, 16, 18, 20, 22, 24, 22, 20, 18, 16, 14, 12, 10, 8, 7, 6, 6, 5, 5, 5, 5, 5, 5]
    gusts = [18, 20, 24, 28, 30, 32, 34, 30, 28, 24, 22, 18, 16, 14, 12, 10, 8, 8, 7, 7, 7, 7, 7, 7]
    temps = [50, 52, 54, 56, 58, 60, 61, 60, 58, 56, 54, 52, 50, 48, 46, 44, 43, 42, 41, 40, 40, 39, 39, 38]

    return _report(
        hourly=_hourly(winds, gusts, temps,
                       forecasts=["Breezy"] * 8 + ["Windy"] * 4 + ["Breezy"] * 4 + ["Partly Cloudy"] * 8),
        alerts=[{
            "event": "Small Craft Advisory",
            "severity": "Moderate",
            "headline": "Small Craft Advisory until 6 PM EDT",
            "onset": sca_onset,
            "ends": sca_ends,
        }],
        marine_advisories=[{
            "label": "Small Craft Advisory",
            "url": "",
            "headline": "Small Craft Advisory until 6 PM EDT",
            "description": "Winds 20 to 25 kt with gusts to 35 kt expected.",
            "instruction": "Inexperienced mariners should avoid navigating in these conditions.",
            "onset": sca_onset,
            "ends": sca_ends,
        }],
        advice={
            "safetyLevel": "UNSAFE",
            "summary": "Small Craft Advisory in effect. Winds 20–24 mph with gusts to 34 mph.",
            "advisory": "UNSAFE — Small Craft Advisory active. No SCOW boats may leave the dock.",
            "keyConcerns": ["Small Craft Advisory in effect", "Gusts to 34 mph", "Club rules prohibit sailing during SCA"],
            "sailingWindows": {
                "cruisingBoats": "None — Small Craft Advisory in effect",
                "daysailers": "None — Small Craft Advisory in effect",
                "reefRequired": "N/A",
            },
            "generatedAt": datetime.now(LOCAL_TZ).isoformat(),
            "model": "test-scenario",
        },
    )


def _thunderstorms():
    now = datetime.now(LOCAL_TZ)
    storm_onset = now.replace(hour=12, minute=0, second=0, microsecond=0).isoformat()
    storm_ends = now.replace(hour=20, minute=0, second=0, microsecond=0).isoformat()

    winds = [8, 10, 12, 14, 20, 28, 32, 25, 18, 14, 10, 8, 7, 6, 5, 5, 4, 4, 4, 3, 3, 3, 3, 3]
    gusts = [12, 14, 18, 22, 30, 40, 45, 35, 25, 20, 15, 12, 10, 8, 7, 7, 6, 6, 6, 5, 5, 5, 5, 5]
    temps = [72, 74, 76, 78, 80, 78, 72, 68, 66, 64, 62, 60, 58, 57, 56, 55, 54, 53, 52, 51, 50, 49, 48, 47]

    return _report(
        hourly=_hourly(winds, gusts, temps,
                       forecasts=(["Partly Cloudy"] * 4 + ["Mostly Cloudy"] * 2 +
                                  ["Thunderstorms"] * 4 + ["Showers And Thunderstorms"] * 2 +
                                  ["Mostly Cloudy"] * 4 + ["Partly Cloudy"] * 8)),
        alerts=[{
            "event": "Severe Thunderstorm Watch",
            "severity": "Severe",
            "headline": "Severe Thunderstorm Watch until 8 PM EDT",
            "onset": storm_onset,
            "ends": storm_ends,
        }],
        advice={
            "safetyLevel": "UNSAFE",
            "summary": "Severe thunderstorms with lightning expected 12–4 PM. Winds gusting to 45 mph during storms.",
            "advisory": "UNSAFE — DO NOT SAIL. Lightning and severe thunderstorms forecast. All boats must stay docked.",
            "keyConcerns": [
                "Severe Thunderstorm Watch active",
                "Lightning expected 12–4 PM",
                "Gusts to 45 mph during storms",
                "Club rules: DO NOT SAIL in lightning",
            ],
            "sailingWindows": {
                "cruisingBoats": "8AM–10AM only (storms arrive by noon)",
                "daysailers": "8AM–10AM only (storms arrive by noon)",
                "reefRequired": "N/A — sailing not recommended",
            },
            "generatedAt": datetime.now(LOCAL_TZ).isoformat(),
            "model": "test-scenario",
        },
    )


def _mixed_day():
    winds = [5, 6, 8, 10, 12, 15, 18, 20, 21, 19, 16, 12, 9, 7, 6, 5, 5, 4, 4, 3, 3, 3, 3, 3]
    gusts = [8, 9, 12, 14, 16, 20, 24, 26, 28, 25, 21, 16, 12, 10, 8, 7, 7, 6, 6, 5, 5, 5, 5, 5]
    temps = [60, 62, 64, 66, 68, 72, 75, 77, 78, 76, 74, 70, 68, 66, 64, 62, 60, 58, 57, 56, 55, 54, 53, 52]

    return _report(
        hourly=_hourly(winds, gusts, temps,
                       forecasts=["Sunny"] * 6 + ["Partly Cloudy"] * 6 + ["Mostly Cloudy"] * 6 + ["Partly Cloudy"] * 6),
        advice={
            "safetyLevel": "CAUTION",
            "summary": "Calm morning building to 21 mph by 2 PM with gusts to 28 mph, easing by evening.",
            "advisory": "CAUTION — Morning is ideal. Afternoon requires caution for daysailers.",
            "keyConcerns": ["Afternoon winds exceed 17 mph", "Gusts to 28 mph at 2 PM"],
            "sailingWindows": {
                "cruisingBoats": "8AM–8PM (winds stay below 29 mph all day)",
                "daysailers": "8AM–11AM unrestricted, 5PM–8PM unrestricted",
                "reefRequired": "11AM–5PM (winds 17–21 mph, reef + lagoon + PFDs)",
            },
            "generatedAt": datetime.now(LOCAL_TZ).isoformat(),
            "model": "test-scenario",
        },
    )


SCENARIOS = {
    "calm_day": ("Calm Day — SAFE", _calm_day),
    "high_winds": ("High Winds — UNSAFE", _high_winds),
    "moderate_winds": ("Moderate Winds — CAUTION", _moderate_winds),
    "small_craft_advisory": ("Small Craft Advisory — UNSAFE", _small_craft_advisory),
    "thunderstorms": ("Thunderstorms & Lightning — UNSAFE", _thunderstorms),
    "mixed_day": ("Mixed Day (morning calm, afternoon windy)", _mixed_day),
}


# ── routes ────────────────────────────────────────────────────────

@router.get("/scenarios")
async def list_scenarios():
    return [{"id": k, "label": v[0]} for k, v in SCENARIOS.items()]


@router.get("/report/{scenario}")
async def test_report(scenario: str):
    entry = SCENARIOS.get(scenario)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {scenario}")
    _, builder = entry
    return builder()
