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
from app.services.report_builder import report_builder
from app.services.weather_brief import write_weather_brief

logger = logging.getLogger("sailcast.scheduler")

scheduler = AsyncIOScheduler()


async def refresh_all_data():
    """Fetch all NWS data, build report, derive brief, and generate AI summary."""
    logger.info("=== Scheduled data refresh starting ===")
    try:
        # 1. Fetch gridpoint gust data first (needed to enrich hourly periods)
        await nws_service.fetch_gridpoint_gusts()

        # 2. Fetch NWS + marine + tides concurrently (results cached by each service)
        await asyncio.gather(
            nws_service.fetch_hourly_forecast(),
            nws_service.fetch_7day_forecast(),
            nws_service.fetch_alerts(),
            marine_service.fetch_marine_forecast(),
            marine_service.fetch_tides(),
        )

        # 3. Build report.json (single source of truth for the frontend)
        report = report_builder.build_report()

        # 4. Derive the weather brief from the report (daytime-only .md for the LLM)
        weather_brief = write_weather_brief(report)

        # 5. Generate AI summary from the brief
        await openai_service.generate_summary(weather_brief)

        logger.info("=== Scheduled data refresh complete ===")

    except Exception as e:
        logger.error(f"Scheduled refresh failed: {e}")


def start_scheduler():
    """Start the hourly scheduler."""
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
