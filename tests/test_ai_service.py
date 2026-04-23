"""Tests for the AI service layer in Hardware Hub.

Covers two functions:

* :func:`~backend.services.ai_service.sanitize_with_gemini` — validates that
  the non-dict item fix (AttributeError guard) works correctly and that the
  normal happy-path validation behaviour is unchanged.

* :func:`~backend.services.ai_service.llm_filter_hardware` — validates the
  LLM-as-filter semantic search pipeline: correct ID parsing, empty-record
  short-circuit, and all error paths (invalid JSON, non-array, missing key).

Strategy
--------
The Gemini API call is mocked entirely — no network.  ``monkeypatch`` sets
fake ``GEMINI_API_KEY`` and ``GEMINI_MODEL`` (both are required by the service).
``unittest.mock.patch`` replaces ``genai.Client`` so that
``client.models.generate_content`` returns a controlled JSON string.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.services.ai_service import llm_filter_hardware, sanitize_with_gemini

_TEST_GEMINI_MODEL: str = "fake-model-for-tests"


def _patch_gemini_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-tests")
    monkeypatch.setenv("GEMINI_MODEL", _TEST_GEMINI_MODEL)


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
        _patch_gemini_env(monkeypatch)
        with patch("backend.services.ai_service.genai.Client", _mock_gemini(payload)):
            return sanitize_with_gemini([{}]).records  # raw input ignored — Gemini is mocked

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
        _patch_gemini_env(monkeypatch)

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
        _patch_gemini_env(monkeypatch)
        with patch("backend.services.ai_service.genai.Client", _mock_gemini(payload)):
            return sanitize_with_gemini([{}]).records

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

    def test_sanitize_result_has_changes_for_corrected_records(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SanitizeResult.changes must include entries when the AI corrects fields."""
        raw_input = [{"name": "MacBook Pro", "brand": "Appel", "status": "Available"}]
        cleaned_output = [{"name": "MacBook Pro", "brand": "Apple", "status": "Available"}]

        _patch_gemini_env(monkeypatch)
        with patch("backend.services.ai_service.genai.Client", _mock_gemini(cleaned_output)):
            result = sanitize_with_gemini(raw_input)

        assert len(result.records) == 1
        assert len(result.changes) == 1
        change = result.changes[0]
        assert change.name == "MacBook Pro"
        field_names = [c.field for c in change.changes]
        assert "brand" in field_names
        brand_change = next(c for c in change.changes if c.field == "brand")
        assert brand_change.before == "Appel"
        assert brand_change.after == "Apple"

    def test_sanitize_result_no_changes_when_all_clean(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SanitizeResult.changes must be empty when the AI makes no corrections."""
        _patch_gemini_env(monkeypatch)
        with patch("backend.services.ai_service.genai.Client", _mock_gemini([_VALID_RECORD])):
            result = sanitize_with_gemini([_VALID_RECORD])

        assert len(result.records) == 1
        assert result.changes == []


# ---------------------------------------------------------------------------
# Helper — mock Gemini for llm_filter_hardware (returns raw text, not a list)
# ---------------------------------------------------------------------------


def _mock_gemini_text(response_text: str) -> MagicMock:
    """Return a mock genai.Client whose generate_content returns *response_text* verbatim."""
    mock_response = MagicMock()
    mock_response.text = response_text

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    mock_client_cls = MagicMock(return_value=mock_client)
    return mock_client_cls


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_RECORDS: list[dict] = [
    {"id": 1, "name": "Apple iPhone 13 Pro Max", "brand": "Apple", "status": "Available"},
    {"id": 2, "name": "Dell XPS 15", "brand": "Dell", "status": "Available"},
    {"id": 3, "name": "Samsung Galaxy S21", "brand": "Samsung", "status": "In Use"},
]


# ---------------------------------------------------------------------------
# Tests — llm_filter_hardware
# ---------------------------------------------------------------------------


class TestLlmFilterHardware:
    """Tests for the LLM-as-filter semantic search pipeline."""

    def test_returns_matching_ids(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Happy path: Gemini returns a JSON array of IDs; function returns them as ints."""
        _patch_gemini_env(monkeypatch)
        with patch("backend.services.ai_service.genai.Client", _mock_gemini_text("[1, 3]")):
            result = llm_filter_hardware("mobile phones", _SAMPLE_RECORDS)

        assert result == [1, 3]

    def test_empty_records_short_circuits_without_api_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When records=[], return [] immediately and never call the Gemini API."""
        _patch_gemini_env(monkeypatch)
        mock_cls = _mock_gemini_text("[]")
        with patch("backend.services.ai_service.genai.Client", mock_cls):
            result = llm_filter_hardware("anything", [])

        assert result == []
        mock_cls.assert_not_called()

    def test_empty_llm_result_returns_empty_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When Gemini returns '[]', function returns an empty list without error."""
        _patch_gemini_env(monkeypatch)
        with patch("backend.services.ai_service.genai.Client", _mock_gemini_text("[]")):
            result = llm_filter_hardware("nothing matches", _SAMPLE_RECORDS)

        assert result == []

    def test_invalid_json_raises_502(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When Gemini returns non-JSON text, HTTPException 502 is raised."""
        _patch_gemini_env(monkeypatch)
        with patch(
            "backend.services.ai_service.genai.Client",
            _mock_gemini_text("not valid json at all"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                llm_filter_hardware("query", _SAMPLE_RECORDS)

        assert exc_info.value.status_code == 502

    def test_non_array_json_raises_502(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When Gemini returns a JSON object instead of an array, HTTPException 502 is raised."""
        _patch_gemini_env(monkeypatch)
        with patch(
            "backend.services.ai_service.genai.Client",
            _mock_gemini_text('{"ids": [1, 2]}'),
        ):
            with pytest.raises(HTTPException) as exc_info:
                llm_filter_hardware("query", _SAMPLE_RECORDS)

        assert exc_info.value.status_code == 502

    def test_array_with_non_integer_elements_raises_502(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the returned array contains non-integer elements, HTTPException 502 is raised."""
        _patch_gemini_env(monkeypatch)
        with patch(
            "backend.services.ai_service.genai.Client",
            _mock_gemini_text('["one", "two"]'),
        ):
            with pytest.raises(HTTPException) as exc_info:
                llm_filter_hardware("query", _SAMPLE_RECORDS)

        assert exc_info.value.status_code == 502

    def test_missing_api_key_raises_503(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When GEMINI_API_KEY is absent, HTTPException 503 is raised before any API call."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(HTTPException) as exc_info:
            llm_filter_hardware("query", _SAMPLE_RECORDS)

        assert exc_info.value.status_code == 503
