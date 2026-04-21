"""AI-powered router for Hardware Hub.

Exposes two endpoints:

* ``POST /api/ai/seed``   — accepts a raw JSON array of potentially malformed
  hardware records, sanitizes them via the Gemini API, and bulk-inserts the
  cleaned data into the database.

* ``POST /api/ai/search`` — accepts a natural-language query, sends all
  hardware records to Gemini (LLM-as-filter), and returns the matching rows
  as JSON.

Detailed documentation for the service layer lives in
:mod:`backend.services.ai_service`.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Hardware
from backend.schemas import HardwareRead, SearchRequest, SeedResponse
from backend.services.ai_service import SanitizeResult, llm_filter_hardware, sanitize_with_gemini

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
       (``gemini-2.5-flash`` by default) accompanied by a strict system prompt.
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
    sanitize_result: SanitizeResult = sanitize_with_gemini(raw_payload)

    # ── Step 4: Bulk insert ─────────────────────────────────────────────────
    inserted_items: list[Hardware] = []
    for record in sanitize_result.records:
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
        changes=sanitize_result.changes,
    )


@router.post(
    "/search",
    response_model=list[HardwareRead],
    summary="Natural-language semantic search (LLM-as-filter)",
    responses={
        200: {"description": "Query executed; matching hardware rows returned."},
        502: {"description": "Gemini API call failed or returned unparseable output."},
        503: {"description": "GEMINI_API_KEY is not configured."},
    },
)
def search_hardware(
    payload: SearchRequest,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Send all hardware records to the LLM and return semantically matching rows.

    **Full pipeline flow:**

    1. **Input**: Client POSTs ``{"query": "I need something to test a mobile app on"}``
       to this endpoint.

    2. **Fetch all records**: All rows from the ``hardware`` table are loaded
       and serialised as a JSON array.  If the database is empty, an empty
       list is returned immediately without touching the LLM.

    3. **LLM-as-filter via Gemini**: The full record list and the user's query
       are forwarded to
       :func:`~backend.services.ai_service.llm_filter_hardware`.  Gemini reads
       every record, applies semantic reasoning, and returns only the integer
       IDs of matching records.  This supports intent-based queries (e.g.
       "something to test a mobile app on" returns phones and tablets) that
       cannot be expressed as SQL column filters.

    4. **ID-based retrieval**: The backend executes a targeted
       ``SELECT … WHERE id IN (…)`` query using the validated integer IDs
       returned by the LLM, preserving the order in which the model returned
       them.

    5. **Serialisation**: Each result row is converted to a dict (keyed by
       column name) and returned as a JSON array.

    Args:
        payload: JSON body with a ``query`` string.
        db: Injected SQLAlchemy session.

    Returns:
        A list of hardware row dicts that the LLM determined to match the
        query.  Each dict contains the same fields as
        :class:`~backend.schemas.HardwareRead`.

    Raises:
        HTTPException (503): If ``GEMINI_API_KEY`` is not set.
        HTTPException (502): If the Gemini API call fails or returns
            non-parseable output.
        HTTPException (500): If SQL execution against the database fails.
    """
    # ── Step 2: Fetch all hardware records ───────────────────────────────────
    all_result = db.execute(text("SELECT * FROM hardware"))
    columns: list[str] = list(all_result.keys())
    all_records: list[dict[str, Any]] = [
        dict(zip(columns, row, strict=True)) for row in all_result.fetchall()
    ]

    if not all_records:
        return []

    # ── Step 3: Ask LLM to filter by semantic relevance ──────────────────────
    matching_ids: list[int] = llm_filter_hardware(payload.query, all_records)

    if not matching_ids:
        return []

    # ── Step 4: Fetch only the matched rows ───────────────────────────────────
    id_list: str = ", ".join(str(i) for i in matching_ids)
    try:
        matched_result = db.execute(text(f"SELECT * FROM hardware WHERE id IN ({id_list})"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SQL execution failed: {exc}",
        ) from exc

    # ── Step 5: Serialise, preserving LLM-returned order ─────────────────────
    matched_columns: list[str] = list(matched_result.keys())
    rows_by_id: dict[int, dict[str, Any]] = {
        int(row[matched_columns.index("id")]): dict(zip(matched_columns, row, strict=True))
        for row in matched_result.fetchall()
    }
    return [rows_by_id[i] for i in matching_ids if i in rows_by_id]
