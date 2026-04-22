"""Hardware Hub FastAPI application entry point.

This module initialises the FastAPI application, registers routers, and exposes
the core health-check endpoint used by the Docker orchestration layer to confirm
that the service is up and ready to accept traffic.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.database import SessionLocal, init_db
from backend.routers import admin, ai, auth, hardware, rentals
from backend.services.bootstrap import bootstrap_admin

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler.

    Runs initialisation tasks on startup before yielding control to the
    application request loop.  Any teardown logic (connection pool close,
    background task cancellation, etc.) should be placed after the ``yield``.

    Steps:
        1. ``init_db`` — creates all tables and applies SQLite column
           compatibility patches (idempotent).
        2. ``bootstrap_admin`` — ensures a first admin account exists
           according to the ``BOOTSTRAP_ADMIN_*`` environment variables.
    """
    init_db()
    db = SessionLocal()
    try:
        bootstrap_admin(db)
    finally:
        db.close()
    yield


app: FastAPI = FastAPI(
    title="Hardware Hub API",
    description="Internal hardware rental management system.",
    version="0.1.0",
    lifespan=lifespan,
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
