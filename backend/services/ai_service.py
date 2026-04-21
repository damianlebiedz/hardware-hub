"""AI-assisted data sanitization and semantic search service for Hardware Hub.

This module encapsulates all Gemini API integrations:

* :func:`sanitize_with_gemini` — seed importer pipeline that cleans messy
  legacy hardware records and returns validated
  :class:`~backend.schemas.HardwareCreate` objects.

* :func:`sanitize_sql` — **critical security gate** that strips markdown
  fences from an LLM-generated SQL string and verifies it is a read-only
  ``SELECT`` statement with no destructive keywords.

* :func:`text_to_sql` — semantic search pipeline that translates a natural-
  language query into a safe SQLite ``SELECT`` statement via Gemini.

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
# Semantic search — Text-to-SQL
# ---------------------------------------------------------------------------

# Exact SQLite DDL for the hardware table, embedded in every search prompt so
# Gemini has unambiguous column names and types to reason about.
_HARDWARE_SCHEMA_DDL: str = """
CREATE TABLE hardware (
    id            INTEGER  PRIMARY KEY AUTOINCREMENT,
    name          VARCHAR  NOT NULL,
    brand         VARCHAR,
    purchase_date DATETIME,
    status        VARCHAR  NOT NULL DEFAULT 'Available',
    notes         TEXT
);
""".strip()

_SEARCH_SYSTEM_PROMPT: str = f"""
You are a SQL translation agent for a SQLite database.
The database contains a single relevant table with the following schema:

{_HARDWARE_SCHEMA_DDL}

Valid values for the `status` column are: 'Available', 'In Use', 'Repair'.

Your task: translate the user's natural-language query into a single, valid
SQLite SELECT statement that retrieves data from the `hardware` table.

Rules you MUST follow without exception:
1. Return ONLY the raw SQL statement — no explanation, no markdown, no code
   fences, no trailing semicolons.
2. The statement MUST begin with the word SELECT (case-insensitive).
3. You MUST NOT produce any statement containing DROP, DELETE, UPDATE, INSERT,
   PRAGMA, ALTER, CREATE, or any other data-modification keyword.
4. Use only columns that exist in the schema above.
5. For status comparisons use the exact casing: 'Available', 'In Use', 'Repair'.
6. If the query is ambiguous, return a broad SELECT that covers likely intent.
7. Never use LIMIT unless the user explicitly asks for a limited number of
   results.
""".strip()

# Keywords whose presence in the LLM output must trigger an immediate reject.
_FORBIDDEN_KEYWORDS: frozenset[str] = frozenset(
    {"DROP", "DELETE", "UPDATE", "INSERT", "PRAGMA", "ALTER", "CREATE"}
)


def sanitize_sql(raw_sql: str) -> str:
    """Strip markdown formatting from LLM output and enforce read-only SQL.

    This is the **critical security gate** between the LLM response and the
    database engine.  It applies three successive checks:

    1. **Markdown stripping** — removes `` ```sql ... ``` `` or
       `` ``` ... ``` `` fences via :func:`_strip_markdown_fences`.
    2. **SELECT assertion** — the cleaned string must begin with ``SELECT``
       (checked case-insensitively after normalisation).
    3. **Forbidden keyword scan** — the upper-cased token set of the query
       must not intersect with :data:`_FORBIDDEN_KEYWORDS`.  Tokenisation is
       done on word boundaries so that ``DROPDOWN`` does not trip the
       ``DROP`` guard.

    Args:
        raw_sql: Raw text returned by the Gemini API.

    Returns:
        The sanitized SQL string, stripped of whitespace and safe to execute.

    Raises:
        HTTPException (422): If the cleaned string does not start with
            ``SELECT``.
        HTTPException (422): If any forbidden keyword is found in the
            query tokens.

    Example:
        >>> sanitize_sql("```sql\\nSELECT * FROM hardware WHERE status='Repair'\\n```")
        "SELECT * FROM hardware WHERE status='Repair'"

        >>> sanitize_sql("DROP TABLE hardware")
        # raises HTTPException(422)
    """
    cleaned: str = _strip_markdown_fences(raw_sql).rstrip(";").strip()

    if not cleaned.upper().startswith("SELECT"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=("The AI did not return a SELECT statement. " f"Received: {cleaned[:200]!r}"),
        )

    # Tokenise on word boundaries for accurate keyword detection.
    tokens: set[str] = set(re.findall(r"\b[A-Za-z_]+\b", cleaned.upper()))
    found_forbidden: set[str] = tokens & _FORBIDDEN_KEYWORDS
    if found_forbidden:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Generated SQL contains forbidden keyword(s): "
                f"{sorted(found_forbidden)}.  Query rejected for safety."
            ),
        )

    return cleaned


def text_to_sql(natural_language_query: str) -> str:
    """Translate a natural-language hardware query into a safe SQLite SELECT.

    Pipeline:

    1. **Prompt construction** — The hardware table DDL and a strict
       instruction set are combined with the user's query and sent to Gemini.
    2. **LLM call** — Gemini returns what should be a raw SQL ``SELECT``
       statement.
    3. **Security sanitization** — :func:`sanitize_sql` strips any markdown
       fences and rejects any output that is not a read-only ``SELECT`` or
       that contains a forbidden keyword.

    Args:
        natural_language_query: Free-text query from the end user, e.g.
            ``'Show me broken Apple laptops'``.

    Returns:
        A sanitized SQLite ``SELECT`` string ready to be executed against the
        ``hardware`` table.

    Raises:
        HTTPException (503): If ``GEMINI_API_KEY`` is not set.
        HTTPException (502): If the Gemini API call fails.
        HTTPException (422): If the LLM output fails the security gate (not a
            SELECT, or contains a forbidden keyword).

    Example:
        >>> sql = text_to_sql("Find all Apple items under repair")
        >>> sql.upper().startswith("SELECT")
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

    model_name: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # ── 1. Build the full prompt ────────────────────────────────────────────
    full_prompt: str = f"{_SEARCH_SYSTEM_PROMPT}\n\n" f"User query: {natural_language_query}"

    # ── 2. Call the Gemini API ──────────────────────────────────────────────
    try:
        client: genai.Client = genai.Client(api_key=api_key)
        logger.info(
            "Translating query to SQL via Gemini (%s): %r", model_name, natural_language_query
        )
        response: genai_types.GenerateContentResponse = client.models.generate_content(
            model=model_name,
            contents=full_prompt,
        )
        raw_sql: str = response.text or ""
    except Exception as exc:
        logger.exception("Gemini API call failed during text-to-SQL: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini API call failed: {exc}",
        ) from exc

    # ── 3. Sanitize and return ──────────────────────────────────────────────
    safe_sql: str = sanitize_sql(raw_sql)
    logger.info("Generated safe SQL: %s", safe_sql)
    return safe_sql
