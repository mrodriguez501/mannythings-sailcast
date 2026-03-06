"""
SailCast FastAPI entry point.
Primary flow: GET / → static page → fetch /api/report every hour → sailing report.
Also: /health for infra/CI.
"""
from pathlib import Path

from dotenv import load_dotenv

# Load .env from sailcast/ so OPENAI_API_KEY and others are set
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api import report

app = FastAPI(
    title="SailCast",
    description="Hourly Sailing Forecast & Recommendation System",
    version="1.0.0",
)

# Single user-facing API (primary directive)
app.include_router(report.router, prefix="/api", tags=["report"])

# Serve static files from app/static
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Serve weather icons from sailcast/static-icons (e.g. from Makin-Things/weather-icons)
STATIC_ICONS_DIR = Path(__file__).resolve().parent.parent / "static-icons"
if STATIC_ICONS_DIR.exists():
    app.mount("/static-icons", StaticFiles(directory=str(STATIC_ICONS_DIR)), name="static-icons")

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
