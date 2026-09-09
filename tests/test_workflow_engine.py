"""Integration: WorkflowEngine.run_workflow end to end (mock provider)."""

import re

import pytest

from app.llm import extractor as extractor_mod
from app.workflow.engine import WorkflowEngine, _state_get
from app.workflow.errors import WorkflowError
from tests.helpers import make_intake


def test_state_get_handles_dict_and_object():
    assert _state_get({"a": 1}, "a") == 1
    assert _state_get({"a": 1}, "missing") is None

    class S:
        b = 2

    assert _state_get(S(), "b") == 2
    assert _state_get(S(), "missing") is None

_UUID4 = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


@pytest.fixture
def engine():
    return WorkflowEngine()


def test_returns_run_id_and_routing(engine):
    res = engine.run_workflow(make_intake(message="the app crashed and will not start"))
    assert _UUID4.match(res["run_id"])
    assert res["routing"].target.value.endswith("_queue")
    assert res["triage"] is not None
    assert res["logs"]["run_id"] == res["run_id"]


def test_supplied_run_id_is_used(engine):
    res = engine.run_workflow(make_intake(), run_id="fixed-123")
    assert res["run_id"] == "fixed-123"
    assert res["logs"]["run_id"] == "fixed-123"


def test_distinct_run_ids_per_call(engine):
    a = engine.run_workflow(make_intake())["run_id"]
    b = engine.run_workflow(make_intake())["run_id"]
    assert a != b


def test_failure_raises_workflow_error(engine, monkeypatch):
    def boom(_prompt):
        raise RuntimeError("llm down")

    monkeypatch.setattr(extractor_mod, "call_llm", boom)

    with pytest.raises(WorkflowError) as exc:
        engine.run_workflow(make_intake(), run_id="fail-1")

    assert exc.value.run_id == "fail-1"
    assert any("extraction" in e for e in exc.value.errors)
