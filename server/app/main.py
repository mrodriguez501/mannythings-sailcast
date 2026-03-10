"""
SailCast Backend - FastAPI Application Entry Point
Serves API and static frontend at / (SailCast UI).
"""

import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.routes.forecast import router as forecast_router
from app.routes.report import router as report_router
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
app.include_router(report_router, prefix="/api")

# Serve static frontend at / when server/static exists
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def root():
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"app": "SailCast", "version": "1.0.0", "docs": "/docs"}
else:

    @app.get("/")
    async def root():
        return {
            "app": "SailCast",
            "version": "1.0.0",
            "description": "Coastal sailing safety advisories",
            "docs": "/docs",
        }


@app.get("/health")
async def health():
    return {"status": "ok"}
