"""Tests for the SQL security sanitization gate.

Verifies that :func:`~backend.services.ai_service.sanitize_sql` correctly:

* Accepts valid ``SELECT`` statements (with and without markdown fences).
* Strips `` ```sql `` / `` ``` `` markdown wrappers transparently.
* Strips trailing semicolons.
* Rejects every forbidden keyword: DROP, DELETE, UPDATE, INSERT, PRAGMA,
  ALTER, CREATE.
* Rejects output that does not start with SELECT.
"""

import pytest
from fastapi import HTTPException

from backend.services.ai_service import sanitize_sql


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected_start",
    [
        ("SELECT * FROM hardware", "SELECT"),
        ("select id, name FROM hardware WHERE status='Repair'", "SELECT"),
        ("  SELECT brand FROM hardware  ", "SELECT"),
        # Trailing semicolons must be stripped without error
        ("SELECT * FROM hardware;", "SELECT"),
        # Markdown fences — ```sql variant
        ("```sql\nSELECT * FROM hardware WHERE brand = 'Apple'\n```", "SELECT"),
        # Markdown fences — plain variant
        ("```\nSELECT name, status FROM hardware\n```", "SELECT"),
    ],
)
def test_sanitize_sql_accepts_valid_select(raw: str, expected_start: str) -> None:
    """Valid SELECT statements are returned cleaned and without error."""
    result = sanitize_sql(raw)
    assert result.upper().startswith(expected_start)
    assert not result.endswith(";"), "Trailing semicolons must be stripped."


# ---------------------------------------------------------------------------
# Rejection paths — forbidden keywords
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "forbidden_sql",
    [
        "DROP TABLE hardware",
        "DELETE FROM hardware WHERE id=1",
        "UPDATE hardware SET status='Available'",
        "INSERT INTO hardware (name) VALUES ('test')",
        "PRAGMA table_info(hardware)",
        "ALTER TABLE hardware ADD COLUMN foo TEXT",
        "CREATE TABLE evil (id INTEGER)",
    ],
)
def test_sanitize_sql_blocks_forbidden_keywords(forbidden_sql: str) -> None:
    """Any SQL containing a forbidden keyword is rejected with HTTP 422."""
    with pytest.raises(HTTPException) as exc_info:
        sanitize_sql(forbidden_sql)
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# Rejection paths — non-SELECT output
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "non_select",
    [
        "not a sql statement at all",
        "EXPLAIN SELECT * FROM hardware",
        "WITH cte AS (SELECT 1) SELECT * FROM cte",  # CTE doesn't start with SELECT
    ],
)
def test_sanitize_sql_blocks_non_select(non_select: str) -> None:
    """Output that does not start with SELECT is rejected with HTTP 422."""
    with pytest.raises(HTTPException) as exc_info:
        sanitize_sql(non_select)
    assert exc_info.value.status_code == 422
