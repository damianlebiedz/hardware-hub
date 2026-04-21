"""Hardware Hub FastAPI application entry point.

This module initialises the FastAPI application, registers routers, and exposes
the core health-check endpoint used by the Docker orchestration layer to confirm
that the service is up and ready to accept traffic.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.database import init_db
from backend.routers import admin, ai, auth, hardware, rentals


app: FastAPI = FastAPI(
    title="Hardware Hub API",
    description="Internal hardware rental management system.",
    version="0.1.0",
)

# ── CORS ───────────────────────────────────────────────────────────────────────
# Allow the Vite dev server (port 5173) and the Docker-served frontend (port
# 5173 mapped by docker-compose) to call the API.  In production behind nginx
# the frontend and API share the same origin so CORS is not strictly needed,
# but it is harmless and simplifies local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(hardware.router)
app.include_router(rentals.router)
app.include_router(admin.router)
app.include_router(ai.router)


@app.on_event("startup")
def on_startup() -> None:
    """Initialise the database tables on application startup.

    Runs ``Base.metadata.create_all`` once when the Uvicorn worker starts.
    This is idempotent — existing tables are not modified.
    """
    init_db()


@app.get(
    "/api/health",
    response_class=JSONResponse,
    tags=["Health"],
    summary="Health check",
)
async def health_check() -> dict[str, str]:
    """Return the operational status of the API service.

    This endpoint is polled by Docker Compose (and any load-balancer / proxy)
    to determine whether the container is healthy and ready to serve requests.

    Returns:
        A JSON object with a single ``status`` key set to ``"ok"``.

    Example:
        >>> import httpx
        >>> response = httpx.get("http://localhost:8000/api/health")
        >>> response.json()
        {'status': 'ok'}
    """
    return {"status": "ok"}
