"""Integration: the compiled LangGraph, driven by the mock LLM provider."""

import pytest

from app.llm import extractor as extractor_mod
from app.workflow import graph as graph_mod
from app.workflow.graph import build_workflow_graph
from tests.helpers import make_intake

_SUPPORT_MSG = "the app keeps crashing whenever I try to log in"


@pytest.fixture
def graph():
    return build_workflow_graph()


def test_full_pipeline_populates_state(graph):
    # LLM_PROVIDER=mock (conftest autouse) → real mock provider, no network.
    out = graph.invoke(
        {
            "run_id": "r1",
            "intake": make_intake(
                department="other",
                message="Please issue a refund for my duplicate invoice charge",
            ),
        }
    )
    assert out["extraction"].department.value == "billing"  # mock detects billing keywords
    assert out["triage"].department_overridden is True  # 'other' → 'billing' @ 0.82
    assert out["routing"].target.value == "billing_queue"
    assert out["logs"]["run_id"] == "r1"
    assert out["errors"] == []


def test_extraction_failure_routes_to_logging(graph, monkeypatch):
    def boom(_prompt):
        raise RuntimeError("llm exploded")

    monkeypatch.setattr(extractor_mod, "call_llm", boom)

    out = graph.invoke({"run_id": "r2", "intake": make_intake()})

    # extraction / triage / routing never produced a value on the failure path
    assert out.get("extraction") is None
    assert out.get("triage") is None
    assert out.get("routing") is None
    assert out["logs"] is not None  # logging node still executed
    assert any("extraction" in e for e in out["errors"])
    assert out["logs"]["errors"] == out["errors"]


def test_triage_reconciliation_match_path(graph):
    matched = graph.invoke(
        {"run_id": "m", "intake": make_intake(department="support", message=_SUPPORT_MSG)}
    )
    assert matched["triage"].department_overridden is False
    assert matched["routing"].target.value == "support_queue"


@pytest.mark.parametrize(
    "node_fn,label",
    [("run_triage", "triage"), ("run_routing", "routing"), ("write_log_record", "logging")],
)
def test_node_exception_is_captured_and_routed(graph, monkeypatch, node_fn, label):
    def boom(*_a, **_k):
        raise RuntimeError(f"{label} broke")

    monkeypatch.setattr(graph_mod, node_fn, boom)
    out = graph.invoke({"run_id": "e", "intake": make_intake(message=_SUPPORT_MSG)})

    assert out["extraction"] is not None  # got past extraction
    assert any(label in e for e in out["errors"])
