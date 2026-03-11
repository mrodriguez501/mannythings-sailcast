"""
SailCast FastAPI entry point.
Primary flow: GET / → static page → fetch /api/report every hour → sailing report.
Also: /health for infra/CI.
Optional: BASIC_AUTH_USER + BASIC_AUTH_PASSWORD in .env for a password wall.
"""
import base64
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from sailcast/ so OPENAI_API_KEY and others are set
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse

from app.api import report

app = FastAPI(
    title="SailCast",
    description="Hourly Sailing Forecast & Recommendation System",
    version="1.0.0",
)

# Optional HTTP Basic Auth: set BASIC_AUTH_USER and BASIC_AUTH_PASSWORD in .env to enable
_BASIC_USER = os.environ.get("BASIC_AUTH_USER", "").strip()
_BASIC_PASS = os.environ.get("BASIC_AUTH_PASSWORD", "").strip()
_AUTH_ENABLED = bool(_BASIC_USER and _BASIC_PASS)


@app.middleware("http")
async def basic_auth_middleware(request: Request, call_next):
    """Require HTTP Basic Auth for all paths except /health when env is set."""
    if not _AUTH_ENABLED:
        return await call_next(request)
    if request.url.path == "/health":
        return await call_next(request)
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Basic "):
        try:
            raw = base64.b64decode(auth[6:].strip()).decode("utf-8")
            user, _, password = raw.partition(":")
            if user == _BASIC_USER and password == _BASIC_PASS:
                return await call_next(request)
        except Exception:
            pass
    return PlainTextResponse(
        "Authentication required",
        status_code=401,
        headers={"WWW-Authenticate": "Basic realm=\"SailCast\""},
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
