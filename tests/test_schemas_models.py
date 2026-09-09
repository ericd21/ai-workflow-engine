import json

import pytest
from pydantic import ValidationError

from app.schemas.extraction import Tone, Urgency
from app.schemas.intake import Department
from app.schemas.routing import SLA, RoutingDecision, RoutingTarget
from app.schemas.triage import Priority, TriageDecision
from tests.helpers import make_extraction, make_triage


def test_extraction_confidence_upper_bound():
    with pytest.raises(ValidationError):
        make_extraction(department_confidence=1.5)


def test_extraction_confidence_lower_bound():
    with pytest.raises(ValidationError):
        make_extraction(tone_confidence=-0.1)


def test_extraction_enum_coercion():
    e = make_extraction(department="billing", tone="negative", urgency="high")
    assert e.department is Department.billing
    assert e.tone is Tone.negative
    assert e.urgency is Urgency.high


def test_extraction_summary_min_length():
    with pytest.raises(ValidationError):
        make_extraction(summary="hi")


def test_extraction_rejects_unknown_enum_value():
    with pytest.raises(ValidationError):
        make_extraction(department="legal")


def test_triage_missing_required_field():
    with pytest.raises(ValidationError):
        TriageDecision(final_department="support")


def test_routing_priority_is_priority_enum():
    triage = make_triage(priority="high")
    rd = RoutingDecision(
        target=RoutingTarget.support_queue,
        sla=SLA.immediate,
        final_department=Department.support,
        urgency=Urgency.high,
        priority=triage.priority,
        summary="s",
    )
    assert rd.priority is Priority.high


def test_models_json_roundtrip():
    e = make_extraction(department="sales")
    assert json.loads(e.model_dump_json())["department"] == "sales"
