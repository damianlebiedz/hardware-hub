# ── Stage 1: builder ──────────────────────────────────────────────────────────
# Install Poetry and resolve/export dependencies into a virtualenv that will be
# copied into the final, slimmer runtime image.
FROM python:3.12-slim AS builder

# Disable bytecode caching and force unbuffered stdout/stderr for clean logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Tell Poetry to create the virtualenv inside the project directory so it
    # is easy to copy to the next stage.
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

WORKDIR /app

# Install Poetry via pip (no requirements.txt — Poetry is the sole package
# manager for this project).
RUN pip install --upgrade pip && pip install poetry

# Copy only the dependency manifests first to benefit from Docker layer caching:
# subsequent builds that don't touch pyproject.toml / poetry.lock will reuse
# this cached layer and skip a full dependency resolution.
COPY pyproject.toml poetry.lock* ./

# Install production dependencies only (no dev/test extras) into the
# in-project virtualenv.
RUN poetry install --without dev --no-root

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Make the in-project venv the active Python environment.
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Bring in the pre-built virtualenv from the builder stage.
COPY --from=builder /app/.venv /app/.venv

# Copy backend application source code.
COPY backend/ ./backend/

# /app/data is mounted as a named Docker volume (see docker-compose.yml) so
# that the SQLite database file survives container restarts and re-deployments.
RUN mkdir -p /app/data

EXPOSE 8000

# Railway injects PORT; Docker Compose leaves it unset → 8000 matches EXPOSE and compose ports.
# Override CMD in docker-compose for local development hot-reloading if desired.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
