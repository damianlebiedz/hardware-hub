"""AI-assisted data sanitization and semantic search service for Hardware Hub.

This module encapsulates all Gemini API integrations:

* :func:`sanitize_with_gemini` — seed importer pipeline that cleans messy
  legacy hardware records and returns validated
  :class:`~backend.schemas.HardwareCreate` objects.

* :func:`llm_filter_hardware` — semantic search pipeline that sends the full
  list of hardware records and a natural-language query to Gemini and returns
  the IDs of matching records.  This LLM-as-filter approach supports
  intent-based queries (e.g. "something to test a mobile app on") that cannot
  be expressed as SQL column filters.

Environment variables
---------------------
``GEMINI_API_KEY``
    Required.  Google AI API key.
    Obtain from https://aistudio.google.com/app/apikey.
``GEMINI_MODEL``
    Optional.  Gemini model identifier.  Defaults to ``gemini-2.5-flash``.
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any

from fastapi import HTTPException, status
from google import genai
from google.genai import types as genai_types
from pydantic import ValidationError

from backend.schemas import HardwareCreate, SeedFieldChange, SeedRecordChange

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
    # Match optional language hint (e.g. ```json, ```sql, ```python …) followed
    # by content and a closing ```.
    pattern: re.Pattern[str] = re.compile(r"^```(?:\w+)?\s*([\s\S]*?)\s*```$", re.IGNORECASE)
    match: re.Match[str] | None = pattern.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


# ---------------------------------------------------------------------------
# Diff helpers
# ---------------------------------------------------------------------------


@dataclass
class SanitizeResult:
    """Return value of :func:`sanitize_with_gemini`.

    Attributes:
        records: Validated :class:`~backend.schemas.HardwareCreate` instances
            ready for bulk insertion.
        changes: Per-record corrections made by the AI; only records with at
            least one modified field are included.
    """

    records: list[HardwareCreate]
    changes: list[SeedRecordChange] = dc_field(default_factory=list)


def _compute_record_diff(
    raw_idx: int,
    raw: dict[str, Any],
    cleaned: HardwareCreate,
) -> SeedRecordChange | None:
    """Compare a raw record to its AI-cleaned counterpart field by field.

    Only fields tracked by :class:`~backend.schemas.HardwareCreate` are
    compared.  The raw payload may use camelCase (``purchaseDate``) or
    snake_case (``purchase_date``); both are handled.

    Returns:
        A :class:`~backend.schemas.SeedRecordChange` when at least one field
        differs, otherwise ``None``.
    """
    field_changes: list[SeedFieldChange] = []

    def _str(val: Any) -> str | None:
        return str(val) if val is not None and str(val) != "" else None

    comparisons: list[tuple[str, Any, Any]] = [
        ("name", raw.get("name"), cleaned.name),
        ("brand", raw.get("brand"), cleaned.brand),
        (
            "purchase_date",
            raw.get("purchaseDate") or raw.get("purchase_date"),
            str(cleaned.purchase_date) if cleaned.purchase_date else None,
        ),
        ("status", raw.get("status"), cleaned.status),
        ("notes", raw.get("notes"), cleaned.notes),
    ]

    for field_name, raw_val, clean_val in comparisons:
        before = _str(raw_val)
        after = _str(clean_val)
        if before != after:
            field_changes.append(SeedFieldChange(field=field_name, before=before, after=after))

    if not field_changes:
        return None

    return SeedRecordChange(index=raw_idx, name=cleaned.name, changes=field_changes)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sanitize_with_gemini(raw_records: list[dict[str, Any]]) -> SanitizeResult:
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
        A :class:`SanitizeResult` with ``records`` (validated
        :class:`~backend.schemas.HardwareCreate` instances ready for bulk
        insertion) and ``changes`` (per-record diff of what the AI corrected).
        Records that fail Pydantic validation even after LLM cleaning are
        skipped (with a warning logged).

    Raises:
        HTTPException (503): If ``GEMINI_API_KEY`` is not set in the
            environment.
        HTTPException (502): If the Gemini API call fails or returns a
            non-parseable response.
        HTTPException (422): If *every* record in the LLM response fails
            Pydantic validation (i.e. nothing could be imported).

    Example:
        >>> records = [{"name": "MacBook Pro", "brand": "Appel", "status": "broken"}]
        >>> result = sanitize_with_gemini(records)
        >>> result.records[0].brand
        'Apple'
        >>> result.records[0].status
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

    model_name: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # ── 1. Build the full prompt ────────────────────────────────────────────
    raw_json: str = json.dumps(raw_records, indent=2, default=str)
    full_prompt: str = f"{_SEED_SYSTEM_PROMPT}\n\n" f"Raw data to clean:\n{raw_json}"

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
            config=genai_types.GenerateContentConfig(
                thinking_config=genai_types.ThinkingConfig(thinking_budget=0)
            ),
        )
        raw_response_text: str = response.text or ""
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

    # ── 5. Pydantic validation + diff computation ───────────────────────────
    validated: list[HardwareCreate] = []
    changes: list[SeedRecordChange] = []
    skipped: int = 0

    for idx, record in enumerate(cleaned_records):
        try:
            # Guard against non-dict items (e.g. ints or strings) that Gemini
            # may occasionally return inside the array — .pop() would raise
            # AttributeError on anything that is not a mapping.
            if not isinstance(record, dict):
                raise TypeError(f"Expected a dict, got {type(record).__name__}")
            # Drop auto-assigned IDs returned by Gemini — the DB will assign them.
            record.pop("id", None)
            hw = HardwareCreate.model_validate(record)
            validated.append(hw)

            # Compute diff against the original raw record at the same position.
            raw = raw_records[idx] if idx < len(raw_records) else {}
            diff = _compute_record_diff(idx, raw, hw)
            if diff is not None:
                changes.append(diff)
        except (TypeError, AttributeError, ValidationError) as exc:
            skipped += 1
            logger.warning("Record at index %d is invalid and was skipped: %s", idx, exc)

    if not validated:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"All {len(cleaned_records)} records returned by Gemini failed "
                "schema validation.  No data was inserted."
            ),
        )

    if skipped:
        logger.warning("%d record(s) were skipped due to validation errors.", skipped)

    logger.info("%d record(s) passed validation and will be inserted.", len(validated))
    return SanitizeResult(records=validated, changes=changes)


# ---------------------------------------------------------------------------
# Semantic search — LLM-as-filter
# ---------------------------------------------------------------------------

_FILTER_SYSTEM_PROMPT: str = """
You are a hardware search assistant for an asset management system.
You will receive a JSON array of hardware records and a natural-language search query.

