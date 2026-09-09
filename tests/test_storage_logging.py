import json

from app.storage.logging import write_log_record
from tests.helpers import make_extraction, make_intake, make_triage

_SECTIONS = {"run_id", "timestamp", "intake", "extraction", "triage", "routing", "metadata", "errors"}


def test_record_has_all_sections():
    rec = write_log_record(
        run_id="r1",
        intake=make_intake(),
        extraction=make_extraction(),
        triage=make_triage(),
        routing=None,
        metadata={},
        errors=[],
    )
    assert set(rec) == _SECTIONS
    assert rec["routing"] is None


def test_models_serialized_json_safe():
    rec = write_log_record(
        run_id="r1",
        intake=make_intake(),
        extraction=make_extraction(department="billing"),
        triage=None,
        routing=None,
        metadata={},
        errors=[],
    )
    assert rec["extraction"]["department"] == "billing"  # enum rendered as str
    json.dumps(rec)  # nothing in the record breaks json.dumps


def test_plain_values_pass_through():
    rec = write_log_record(
        run_id="r1",
        intake={"raw": 1},
        extraction=None,
        triage=None,
        routing=None,
        metadata={"k": "v"},
        errors=["extraction: boom"],
    )
    assert rec["intake"] == {"raw": 1}
    assert rec["errors"] == ["extraction: boom"]
