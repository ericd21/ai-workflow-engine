import pytest

from app.schemas.intake import Department
from app.schemas.triage import Priority
from app.workflow.triage import run_triage
from tests.helpers import make_extraction


def test_department_match_keeps_choice():
    ext = make_extraction(department="support", department_confidence=0.95)
    d = run_triage(ext, "r", submitted_department=Department.support)
    assert d.final_department is Department.support
    assert d.department_overridden is False
    assert d.human_review_required is False


def test_confident_disagreement_overrides_to_llm():
    ext = make_extraction(department="billing", department_confidence=0.8)
    d = run_triage(ext, "r", submitted_department=Department.support)
    assert d.final_department is Department.billing
    assert d.department_overridden is True
    assert "reclassified" in d.department_override_reason
    assert d.human_review_required is False


def test_unconfident_disagreement_keeps_choice_and_flags_review():
    ext = make_extraction(department="billing", department_confidence=0.4)
    d = run_triage(ext, "r", submitted_department=Department.support)
    assert d.final_department is Department.support
    assert d.department_overridden is False
    assert d.human_review_required is True
    assert "Ambiguous" in d.human_review_reason


def test_threshold_is_configurable(monkeypatch):
    monkeypatch.setenv("DEPARTMENT_CONFIDENCE_THRESHOLD", "0.9")
    ext = make_extraction(department="billing", department_confidence=0.8)
    d = run_triage(ext, "r", submitted_department=Department.support)
    assert d.department_overridden is False  # 0.8 < 0.9 now
    assert d.human_review_required is True


@pytest.mark.parametrize(
    "urgency,expected",
    [("high", Priority.high), ("medium", Priority.medium), ("low", Priority.low)],
)
def test_priority_mapping(urgency, expected):
    ext = make_extraction(urgency=urgency)
    d = run_triage(ext, "r", submitted_department=ext.department)
    assert d.priority is expected


def test_low_summary_confidence_flags_review():
    ext = make_extraction(summary_confidence=0.3)
    d = run_triage(ext, "r", submitted_department=ext.department)
    assert d.human_review_required is True
    assert d.human_review_reason == "Low summary confidence"


def test_missing_order_number_flags_review():
    ext = make_extraction(missing_info=["order_number"])
    d = run_triage(ext, "r", submitted_department=ext.department)
    assert d.human_review_required is True
    assert d.missing_info == ["order_number"]


def test_confidences_and_fields_copied_from_extraction():
    ext = make_extraction(tone="negative", tone_confidence=0.71, summary="carry this over please")
    d = run_triage(ext, "r", submitted_department=ext.department)
    assert d.tone.value == "negative"
    assert d.tone_confidence == 0.71
    assert d.summary == "carry this over please"
