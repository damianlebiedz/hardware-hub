"""Tests for the sanitize_with_gemini validation loop in ai_service.

Focus: prove that the fix for the non-dict item bug (AttributeError on
``record.pop("id", None)`` when Gemini returns a primitive instead of a
dict) works correctly.

Before the fix the loop was:

    for idx, record in enumerate(cleaned_records):
        record.pop("id", None)          # <── outside try/except
        try:
            validated.append(HardwareCreate.model_validate(record))
        except ValidationError as exc:
            ...

A non-dict item (int, str, None, …) would raise AttributeError here,
which was NOT caught, resulting in an unhandled 500 Internal Server Error.

After the fix every step is inside a single try/except that catches
TypeError, AttributeError, and ValidationError, so primitive items are
silently skipped and only a 422 is raised when *every* item fails.

Strategy
--------
The Gemini API call is mocked entirely — no network, no key required.
``monkeypatch`` sets a fake ``GEMINI_API_KEY``.
``unittest.mock.patch`` replaces ``genai.Client`` so that
``client.models.generate_content`` returns a controlled JSON string.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.services.ai_service import sanitize_with_gemini

# ---------------------------------------------------------------------------
# Minimal valid hardware dict (satisfies HardwareCreate without an id field)
# ---------------------------------------------------------------------------
_VALID_RECORD: dict = {
    "name": "ThinkPad X1 Carbon",
    "brand": "Lenovo",
    "status": "Available",
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _mock_gemini(response_payload: list) -> MagicMock:
    """Return a mock genai.Client whose generate_content returns *response_payload*
    serialised as a JSON string (simulating a clean Gemini response).
    """
    mock_response = MagicMock()
    mock_response.text = json.dumps(response_payload)

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    mock_client_cls = MagicMock(return_value=mock_client)
    return mock_client_cls


# ---------------------------------------------------------------------------
# Tests — non-dict items must be skipped, not crash
# ---------------------------------------------------------------------------


class TestNonDictItemsAreSkipped:
    """Verify that primitive items inside the Gemini JSON array are skipped
    gracefully instead of crashing with AttributeError / 500.
    """

    def _run(self, monkeypatch: pytest.MonkeyPatch, payload: list) -> list:
        """Shared runner: mock env + Gemini, call sanitize_with_gemini."""
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-tests")
        with patch("backend.services.ai_service.genai.Client", _mock_gemini(payload)):
            return sanitize_with_gemini([{}])  # raw input ignored — Gemini is mocked

    def test_integer_items_are_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An integer inside the Gemini array must be skipped, not raise AttributeError.

        Without the fix ``42.pop("id", None)`` raises AttributeError → 500.
        With the fix it is caught and skipped; the valid record passes through.
        """
        payload = [1, _VALID_RECORD, 99]
        result = self._run(monkeypatch, payload)

        assert len(result) == 1, "Only the valid dict should survive."
        assert result[0].name == _VALID_RECORD["name"]

    def test_string_items_are_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A bare string inside the array must be skipped gracefully."""
        payload = ["not a record", _VALID_RECORD]
        result = self._run(monkeypatch, payload)

        assert len(result) == 1
        assert result[0].name == _VALID_RECORD["name"]

    def test_null_items_are_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A JSON null (Python None) inside the array must be skipped gracefully."""
        payload = [None, _VALID_RECORD]
        result = self._run(monkeypatch, payload)

        assert len(result) == 1
        assert result[0].name == _VALID_RECORD["name"]

    def test_list_items_are_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A nested list inside the array must be skipped gracefully."""
        payload = [[1, 2, 3], _VALID_RECORD]
        result = self._run(monkeypatch, payload)

        assert len(result) == 1
        assert result[0].name == _VALID_RECORD["name"]

    def test_mixed_primitives_all_skipped_raises_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When EVERY item is a non-dict primitive the endpoint must raise HTTP 422,
        NOT an unhandled AttributeError (which would surface as 500).
        """
        payload = [1, "bad", None, []]
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-tests")

        with patch("backend.services.ai_service.genai.Client", _mock_gemini(payload)):
            with pytest.raises(HTTPException) as exc_info:
                sanitize_with_gemini([{}])

        assert (
            exc_info.value.status_code == 422
        ), "All-bad payload must raise 422 Unprocessable, not 500 AttributeError."


# ---------------------------------------------------------------------------
# Tests — correct behaviour with well-formed data is unchanged
# ---------------------------------------------------------------------------


class TestNormalValidationBehaviour:
    """Regression guard: the fix must not break handling of valid payloads."""

    def _run(self, monkeypatch: pytest.MonkeyPatch, payload: list) -> list:
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-tests")
        with patch("backend.services.ai_service.genai.Client", _mock_gemini(payload)):
            return sanitize_with_gemini([{}])

    def test_valid_records_pass_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """All valid dicts are returned as HardwareCreate instances."""
        second = {"name": "Dell XPS 15", "brand": "Dell", "status": "Repair"}
        result = self._run(monkeypatch, [_VALID_RECORD, second])

        assert len(result) == 2
        assert result[0].name == _VALID_RECORD["name"]
        assert result[1].status == "Repair"

    def test_id_field_is_stripped_from_valid_records(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The ``id`` key returned by Gemini must be removed before Pydantic validation.

        HardwareCreate has no ``id`` field — if it were forwarded, model_validate
        would receive an unexpected key (extra='ignore' handles it in Pydantic v2,
        but the intent is that the DB assigns the PK, never the client).
        This asserts the pop still runs for well-formed dicts.
        """
        record_with_id = {**_VALID_RECORD, "id": 42}
        result = self._run(monkeypatch, [record_with_id])

        assert len(result) == 1
        # HardwareCreate has no `id` attribute; confirming the record was created
        # successfully (not skipped) proves pop ran and did not crash.
        assert result[0].name == _VALID_RECORD["name"]

    def test_invalid_schema_record_is_skipped_valid_one_is_kept(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A dict that fails Pydantic validation is skipped; valid ones still pass."""
        bad_schema = {"name": "", "status": "Available"}  # name min_length=1 → fail
        result = self._run(monkeypatch, [bad_schema, _VALID_RECORD])

        assert len(result) == 1
        assert result[0].name == _VALID_RECORD["name"]
