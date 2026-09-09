import json

import pytest

from app.llm import extractor as extractor_mod
from app.llm.extractor import (
    _extract_first_json_object,
    _parse_extraction_json,
    run_extraction,
)
from app.schemas.extraction import ExtractionResult
from tests.helpers import extraction_payload, make_intake, raw_llm_response


class TestExtractFirstJsonObject:
    def test_json_then_prose(self):
        assert json.loads(_extract_first_json_object('{"a": 1}\n\nblah blah')) == {"a": 1}

    def test_nested_object(self):
        assert json.loads(_extract_first_json_object('x {"a": {"b": 2}} y')) == {"a": {"b": 2}}

    def test_brace_inside_string_literal(self):
        assert json.loads(_extract_first_json_object('{"s": "a } b"}')) == {"s": "a } b"}

    def test_escaped_quote_inside_string(self):
        got = _extract_first_json_object(r'{"s": "she said \"hi\" }"} trailing')
        assert json.loads(got) == {"s": 'she said "hi" }'}

    def test_code_fence(self):
        assert json.loads(_extract_first_json_object('```json\n{"x": true}\n```')) == {"x": True}

    def test_no_json_returns_none(self):
        assert _extract_first_json_object("sorry, no JSON here") is None

    def test_unterminated_returns_none(self):
        assert _extract_first_json_object('{"a": 1') is None


class TestParseExtractionJson:
    def test_valid(self):
        data = _parse_extraction_json(raw_llm_response(department="billing"), "r")
        assert data["department"] == "billing"

    def test_missing_field_raises(self):
        payload = extraction_payload()
        del payload["tone"]
        with pytest.raises(ValueError, match="Missing required fields"):
            _parse_extraction_json(json.dumps(payload), "r")

    def test_no_json_raises(self):
        with pytest.raises(ValueError, match="did not return a JSON object"):
            _parse_extraction_json("I can't help with that.", "r")

    def test_malformed_json_raises(self):
        with pytest.raises(ValueError, match="Malformed JSON"):
            _parse_extraction_json('{"department": "support",,}', "r")


class TestRunExtraction:
    def test_happy_path(self, monkeypatch):
        monkeypatch.setattr(extractor_mod, "call_llm", lambda _p: raw_llm_response(department="billing"))
        result = run_extraction(make_intake(), "r")
        assert isinstance(result, ExtractionResult)
        assert result.department.value == "billing"
        assert result.raw_model_output  # raw output retained for debugging

    def test_retry_then_success(self, monkeypatch):
        calls = {"n": 0}

        def flaky(_p):
            calls["n"] += 1
            return "not json" if calls["n"] == 1 else raw_llm_response()

        monkeypatch.setattr(extractor_mod, "call_llm", flaky)
        assert isinstance(run_extraction(make_intake(), "r"), ExtractionResult)
        assert calls["n"] == 2

    def test_always_malformed_raises_after_three_attempts(self, monkeypatch):
        calls = {"n": 0}

        def bad(_p):
            calls["n"] += 1
            return "never valid json"

        monkeypatch.setattr(extractor_mod, "call_llm", bad)
        with pytest.raises(RuntimeError, match="after 3 attempts"):
            run_extraction(make_intake(), "r")
        assert calls["n"] == 3
