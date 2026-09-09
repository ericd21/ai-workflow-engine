import pytest

from app.schemas.extraction import Urgency
from app.schemas.intake import Department
from app.schemas.routing import SLA, RoutingTarget
from app.workflow.routing import run_routing
from tests.helpers import make_triage


def test_human_review_routes_to_review_queue():
    t = make_triage(human_review_required=True, human_review_reason="ambiguous")
    r = run_routing(t, "r")
    assert r.target is RoutingTarget.human_review_queue
    assert r.sla is SLA.one_hour


@pytest.mark.parametrize(
    "dept,target",
    [
        (Department.support, RoutingTarget.support_queue),
        (Department.billing, RoutingTarget.billing_queue),
        (Department.sales, RoutingTarget.sales_queue),
        (Department.other, RoutingTarget.general_queue),
    ],
)
def test_department_queue_mapping(dept, target):
    assert run_routing(make_triage(final_department=dept), "r").target is target


@pytest.mark.parametrize(
    "urgency,sla",
    [
        (Urgency.high, SLA.immediate),
        (Urgency.medium, SLA.one_hour),
        (Urgency.low, SLA.four_hours),
    ],
)
def test_urgency_sla_mapping(urgency, sla):
    assert run_routing(make_triage(urgency=urgency), "r").sla is sla


def test_summary_and_priority_passthrough():
    r = run_routing(make_triage(summary="carry me over", priority="high"), "r")
    assert r.summary == "carry me over"
    assert r.priority.value == "high"


def test_human_review_reason_carried():
    t = make_triage(human_review_required=True, human_review_reason="low confidence")
    assert run_routing(t, "r").human_review_reason == "low confidence"
