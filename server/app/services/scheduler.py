"""
Scheduler Service
Runs hourly jobs to fetch NWS data and generate AI summaries.
Uses APScheduler for reliable cron-like scheduling.
"""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.marine_service import marine_service
from app.services.nws_service import nws_service
from app.services.openai_service import openai_service
from app.services.weather_brief import write_weather_brief

logger = logging.getLogger("sailcast.scheduler")

scheduler = AsyncIOScheduler()


async def refresh_all_data():
    """Fetch all NWS data, marine, tides, and regenerate AI summary."""
    logger.info("=== Scheduled data refresh starting ===")
    try:
        # Fetch gridpoint gust data first (needed to enrich hourly periods)
        await nws_service.fetch_gridpoint_gusts()

        # Fetch NWS + marine + tides concurrently (results cached by each service)
        await asyncio.gather(
            nws_service.fetch_hourly_forecast(),
            nws_service.fetch_7day_forecast(),
            nws_service.fetch_alerts(),
            marine_service.fetch_marine_forecast(),
            marine_service.fetch_tides(),
        )

        # Build the weather brief file (filtered daytime data for the LLM)
        weather_brief = write_weather_brief()

        # Generate AI summary from the brief
        await openai_service.generate_summary(weather_brief)

        logger.info("=== Scheduled data refresh complete ===")

    except Exception as e:
        logger.error(f"Scheduled refresh failed: {e}")


def start_scheduler():
    """Start the hourly scheduler."""
    # Run every hour at the top of the hour
    scheduler.add_job(
        refresh_all_data,
        trigger=CronTrigger(minute=0),
        id="hourly_refresh",
        name="Hourly NWS + AI refresh",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started: refreshing every hour at :00")


def stop_scheduler():
    """Gracefully stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
