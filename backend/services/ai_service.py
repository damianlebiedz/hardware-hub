"""AI-assisted data sanitization service for Hardware Hub.

This module encapsulates the Gemini API integration used by the seed importer
pipeline.  The single public function :func:`sanitize_with_gemini` receives an
arbitrary list of raw hardware records (potentially malformed legacy data),
delegates cleaning to the LLM, and returns a validated list of
:class:`~backend.schemas.HardwareCreate` objects that are safe to bulk-insert
into the database.

Pipeline overview
-----------------
1. **Prompt construction** — A strict system prompt is prepended to the raw
   JSON payload.  The prompt instructs Gemini to act as a data-cleaning agent
   and return *only* a valid JSON array with no surrounding text or markdown.
2. **LLM call** — The combined prompt is sent to ``gemini-1.5-flash`` via the
   ``google-generativeai`` SDK.  The model name can be overridden with the
   ``GEMINI_MODEL`` environment variable.
3. **Response stripping** — LLMs occasionally wrap JSON in markdown fences
   (`` ```json ... ``` ``).  A lightweight stripping function removes any such
   wrappers before parsing.
4. **JSON parsing** — The stripped response is parsed with :func:`json.loads`.
   Any parse error raises an :class:`~fastapi.HTTPException` (502) so the
   caller receives a meaningful error rather than an unhandled exception.
5. **Pydantic validation** — Each record is coerced through
   :class:`~backend.schemas.HardwareCreate`.  Records that fail validation are
   collected and reported; the valid subset is returned to the caller.

Environment variables
---------------------
``GEMINI_API_KEY``
    Required.  Google AI API key used to authenticate Gemini requests.
    Obtain from https://aistudio.google.com/app/apikey.
``GEMINI_MODEL``
    Optional.  Gemini model identifier.  Defaults to ``gemini-1.5-flash``.
"""

import json
import logging
import os
import re
from typing import Any

from fastapi import HTTPException, status
from google import genai
from google.genai import types as genai_types
from pydantic import ValidationError

from backend.schemas import HardwareCreate


