"""AI-powered router for Hardware Hub.

Currently exposes the seed importer endpoint:

* ``POST /api/ai/seed`` — accepts a raw JSON array of potentially malformed
  hardware records, sanitizes them via the Gemini API, and bulk-inserts the
  cleaned data into the database.

Pipeline summary (detailed documentation lives in
:mod:`backend.services.ai_service`):

1. Client POSTs a raw JSON array to ``/api/ai/seed``.
2. The array is forwarded to :func:`~backend.services.ai_service.sanitize_with_gemini`,
   which sends it to Gemini with a strict data-cleaning system prompt covering
   brand-typo correction, date normalisation, status mapping, and ID
   de-duplication.
3. Gemini's JSON response is stripped of any markdown fences, parsed, and each
   record is coerced through the :class:`~backend.schemas.HardwareCreate`
   Pydantic model to guarantee schema compliance.
4. The validated list is bulk-inserted into the ``hardware`` table inside a
   single database transaction.
5. A :class:`~backend.schemas.SeedResponse` summarising the inserted count and
   full item list is returned to the caller.
"""

from typing import Any, List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Hardware
from backend.schemas import HardwareCreate, HardwareRead, SeedResponse
from backend.services.ai_service import sanitize_with_gemini


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
    raw_payload: List[Any],
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
    validated_records: List[HardwareCreate] = sanitize_with_gemini(raw_payload)

    # ── Step 4: Bulk insert ─────────────────────────────────────────────────
    inserted_items: List[Hardware] = []
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