Your task: return ONLY a valid JSON array of integer IDs of the records that
semantically match the query.

Rules you MUST follow without exception:
1. Return ONLY a valid JSON array of integers — no explanation, no markdown
   code fences, no extra text.  The response must be parseable by json.loads()
   with no pre-processing.
2. Match records based on the semantic intent of the query, not just keyword
   matching.  For example: "something to test a mobile app on" should match
   phones and tablets even if those words do not appear verbatim in the record.
3. If no records match, return an empty JSON array: []
4. Only include IDs of records that actually appear in the provided array.
""".strip()


def llm_filter_hardware(query: str, records: list[dict[str, Any]]) -> list[int]:
    """Send all hardware records and a natural-language query to Gemini and
    return the IDs of semantically matching records.

    This is the core of the LLM-as-filter semantic search pipeline.  Unlike
    Text-to-SQL, this approach does not require the query to map to an explicit
    schema column.  The LLM reads every record and applies semantic reasoning
    to determine which records match the user's intent (e.g. "something to
    test a mobile app on" correctly returns phones and tablets even though
    the schema has no ``category`` column).

    Args:
        query: Free-text search query from the end user, e.g.
            ``'I need something to test a mobile app on'``.
        records: Full list of hardware records serialised as dicts (all
            columns included).  Typically fetched from ``SELECT * FROM
            hardware`` immediately before calling this function.

    Returns:
        A list of integer hardware IDs whose records the LLM determined to
        match the query, in the order returned by the model.  An empty list
        means no records matched.

    Raises:
        HTTPException (503): If ``GEMINI_API_KEY`` is not set.
        HTTPException (502): If the Gemini API call fails, or if the model
            returns output that cannot be parsed as a JSON array of integers.

    Example:
        >>> ids = llm_filter_hardware("broken Apple laptops", all_records)
        >>> isinstance(ids, list) and all(isinstance(i, int) for i in ids)
        True
    """
    api_key: str | None = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "GEMINI_API_KEY environment variable is not set. "
                "The AI search feature is unavailable."
            ),
        )

    if not records:
        return []

    model_name: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # ── 1. Build the full prompt ────────────────────────────────────────────
    records_json: str = json.dumps(records, indent=2, default=str)
    full_prompt: str = (
        f"{_FILTER_SYSTEM_PROMPT}\n\n"
        f"Hardware records:\n{records_json}\n\n"
        f"User query: {query}"
    )

    # ── 2. Call the Gemini API ──────────────────────────────────────────────
    try:
        client: genai.Client = genai.Client(api_key=api_key)
        logger.info(
            "Filtering %d hardware record(s) via Gemini (%s) for query: %r",
            len(records),
            model_name,
            query,
        )
        response: genai_types.GenerateContentResponse = client.models.generate_content(
            model=model_name,
            contents=full_prompt,
            config=genai_types.GenerateContentConfig(
                thinking_config=genai_types.ThinkingConfig(thinking_budget=0)
            ),
        )
        raw_response: str = response.text or ""
    except Exception as exc:
        logger.exception("Gemini API call failed during hardware filtering: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini API call failed: {exc}",
        ) from exc

    # ── 3. Parse the response as a JSON integer array ───────────────────────
    clean_text: str = _strip_markdown_fences(raw_response)

    try:
        parsed: Any = json.loads(clean_text)
        if not isinstance(parsed, list):
            raise ValueError(f"Expected a JSON array, got {type(parsed).__name__}.")
        ids: list[int] = []
        for item in parsed:
            if not isinstance(item, int):
                raise ValueError(
                    f"Expected integer IDs, got {type(item).__name__}: {item!r}."
                )
            ids.append(item)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error(
            "Failed to parse Gemini filter response as a JSON integer array: %s",
            clean_text[:500],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini returned an unexpected response format: {exc}",
        ) from exc

    logger.info(
        "Gemini matched %d record(s) for query %r: IDs=%s",
        len(ids),
        query,
        ids,
    )
    return ids