logger: logging.Logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SEED_SYSTEM_PROMPT: str = """
You are a data-cleaning agent for a hardware asset management system.
You will receive a JSON array of hardware records that may contain errors.

Your task is to return a CLEANED version of the same array, applying ALL of
the following rules without exception:

1. **Brand typos**: Correct obvious brand name misspellings.
   Examples: "Appel" → "Apple", "Samsug" → "Samsung", "Lenoco" → "Lenovo".

2. **Date normalisation**: Convert every date to ISO-8601 format "YYYY-MM-DD".
   If a date is missing or unparseable, set the field to null.

3. **Status normalisation**: Map every status value to exactly one of:
   "Available", "In Use", or "Repair".
   Mapping rules:
   - If status is already one of the three valid values, keep it as-is.
   - If the notes field mentions damage, broken, cracked, fault, repair, or
     similar, set status to "Repair".
   - Otherwise, set status to "Available".

4. **Duplicate ID resolution**: If two or more records share the same integer
   "id" field, re-assign unique sequential integers starting from 1, preserving
   the original order.  If no "id" field is present, omit it entirely from the
   output (the database will auto-assign).

5. **Output format**: Return ONLY a valid JSON array.  Do NOT include any
   explanation, markdown code fences, or extra text.  The response must be
   parseable by json.loads() with no pre-processing.

6. **Field retention**: Preserve all other fields exactly as provided.  Do
   not add or remove fields beyond what the rules above require.
""".strip()

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences that an LLM may wrap around JSON output.

    Handles both `` ```json ... ``` `` and plain `` ``` ... ``` `` wrappers,
    as well as any leading/trailing whitespace.

    Args:
        text: Raw text returned by the LLM.

    Returns:
        The input string with any surrounding markdown fences removed and
        leading/trailing whitespace stripped.

    Example:
        >>> _strip_markdown_fences("```json\\n[{...}]\\n```")
        '[{...}]'
    """
    stripped: str = text.strip()
    # Match optional language hint (e.g. ```json) followed by content and closing ```
    pattern: re.Pattern[str] = re.compile(
        r"^```(?:json)?\s*([\s\S]*?)\s*```$", re.IGNORECASE
    )
    match: re.Match[str] | None = pattern.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sanitize_with_gemini(raw_records: list[dict[str, Any]]) -> list[HardwareCreate]:
    """Send messy legacy hardware records to Gemini for cleaning and validation.

    This function is the core of the AI seed importer pipeline.  It combines
    a strict data-cleaning system prompt with the caller's raw JSON payload,
    submits the request to the Gemini API, strips any markdown formatting from
    the response, parses the resulting JSON, and coerces each record through
    the :class:`~backend.schemas.HardwareCreate` Pydantic model to guarantee
    schema compliance before the records are persisted.

    Args:
        raw_records: List of raw hardware dicts as received from the client.
            Records may contain typos, invalid statuses, malformed dates, or
            duplicate IDs — Gemini is instructed to correct all of these.

    Returns:
        A list of validated :class:`~backend.schemas.HardwareCreate` instances
        ready for bulk insertion.  Records that fail Pydantic validation even
        after LLM cleaning are skipped (with a warning logged) so that a
        partially corrupt payload does not block a full import.

    Raises:
        HTTPException (503): If ``GEMINI_API_KEY`` is not set in the
            environment.
        HTTPException (502): If the Gemini API call fails or returns a
            non-parseable response.
        HTTPException (422): If *every* record in the LLM response fails
            Pydantic validation (i.e. nothing could be imported).

    Example:
        >>> records = [{"name": "MacBook Pro", "brand": "Appel", "status": "broken"}]
        >>> cleaned = sanitize_with_gemini(records)
        >>> cleaned[0].brand
        'Apple'
        >>> cleaned[0].status
        'Repair'
    """
    api_key: str | None = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "GEMINI_API_KEY environment variable is not set. "
                "The AI seed importer is unavailable."
            ),
        )

    model_name: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # ── 1. Build the full prompt ────────────────────────────────────────────
    raw_json: str = json.dumps(raw_records, indent=2, default=str)
    full_prompt: str = (
        f"{_SEED_SYSTEM_PROMPT}\n\n"
        f"Raw data to clean:\n{raw_json}"
    )

    # ── 2. Call the Gemini API ──────────────────────────────────────────────
    try:
        client: genai.Client = genai.Client(api_key=api_key)
        logger.info(
            "Sending %d records to Gemini (%s) for sanitization.",
            len(raw_records),
            model_name,
        )
        response: genai_types.GenerateContentResponse = client.models.generate_content(
            model=model_name,
            contents=full_prompt,
        )
        raw_response_text: str = response.text
    except Exception as exc:
        logger.exception("Gemini API call failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini API call failed: {exc}",
        ) from exc

    # ── 3. Strip markdown fences ────────────────────────────────────────────
    clean_text: str = _strip_markdown_fences(raw_response_text)

    # ── 4. Parse JSON ───────────────────────────────────────────────────────
    try:
        cleaned_records: list[dict[str, Any]] = json.loads(clean_text)
        if not isinstance(cleaned_records, list):
            raise ValueError("Expected a JSON array at the top level.")
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Failed to parse Gemini response as JSON: %s", clean_text[:500])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini returned non-JSON output: {exc}",
        ) from exc

    # ── 5. Pydantic validation ──────────────────────────────────────────────
    validated: list[HardwareCreate] = []
    skipped: int = 0

    for idx, record in enumerate(cleaned_records):
        # Drop auto-assigned IDs returned by Gemini — the DB will assign them.
        record.pop("id", None)
        try:
            validated.append(HardwareCreate.model_validate(record))
        except ValidationError as exc:
            skipped += 1
            logger.warning(
                "Record at index %d failed Pydantic validation (skipped): %s", idx, exc
            )

    if not validated:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"All {len(cleaned_records)} records returned by Gemini failed "
                "schema validation.  No data was inserted."
            ),
        )

    if skipped:
        logger.warning("%d record(s) were skipped due to validation errors.", skipped)

    logger.info("%d record(s) passed validation and will be inserted.", len(validated))
    return validated
