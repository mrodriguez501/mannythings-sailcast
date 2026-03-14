"""
Report API Route

Serves the cached report payload (built by report_builder) with
LLM advice merged at serve-time from the OpenAI cache.

Also provides an SSE endpoint (/api/events) that pushes notifications
when the scheduler completes a data refresh.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.services.event_bus import event_bus
from app.services.openai_service import openai_service
from app.services.report_builder import report_builder

logger = logging.getLogger("sailcast.routes.report")

router = APIRouter()

HEARTBEAT_INTERVAL_S = 30


def _build_advice(summary_data: dict | str | None) -> tuple[str, dict | None]:
    """Extract recommendation string and structured advice from OpenAI cache."""
    if summary_data and isinstance(summary_data, dict):
        summary = summary_data.get("summary", "") or summary_data.get("text", "")
        advisory = summary_data.get("advisory", "")
        recommendation = (
            f"{summary}\n\n{advisory}".strip() if (summary and advisory) else summary or advisory or str(summary_data)
        )
        advice = None
        if summary_data.get("safetyLevel"):
            advice = {
                "safetyLevel": summary_data.get("safetyLevel"),
                "summary": summary,
                "advisory": advisory,
                "keyConcerns": summary_data.get("keyConcerns", []),
                "sailingWindows": summary_data.get("sailingWindows"),
                "generatedAt": summary_data.get("generatedAt"),
                "model": summary_data.get("model"),
            }
        return recommendation, advice

    if isinstance(summary_data, str):
        return summary_data, None

    return "", None


@router.get("/report")
async def api_report():
    """Single report payload for the SailCast static UI."""
    report = report_builder.get_cached_report()
    if report is None:
        raise HTTPException(
            status_code=503,
            detail="Forecast data not yet available (scheduler may still be loading).",
        )

    recommendation, advice = _build_advice(openai_service.get_cached_summary())

    result = {**report, "recommendation": recommendation or "No recommendation available."}
    if advice:
        result["advice"] = advice
    return result


async def _sse_generator(request: Request):
    """Yield SSE-formatted messages: heartbeat pings + refresh events."""
    q = event_bus.subscribe()
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                msg = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_INTERVAL_S)
                yield f"event: {msg.get('event', 'refresh')}\ndata: {json.dumps(msg)}\n\n"
            except TimeoutError:
                yield ": heartbeat\n\n"
    finally:
        event_bus.unsubscribe(q)


@router.get("/events")
async def sse_events(request: Request):
    """Server-Sent Events stream. Pushes a 'refresh' event after each
    scheduled data update so the frontend can fetch fresh data immediately."""
    return StreamingResponse(
        _sse_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
