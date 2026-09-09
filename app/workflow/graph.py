from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from app.llm.extractor import run_extraction
from app.logging_config import get_logger
from app.schemas.extraction import ExtractionResult
from app.schemas.intake import IntakeRequest
from app.schemas.routing import RoutingDecision
from app.schemas.triage import TriageDecision
from app.storage.logging import write_log_record
from app.workflow.routing import run_routing
from app.workflow.triage import run_triage

logger = get_logger(__name__)

# ---------------------------------------------------------
# State Model
# ---------------------------------------------------------

class WorkflowState(BaseModel):
    run_id: str
    intake: IntakeRequest
    extraction: ExtractionResult | None = None
    triage: TriageDecision | None = None
    routing: RoutingDecision | None = None
    logs: dict[str, Any] | None = None
    errors: list[str] = []
    metadata: dict[str, Any] = {}

# ---------------------------------------------------------
# Node Definitions
#
# On failure a node records the error on state and returns normally; the
# conditional edges below then route straight to the logging node so every
# run — success or failure — produces a persisted structured log record.
# ---------------------------------------------------------

def intake_node(state: WorkflowState) -> WorkflowState:
    # Intake is already validated by FastAPI / the engine before entering the
    # graph. This node exists mainly for symmetry and future expansion.
    return state


def extraction_node(state: WorkflowState) -> WorkflowState:
    try:
        state.extraction = run_extraction(state.intake, state.run_id)
    except Exception as e:
        logger.exception(
            "Extraction node failed",
            extra={"run_id": state.run_id, "event": "node_error", "node": "extraction"},
        )
        state.errors.append(f"extraction: {e}")
    return state


def triage_node(state: WorkflowState) -> WorkflowState:
    try:
        state.triage = run_triage(
            state.extraction,
            state.run_id,
            submitted_department=state.intake.department,
        )
    except Exception as e:
        logger.exception(
            "Triage node failed",
            extra={"run_id": state.run_id, "event": "node_error", "node": "triage"},
        )
        state.errors.append(f"triage: {e}")
    return state


def routing_node(state: WorkflowState) -> WorkflowState:
    try:
        state.routing = run_routing(state.triage, state.run_id)
    except Exception as e:
        logger.exception(
            "Routing node failed",
            extra={"run_id": state.run_id, "event": "node_error", "node": "routing"},
        )
        state.errors.append(f"routing: {e}")
    return state


def logging_node(state: WorkflowState) -> WorkflowState:
    try:
        state.logs = write_log_record(
            run_id=state.run_id,
            intake=state.intake,
            extraction=state.extraction,
            triage=state.triage,
            routing=state.routing,
            metadata=state.metadata,
            errors=state.errors,
        )
    except Exception as e:
        logger.exception(
            "Logging node failed",
            extra={"run_id": state.run_id, "event": "node_error", "node": "logging"},
        )
        state.errors.append(f"logging: {e}")
    return state


def response_node(state: WorkflowState) -> WorkflowState:
    # Marks the end of the workflow. The engine returns state.routing (or raises
    # WorkflowError if state.errors is non-empty).
    return state


# ---------------------------------------------------------
# Conditional routing: skip ahead to logging on error
# ---------------------------------------------------------

def _route_after_extraction(state: WorkflowState) -> str:
    return "logging" if state.errors else "triage"


def _route_after_triage(state: WorkflowState) -> str:
    return "logging" if state.errors else "routing"


# ---------------------------------------------------------
# Graph Definition
# ---------------------------------------------------------

def build_workflow_graph():
    graph = StateGraph(WorkflowState)

    graph.add_node("intake", intake_node)
    graph.add_node("extraction", extraction_node)
    graph.add_node("triage", triage_node)
    graph.add_node("routing", routing_node)
    graph.add_node("logging", logging_node)
    graph.add_node("response", response_node)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "extraction")
    graph.add_conditional_edges(
        "extraction", _route_after_extraction, {"triage": "triage", "logging": "logging"}
    )
    graph.add_conditional_edges(
        "triage", _route_after_triage, {"routing": "routing", "logging": "logging"}
    )
    graph.add_edge("routing", "logging")
    graph.add_edge("logging", "response")
    graph.add_edge("response", END)

    return graph.compile()


# ---------------------------------------------------------
# Public API for engine.py
# ---------------------------------------------------------

workflow_graph = build_workflow_graph()
