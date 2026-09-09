import json

from app.llm.extractor import _extract_first_json_object
from app.llm.mock import generate_mock_response
from app.schemas.extraction import ExtractionResult


def _payload(raw: str) -> dict:
    block = _extract_first_json_object(raw)
    assert block is not None
    return json.loads(block)


def test_mock_output_satisfies_extraction_result():
    raw = generate_mock_response("User message:\nMy invoice was double charged this month")
    ExtractionResult(**_payload(raw), raw_model_output=raw)  # must not raise


def test_mock_support_and_urgency_keywords():
    raw = generate_mock_response("User message:\nurgent - the app crashed and login is broken")
    data = _payload(raw)
    assert data["department"] == "support"
    assert data["urgency"] == "high"


def test_mock_billing_keywords():
    raw = generate_mock_response("User message:\nplease refund my subscription invoice")
    assert _payload(raw)["department"] == "billing"


def test_mock_negative_tone():
    data = _payload(generate_mock_response("User message:\nthis is terrible and I am furious"))
    assert data["tone"] == "negative"


def test_mock_positive_tone():
    data = _payload(generate_mock_response("User message:\nthanks, the new feature is awesome"))
    assert data["tone"] == "positive"


def test_mock_defaults_to_other():
    data = _payload(generate_mock_response("User message:\njust saying hello, nothing specific"))
    assert data["department"] == "other"
    assert data["urgency"] == "medium"


def test_mock_has_trailing_prose_after_json():
    raw = generate_mock_response("User message:\nhello world this message is fine")
    assert "Explanation:" in raw
    assert raw.index("Explanation:") > raw.index("}")
