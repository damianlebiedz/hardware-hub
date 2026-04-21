"""Hardware Hub FastAPI application entry point.

This module initialises the FastAPI application, registers routers, and exposes
the core health-check endpoint used by the Docker orchestration layer to confirm
that the service is up and ready to accept traffic.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse


app: FastAPI = FastAPI(
    title="Hardware Hub API",
    description="Internal hardware rental management system.",
    version="0.1.0",
)


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
