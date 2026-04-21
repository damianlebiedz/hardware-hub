"""AI-powered router for Hardware Hub.

Exposes two endpoints:

* ``POST /api/ai/seed``   — accepts a raw JSON array of potentially malformed
  hardware records, sanitizes them via the Gemini API, and bulk-inserts the
  cleaned data into the database.

* ``POST /api/ai/search`` — accepts a natural-language query, translates it
  to a safe SQLite ``SELECT`` via Gemini (Text-to-SQL), executes it against
  the ``hardware`` table, and returns the matching rows as JSON.

Detailed documentation for the service layer lives in
:mod:`backend.services.ai_service`.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Hardware
from backend.schemas import HardwareCreate, HardwareRead, SearchRequest, SeedResponse
from backend.services.ai_service import sanitize_with_gemini, text_to_sql

router: APIRouter = APIRouter(prefix="/api/ai", tags=["AI"])


@router.post(
    "/seed",
    response_model=SeedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="AI-assisted bulk hardware import",
    responses={
        201: {"description": "Records cleaned and inserted successfully."},
        422: {"description": "All records failed schema validation after LLM cleaning."},
        502: {"description": "Gemini API call failed or returned unparseable output."},
        503: {"description": "GEMINI_API_KEY is not configured."},
    },
)
def seed_hardware(
    raw_payload: list[Any],
    db: Session = Depends(get_db),
) -> SeedResponse:
    """Accept raw legacy hardware data, sanitize it with Gemini, and persist it.

    This endpoint is the HTTP entry point for the AI seed importer pipeline.
    It delegates all LLM interaction and data-cleaning to
    :func:`~backend.services.ai_service.sanitize_with_gemini` and focuses
    solely on the bulk-insert and response-construction responsibilities.

    **Full pipeline flow:**

    1. **Input**: Client POSTs a JSON array of raw hardware objects.  The
       records may contain brand typos (e.g. ``"Appel"``), invalid statuses
       (e.g. ``"broken"``), non-standard date formats, and duplicate integer
       IDs — all common artefacts of legacy data exports.

    2. **AI sanitization**: The raw array is sent to the Gemini API
       (``gemini-1.5-flash`` by default) accompanied by a strict system prompt.
       Gemini is instructed to:

       * Fix brand typos (``"Appel"`` → ``"Apple"``).
       * Normalise all dates to ``YYYY-MM-DD``.
       * Map every status to one of ``"Available"``, ``"In Use"``, or
         ``"Repair"`` (using the notes field to infer ``"Repair"`` when the
         notes mention damage).
       * Re-index duplicate IDs.
       * Return **only** a valid JSON array — no markdown, no explanation.

    3. **Type-safety gate**: Each record in Gemini's response is parsed through
       :class:`~backend.schemas.HardwareCreate`.  Records that still fail
       validation after LLM cleaning are skipped with a logged warning.

    4. **Bulk insert**: All validated records are inserted into the
       ``hardware`` table inside a single database transaction.  If the
       transaction fails the session is rolled back and a 500 error is raised.

    5. **Response**: Returns :class:`~backend.schemas.SeedResponse` with the
       count of inserted records and their full serialised representations.

    Args:
        raw_payload: A JSON array of arbitrary hardware objects as received
            from the client.  No pre-validation is applied before forwarding
            to the LLM.
        db: Injected SQLAlchemy session.

    Returns:
        :class:`~backend.schemas.SeedResponse` with ``inserted`` count and
        ``items`` list.

    Raises:
        HTTPException (503): If ``GEMINI_API_KEY`` is not set.
        HTTPException (502): If the Gemini API call fails or returns
            non-JSON output.
        HTTPException (422): If every record fails validation.
        HTTPException (500): If the database transaction fails.
    """
    # ── Step 3: AI sanitization + Pydantic validation ───────────────────────
    validated_records: list[HardwareCreate] = sanitize_with_gemini(raw_payload)

    # ── Step 4: Bulk insert ─────────────────────────────────────────────────
    inserted_items: list[Hardware] = []
    for record in validated_records:
        hw: Hardware = Hardware(**record.model_dump())
        db.add(hw)
        inserted_items.append(hw)

    db.commit()

    for hw in inserted_items:
        db.refresh(hw)

    # ── Step 5: Build response ──────────────────────────────────────────────
    return SeedResponse(
        inserted=len(inserted_items),
        items=[HardwareRead.model_validate(hw) for hw in inserted_items],
    )


@router.post(
    "/search",
    response_model=list[HardwareRead],
    summary="Natural-language semantic search (Text-to-SQL)",
    responses={
        200: {"description": "Query executed; matching hardware rows returned."},
        422: {"description": "LLM output failed the SQL security gate."},
        502: {"description": "Gemini API call failed."},
        503: {"description": "GEMINI_API_KEY is not configured."},
    },
)
def search_hardware(
    payload: SearchRequest,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Translate a natural-language query to SQL and return matching hardware rows.

    **Full pipeline flow:**

    1. **Input**: Client POSTs ``{"query": "Show me broken Apple laptops"}``
       to this endpoint.

    2. **Text-to-SQL via Gemini**: The query is forwarded to
       :func:`~backend.services.ai_service.text_to_sql`, which sends a prompt
       to Gemini containing:

       * The exact SQLite DDL for the ``hardware`` table (column names,
         types, valid status values).
       * Strict instructions to return *only* a ``SELECT`` statement with no
         markdown, no explanation, and no data-modification keywords.
       * The user's natural-language query.

    3. **Critical security gate**: The LLM response passes through
       :func:`~backend.services.ai_service.sanitize_sql`, which:

       * Strips any markdown code fences (`` ```sql ... ``` ``).
       * Asserts the cleaned string begins with ``SELECT``.
       * Tokenises the query and rejects it if any of the following forbidden
         keywords are present: ``DROP``, ``DELETE``, ``UPDATE``, ``INSERT``,
         ``PRAGMA``, ``ALTER``, ``CREATE``.

       A query that fails either check raises HTTP 422 immediately — the
       database is never touched.

    4. **Execution**: The sanitized SQL is executed against the SQLite
       ``hardware`` table using SQLAlchemy's ``text()`` construct.

    5. **Serialisation**: Each result row is converted to a dict (keyed by
       column name) and returned as a JSON array.

    Args:
        payload: JSON body with a ``query`` string.
        db: Injected SQLAlchemy session.

    Returns:
        A list of hardware row dicts matching the translated SQL query.
        Each dict contains the same fields as :class:`~backend.schemas.HardwareRead`.

    Raises:
        HTTPException (503): If ``GEMINI_API_KEY`` is not set.
        HTTPException (502): If the Gemini API call fails.
        HTTPException (422): If the generated SQL fails the security gate.
        HTTPException (500): If SQL execution against the database fails.
    """
    # ── Step 2 + 3: Translate + sanitize ────────────────────────────────────
    safe_sql: str = text_to_sql(payload.query)

    # ── Step 4: Execute against the database ────────────────────────────────
    try:
        result = db.execute(text(safe_sql))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SQL execution failed: {exc}",
        ) from exc

    # ── Step 5: Map rows to JSON-serialisable dicts ──────────────────────────
    columns: list[str] = list(result.keys())
    rows: list[dict[str, Any]] = [dict(zip(columns, row, strict=True)) for row in result.fetchall()]
    return rows
