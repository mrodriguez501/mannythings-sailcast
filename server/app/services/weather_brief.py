"""
Weather Brief Builder

Derives a filtered, daytime-only markdown brief from the prepared report
dict (built by report_builder). Written to disk every hour *before* the
OpenAI call so the AI always sees fresh data.

Output: server/app/data/weather_brief.md
"""

import logging
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger("sailcast.brief")

LOCAL_TZ = ZoneInfo("America/New_York")
BRIEF_PATH = Path(__file__).resolve().parent.parent / "data" / "weather_brief.md"
DAYTIME_START = 8  # 8 AM local
DAYTIME_END = 20  # 8 PM local


def _wind_mph(wind_str: str | None) -> int | None:
    """Extract numeric mph from strings like '15 mph' or '10 to 15 mph'."""
    if not wind_str:
        return None
    nums = re.findall(r"\d+", wind_str)
    return int(nums[-1]) if nums else None


def _format_hour(dt: datetime) -> str:
    h = dt.hour % 12 or 12
    suffix = "AM" if dt.hour < 12 else "PM"
    return f"{h}{suffix}"


def _filter_daytime_periods(periods: list[dict]) -> list[tuple[datetime, dict]]:
    """Return (local_dt, period) tuples for daytime hours within next 24h."""
    now_utc = datetime.now(UTC)
    cutoff = now_utc + timedelta(hours=24)
    results: list[tuple[datetime, dict]] = []

    for p in periods:
        try:
            dt = datetime.fromisoformat(p.get("startTime", ""))
        except (ValueError, TypeError):
            continue
        if dt.astimezone(UTC) > cutoff:
            continue
        dt_local = dt.astimezone(LOCAL_TZ)
        if dt_local.hour < DAYTIME_START or dt_local.hour >= DAYTIME_END:
            continue
        results.append((dt_local, p))

    return results


def _peak_conditions(daytime: list[tuple[datetime, dict]]) -> dict:
    """Compute peak wind, gust, and temp range across daytime periods."""
    max_wind = 0
    max_wind_hour = ""
    max_gust = 0
    max_gust_hour = ""
    temps: list[int] = []

    for dt_local, p in daytime:
        hour_label = _format_hour(dt_local)

        w = _wind_mph(p.get("windSpeed"))
        if w and w > max_wind:
            max_wind = w
            max_wind_hour = hour_label

        g = _wind_mph(p.get("windGust"))
        if g and g > max_gust:
            max_gust = g
            max_gust_hour = hour_label

        t = p.get("temp")
        if isinstance(t, (int, float)):
            temps.append(int(t))

    return {
        "max_wind": max_wind,
        "max_wind_hour": max_wind_hour,
        "max_gust": max_gust,
        "max_gust_hour": max_gust_hour,
        "temp_lo": min(temps) if temps else None,
        "temp_hi": max(temps) if temps else None,
    }


def build_weather_brief(report: dict) -> str:
    """Build a structured markdown weather brief from the report dict.

    Only includes daytime periods (8 AM - 8 PM ET) within the next 24 hours.
    The report dict is the same shape produced by report_builder.build_report().
    """
    now = datetime.now(LOCAL_TZ)

    hourly = report.get("hourly", [])
    forecast_3day = report.get("forecast_3day", [])
    alerts = report.get("alerts", [])
    marine = report.get("marine_forecast")
    tides = report.get("tides", [])

    lines: list[str] = [
        "# SailCast Weather Brief",
        f"Generated: {now.strftime('%Y-%m-%d %I:%M %p %Z')}",
        "Coverage: Daytime only (8 AM - 8 PM ET), next 24 hours",
        "",
    ]

    # ── Active Alerts ─────────────────────────────────────────────
    lines.append("## Active Alerts")
    if alerts:
        for a in alerts:
            lines.append(
                f"- **{a.get('event', 'Unknown')}** | Severity: {a.get('severity', 'N/A')} | {a.get('headline', '')}"
            )
    else:
        lines.append("- None")
    lines.append("")

    # ── Marine Advisories (advisory names + time windows only) ────
    lines.append("## Marine Advisories")
    if marine:
        advisories = marine.get("advisories", [])
        if advisories:
            for a in advisories:
                onset = a.get("onset", "N/A")
                ends = a.get("ends", "N/A")
                lines.append(f"- **{a.get('label', 'Unknown')}**: onset {onset}, ends {ends}")
        else:
            lines.append("- None")
    else:
        lines.append("- Marine data not available.")
    lines.append("")

    # ── Peak Conditions ───────────────────────────────────────────
    daytime: list[tuple[datetime, dict]] = []
    if hourly:
        daytime = _filter_daytime_periods(hourly)

    if daytime:
        pk = _peak_conditions(daytime)
        lines.append("## Peak Conditions (8 AM - 8 PM)")
        lines.append(f"- **Max sustained wind:** {pk['max_wind']} mph at {pk['max_wind_hour']}")
        if pk["max_gust"]:
            lines.append(f"- **Max gust:** {pk['max_gust']} mph at {pk['max_gust_hour']}")
        else:
            lines.append("- **Max gust:** None forecast")
        if pk["temp_lo"] is not None:
            lines.append(f"- **Temperature range:** {pk['temp_lo']}-{pk['temp_hi']}°F")
        lines.append("")

    # ── Hourly Table ──────────────────────────────────────────────
    lines.append("## Hourly Wind & Weather (8 AM - 8 PM)")
    if daytime:
        lines.append("")
        lines.append("| Hour | Wind | Gust | Direction | Temp | Forecast |")
        lines.append("|------|------|------|-----------|------|----------|")
        for dt_local, p in daytime:
            hour = _format_hour(dt_local)
            wind = p.get("windSpeed", "—")
            gust = p.get("windGust") or "—"
            direction = p.get("windDirection", "—")
            temp_val = p.get("temp", "—")
            unit = p.get("temperatureUnit", "F")
            temp = f"{temp_val}°{unit}"
            forecast = p.get("shortForecast", "—")
            lines.append(f"| {hour} | {wind} | {gust} | {direction} | {temp} | {forecast} |")
    else:
        lines.append("No daytime periods available in the next 24 hours.")
    lines.append("")

    # ── Tides ─────────────────────────────────────────────────────
    lines.append("## Tides")
    if tides:
        for t in tides[:8]:
            time_str = t.get("t", "")
            value = t.get("v", "")
            tide_type = "High" if t.get("type") == "H" else "Low"
            lines.append(f"- {time_str} — {tide_type}: {value} ft")
    else:
        lines.append("Tide data not available.")
    lines.append("")

    # ── 3-Day Outlook ─────────────────────────────────────────────
    lines.append("## 3-Day Outlook")
    if forecast_3day:
        for p in forecast_3day[:6]:
            name = p.get("name", "")
            wind = p.get("windSpeed", "")
            direction = p.get("windDirection", "")
            forecast = p.get("shortForecast", "")
            temp_val = p.get("temp", "")
            if name:
                lines.append(f"- **{name}**: {forecast}, {temp_val}°F, wind {wind} {direction}")
    else:
        lines.append("Extended forecast not available.")
    lines.append("")

    return "\n".join(lines)


def write_weather_brief(report: dict) -> str:
    """Build the weather brief from the report dict, write to disk, return content."""
    content = build_weather_brief(report)
    try:
        BRIEF_PATH.parent.mkdir(parents=True, exist_ok=True)
        BRIEF_PATH.write_text(content, encoding="utf-8")
        logger.info(f"Weather brief written to {BRIEF_PATH}")
    except Exception as e:
        logger.error(f"Failed to write weather brief: {e}")
    return content
