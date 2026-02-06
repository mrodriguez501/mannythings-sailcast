"""
SailCast Backend - FastAPI Application Entry Point
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes.forecast import router as forecast_router
from app.services.scheduler import (
    refresh_all_data,
    start_scheduler,
    stop_scheduler,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sailcast")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle events."""
    # Startup: fetch initial data and start scheduler
    logger.info("SailCast starting up...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"NWS Gridpoint: {settings.NWS_OFFICE}/{settings.NWS_GRIDPOINT_X},{settings.NWS_GRIDPOINT_Y}")

    try:
        await refresh_all_data()
        logger.info("Initial data fetch complete")
    except Exception as e:
        logger.warning(f"Initial data fetch failed (will retry on schedule): {e}")

    start_scheduler()

    yield

    # Shutdown
    stop_scheduler()
    logger.info("SailCast shut down")


app = FastAPI(
    title="SailCast API",
    description="Coastal sailing safety advisories powered by NWS data and AI",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - allow the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.CLIENT_URL, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(forecast_router)


@app.get("/")
async def root():
    return {
        "app": "SailCast",
        "version": "1.0.0",
        "description": "Coastal sailing safety advisories",
        "docs": "/docs",
    }
