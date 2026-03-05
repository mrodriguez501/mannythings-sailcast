"""
SailCast FastAPI entry point.
Serves static files and exposes /health, /api/forecast, /api/report.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api import forecast, report

app = FastAPI(
    title="SailCast",
    description="Hourly Sailing Forecast & Recommendation System",
    version="1.0.0",
)

# Mount API routers
app.include_router(forecast.router, prefix="/api", tags=["forecast"])
app.include_router(report.router, prefix="/api", tags=["report"])

# Serve static files from app/static
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def root():
        """Serve the main static HTML page."""
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"message": "SailCast API", "docs": "/docs"}


@app.get("/health")
async def health():
    """Health check for load balancers and CI."""
    return {"status": "ok"}
