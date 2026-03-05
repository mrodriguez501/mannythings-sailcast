"""
LLM service: weather + alerts + tides + club guidance → concise sailing recommendation.
"""
import os
import httpx

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


async def generate_report(
    *,
    forecast_3day: list[dict],
    hourly: list[dict],
    alerts: list[dict],
    tides: list[dict],
    guidance: str,
) -> str:
    """
    Call LLM with 3-day forecast, hourly wind, alerts, tides, and club rules.
    """
    if not OPENAI_API_KEY:
        return _fallback_recommendation(forecast_3day, hourly, alerts)

    # Build context
    period_lines = "\n".join(
        f"- {p.get('name', '')}: {p.get('shortForecast', '')} "
        f"Temp {p.get('temp')}°F, Wind {p.get('windSpeed')}"
        for p in forecast_3day[:6]
    )
    hourly_lines = "\n".join(
        f"- {p.get('startTime', '')}: Wind {p.get('windSpeed')} Gusts {p.get('windGust')}"
        for p in hourly[:12]
    )
    alerts_text = "None active."
    if alerts:
        alerts_text = "\n".join(
            f"- {a.get('event')} ({a.get('severity')}): {a.get('headline', '')}"
            for a in alerts
        )
    tides_preview = ", ".join(
        f"{t.get('type')} {t.get('v')} ft at {t.get('t')}" for t in tides[:6]
    ) if tides else "No tide data"

    prompt = f"""You are a sailing club forecaster. Given the location's 3-day forecast, hourly wind, any active weather alerts (e.g. small craft advisories), tide predictions, and club rules, write a brief (2–4 sentence) sailing recommendation.

Club rules:
{guidance[:2000]}

3-day forecast:
{period_lines}

Hourly wind (next 12h):
{hourly_lines}

Active alerts:
{alerts_text}

Tides (next 2 days): {tides_preview}

Reply with only the recommendation, no preamble."""

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENAI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
            },
        )
        if resp.status_code != 200:
            return _fallback_recommendation(forecast_3day, hourly, alerts)
        data = resp.json()
        choice = data.get("choices", [{}])[0]
        content = (choice.get("message", {}).get("content") or "").strip()
        return content or _fallback_recommendation(forecast_3day, hourly, alerts)


def _fallback_recommendation(
    forecast_3day: list[dict],
    hourly: list[dict],
    alerts: list[dict],
) -> str:
    """When LLM is unavailable."""
    parts = []
    if alerts:
        parts.append(f"Active alerts: {', '.join(a.get('event', '') for a in alerts)}. ")
    if hourly:
        p = hourly[0]
        parts.append(
            f"Current: Wind {p.get('windSpeed', 'N/A')}, Gusts {p.get('windGust', 'N/A')}. "
        )
    parts.append("Check club rules and local conditions before sailing. (LLM not configured.)")
    return "".join(parts).strip()
