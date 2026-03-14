"""
Weather Brief Scenario Tests

Generates weather_brief.md for 6 different weather scenarios by injecting
mock data into the service caches. Run from the server/ directory:

    python -m tests.test_weather_scenarios

Each scenario writes to server/app/data/test_briefs/<scenario_name>.md
so you can inspect the output side by side.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Ensure app imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.marine_service import marine_service
from app.services.nws_service import nws_service
from app.services.weather_brief import build_weather_brief

LOCAL_TZ = ZoneInfo("America/New_York")
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "test_briefs"


def _make_hourly_periods(
    wind_speeds: list[int],
    gusts: list[int | None],
    directions: list[str] | None = None,
    temps: list[int] | None = None,
    forecasts: list[str] | None = None,
    start_hour: int = 6,
) -> list[dict]:
    """Build 24 hourly period dicts starting at start_hour today (local)."""
    now_local = datetime.now(LOCAL_TZ).replace(hour=start_hour, minute=0, second=0, microsecond=0)
    periods = []
    for i in range(24):
        dt = now_local + timedelta(hours=i)
        idx = min(i, len(wind_speeds) - 1)
        gust_val = gusts[min(i, len(gusts) - 1)] if gusts else None
        periods.append({
            "startTime": dt.isoformat(),
            "endTime": (dt + timedelta(hours=1)).isoformat(),
            "temperature": (temps or [60] * 24)[min(i, len(temps or [60]) - 1)],
            "temperatureUnit": "F",
            "windSpeed": f"{wind_speeds[idx]} mph",
            "windDirection": (directions or ["SW"] * 24)[min(i, len(directions or ["SW"]) - 1)],
            "windGust": f"{gust_val} mph" if gust_val else None,
            "shortForecast": (forecasts or ["Sunny"] * 24)[min(i, len(forecasts or ["Sunny"]) - 1)],
            "isDaytime": 6 <= dt.hour < 18,
        })
    return periods


def _make_7day(names_and_forecasts: list[tuple[str, str, int, str]]) -> dict:
    now = datetime.now(LOCAL_TZ).replace(hour=8, minute=0, second=0, microsecond=0)
    periods = []
    for i, (name, forecast, temp, wind) in enumerate(names_and_forecasts):
        dt = now + timedelta(days=i // 2)
        periods.append({
            "name": name,
            "startTime": dt.isoformat(),
            "temperature": temp,
            "temperatureUnit": "F",
            "windSpeed": wind,
            "windDirection": "SW",
            "shortForecast": forecast,
            "detailedForecast": forecast,
            "isDaytime": i % 2 == 0,
        })
    return {"periods": periods, "fetchedAt": datetime.now(LOCAL_TZ).isoformat()}


def _make_tides() -> list:
    now = datetime.now(LOCAL_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return [
        {"t": (now + timedelta(hours=5, minutes=25)).strftime("%Y-%m-%d %H:%M"), "v": "2.22", "type": "H"},
        {"t": (now + timedelta(hours=11, minutes=42)).strftime("%Y-%m-%d %H:%M"), "v": "0.32", "type": "L"},
        {"t": (now + timedelta(hours=17, minutes=34)).strftime("%Y-%m-%d %H:%M"), "v": "2.43", "type": "H"},
        {"t": (now + timedelta(hours=24, minutes=33)).strftime("%Y-%m-%d %H:%M"), "v": "0.30", "type": "L"},
    ]


DEFAULT_7DAY = _make_7day([
    ("Saturday", "Mostly Sunny", 65, "10 to 15 mph"),
    ("Saturday Night", "Clear", 48, "5 mph"),
    ("Sunday", "Partly Cloudy", 62, "8 to 12 mph"),
    ("Sunday Night", "Mostly Clear", 50, "5 mph"),
    ("Monday", "Sunny", 68, "6 to 10 mph"),
    ("Monday Night", "Clear", 52, "5 mph"),
])


def _inject(hourly_periods, alerts=None, marine_advisories=None, seven_day=None):
    """Inject mock data into the service singletons."""
    nws_service._hourly_cache = {
        "periods": hourly_periods,
        "fetchedAt": datetime.now(LOCAL_TZ).isoformat(),
    }
    nws_service._alerts_cache = {
        "alerts": alerts or [],
        "count": len(alerts or []),
        "fetchedAt": datetime.now(LOCAL_TZ).isoformat(),
    }
    nws_service._7day_cache = seven_day or DEFAULT_7DAY

    marine_service._marine_cache = {
        "zone_id": "ANZ535",
        "name": "Tidal Potomac from Key Bridge to Indian Head MD",
        "forecast_text": "",
        "advisories": marine_advisories or [],
        "periods": [],
        "parse_ok": True,
        "url": "",
    }
    marine_service._tides_cache = _make_tides()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SCENARIOS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCENARIOS: dict[str, callable] = {}


def scenario(name):
    def decorator(fn):
        SCENARIOS[name] = fn
        return fn
    return decorator


@scenario("01_calm_day")
def _():
    """Perfect sailing day — light winds, no gusts, no alerts."""
    _inject(
        hourly_periods=_make_hourly_periods(
            wind_speeds=[5, 6, 7, 8, 8, 9, 10, 10, 9, 8, 7, 6, 5, 4, 4, 3, 3, 3, 2, 2, 2, 2, 2, 2],
            gusts=[None] * 24,
            temps=[58, 59, 60, 62, 64, 66, 68, 70, 71, 72, 71, 70, 68, 66, 64, 62, 60, 58, 56, 55, 54, 53, 52, 51],
            forecasts=["Sunny"] * 12 + ["Partly Cloudy"] * 6 + ["Clear"] * 6,
        ),
    )


@scenario("02_high_winds_unsafe")
def _():
    """Winds exceed 29 MPH — unsafe for ALL boats."""
    _inject(
        hourly_periods=_make_hourly_periods(
            wind_speeds=[18, 22, 26, 30, 32, 34, 33, 31, 28, 25, 22, 18, 15, 12, 10, 8, 8, 7, 6, 6, 5, 5, 5, 5],
            gusts=      [25, 30, 35, 40, 42, 45, 44, 40, 36, 32, 28, 24, 20, 16, 14, 12, 10, 10, 8, 8, 7, 7, 7, 7],
            temps=[52, 54, 56, 58, 60, 62, 63, 62, 60, 58, 56, 54, 52, 50, 48, 46, 44, 43, 42, 41, 40, 40, 39, 39],
            directions=["SW"] * 8 + ["W"] * 8 + ["NW"] * 8,
            forecasts=["Mostly Cloudy"] * 6 + ["Windy"] * 6 + ["Partly Cloudy"] * 6 + ["Clear"] * 6,
        ),
    )


@scenario("03_moderate_winds_caution")
def _():
    """Winds 17–23 MPH — daysailers must reef, stay in lagoon, wear PFDs."""
    _inject(
        hourly_periods=_make_hourly_periods(
            wind_speeds=[8, 10, 14, 17, 19, 21, 22, 20, 18, 15, 12, 10, 8, 7, 6, 5, 5, 5, 4, 4, 4, 3, 3, 3],
            gusts=      [12, 15, 18, 22, 24, 26, 28, 26, 23, 20, 16, 14, 12, 10, 8, 7, 7, 7, 6, 6, 6, 5, 5, 5],
            temps=[60, 62, 64, 66, 68, 70, 72, 73, 72, 70, 68, 66, 64, 62, 60, 58, 57, 56, 55, 54, 53, 52, 51, 50],
            forecasts=["Partly Cloudy"] * 12 + ["Mostly Cloudy"] * 6 + ["Partly Cloudy"] * 6,
        ),
    )


@scenario("04_small_craft_advisory")
def _():
    """Small Craft Advisory active — UNSAFE, no boats allowed out."""
    now = datetime.now(LOCAL_TZ)
    sca_onset = now.replace(hour=6, minute=0, second=0, microsecond=0).isoformat()
    sca_ends = now.replace(hour=18, minute=0, second=0, microsecond=0).isoformat()

    _inject(
        hourly_periods=_make_hourly_periods(
            wind_speeds=[12, 14, 16, 18, 20, 22, 24, 22, 20, 18, 16, 14, 12, 10, 8, 7, 6, 6, 5, 5, 5, 5, 5, 5],
            gusts=      [18, 20, 24, 28, 30, 32, 34, 30, 28, 24, 22, 18, 16, 14, 12, 10, 8, 8, 7, 7, 7, 7, 7, 7],
            temps=[50, 52, 54, 56, 58, 60, 61, 60, 58, 56, 54, 52, 50, 48, 46, 44, 43, 42, 41, 40, 40, 39, 39, 38],
            forecasts=["Breezy"] * 8 + ["Windy"] * 4 + ["Breezy"] * 4 + ["Partly Cloudy"] * 8,
        ),
        alerts=[
            {
                "event": "Small Craft Advisory",
                "headline": f"Small Craft Advisory until 6 PM EDT",
                "description": "Winds 20 to 25 kt with gusts to 35 kt expected.",
                "severity": "Moderate",
                "urgency": "Expected",
                "onset": sca_onset,
                "expires": sca_ends,
            }
        ],
        marine_advisories=[
            {
                "label": "Small Craft Advisory",
                "url": "",
                "headline": f"Small Craft Advisory until 6 PM EDT",
                "description": "Winds 20 to 25 kt with gusts to 35 kt expected.",
                "instruction": "Inexperienced mariners should avoid navigating in these conditions.",
                "onset": sca_onset,
                "ends": sca_ends,
            }
        ],
    )


@scenario("05_thunderstorms_lightning")
def _():
    """Thunderstorms with lightning in the forecast — DO NOT SAIL."""
    now = datetime.now(LOCAL_TZ)
    storm_onset = now.replace(hour=12, minute=0, second=0, microsecond=0).isoformat()
    storm_ends = now.replace(hour=20, minute=0, second=0, microsecond=0).isoformat()

    _inject(
        hourly_periods=_make_hourly_periods(
            wind_speeds=[8, 10, 12, 14, 20, 28, 32, 25, 18, 14, 10, 8, 7, 6, 5, 5, 4, 4, 4, 3, 3, 3, 3, 3],
            gusts=      [12, 14, 18, 22, 30, 40, 45, 35, 25, 20, 15, 12, 10, 8, 7, 7, 6, 6, 6, 5, 5, 5, 5, 5],
            temps=[72, 74, 76, 78, 80, 78, 72, 68, 66, 64, 62, 60, 58, 57, 56, 55, 54, 53, 52, 51, 50, 49, 48, 47],
            forecasts=(
                ["Partly Cloudy"] * 4
                + ["Mostly Cloudy"] * 2
                + ["Thunderstorms"] * 4
                + ["Showers And Thunderstorms"] * 2
                + ["Mostly Cloudy"] * 4
                + ["Partly Cloudy"] * 8
            ),
        ),
        alerts=[
            {
                "event": "Severe Thunderstorm Watch",
                "headline": "Severe Thunderstorm Watch until 8 PM EDT",
                "description": "Conditions are favorable for severe thunderstorms with damaging winds and frequent lightning.",
                "severity": "Severe",
                "urgency": "Expected",
                "onset": storm_onset,
                "expires": storm_ends,
            }
        ],
    )


@scenario("06_mixed_day_window")
def _():
    """Morning is calm (SAFE), afternoon picks up (CAUTION/reef), evening calms.
    Tests whether the brief clearly shows a shifting sailing window."""
    _inject(
        hourly_periods=_make_hourly_periods(
            wind_speeds=[5, 6, 8, 10, 12, 15, 18, 20, 21, 19, 16, 12, 9, 7, 6, 5, 5, 4, 4, 3, 3, 3, 3, 3],
            gusts=      [8, 9, 12, 14, 16, 20, 24, 26, 28, 25, 21, 16, 12, 10, 8, 7, 7, 6, 6, 5, 5, 5, 5, 5],
            temps=[60, 62, 64, 66, 68, 72, 75, 77, 78, 76, 74, 70, 68, 66, 64, 62, 60, 58, 57, 56, 55, 54, 53, 52],
            forecasts=["Sunny"] * 6 + ["Partly Cloudy"] * 6 + ["Mostly Cloudy"] * 6 + ["Partly Cloudy"] * 6,
        ),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RUNNER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_all():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for name, setup_fn in SCENARIOS.items():
        setup_fn()
        brief = build_weather_brief()
        out_path = OUTPUT_DIR / f"{name}.md"
        out_path.write_text(brief, encoding="utf-8")
        print(f"  ✓ {name} → {out_path.relative_to(OUTPUT_DIR.parent.parent)}")

    print(f"\nAll {len(SCENARIOS)} scenarios written to {OUTPUT_DIR.relative_to(OUTPUT_DIR.parent.parent.parent)}/")


if __name__ == "__main__":
    run_all()
