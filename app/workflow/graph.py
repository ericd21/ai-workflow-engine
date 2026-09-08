from typing import Optional, Dict, Any
from langgraph.graph import StateGraph, END
from pydantic import BaseModel

from app.schemas.intake import IntakeRequest
from app.schemas.extraction import ExtractionResult
from app.schemas.triage import TriageDecision
from app.schemas.routing import RoutingDecision

from app.llm.extractor import run_extraction
from app.workflow.triage import run_triage
from app.workflow.routing import run_routing
from app.storage.logging import write_log_record

# ---------------------------------------------------------
# State Model
# ---------------------------------------------------------

class WorkflowState(BaseModel):
    run_id: str
    intake: IntakeRequest
    extraction: Optional[ExtractionResult] = None
    triage: Optional[TriageDecision] = None
    routing: Optional[RoutingDecision] = None
    logs: Optional[Dict[str, Any]] = None
    errors: list[str] = []
    metadata: Dict[str, Any] = {}
    
# ---------------------------------------------------------
# Node Definitions
# ---------------------------------------------------------

def intake_node(state: WorkflowState) -> WorkflowState:
    # Intake is already validated by FastAPI before entering the graph.
    # This node exists mainly for symmetry and future expansion.
    return state


def extraction_node(state: WorkflowState) -> WorkflowState:
    try:
        extraction = run_extraction(state.intake, state.run_id)
        state.extraction = extraction
    except Exception as e:
        state.errors.append(str(e))
        raise
    return state


def triage_node(state: WorkflowState) -> WorkflowState:
    try:
        triage = run_triage_rules(state.extraction, state.run_id)
        state.triage = triage
    except Exception as e:
        state.errors.append(str(e))
        raise
    return state


def routing_node(state: WorkflowState) -> WorkflowState:
    try:
        routing = run_routing_rules(state.triage, state.run_id)
        state.routing = routing
    except Exception as e:
        state.errors.append(str(e))
        raise
    return state


def logging_node(state: WorkflowState) -> WorkflowState:
    try:
        log_record = write_log_record(
            run_id=state.run_id,
            intake=state.intake,
            extraction=state.extraction,
            triage=state.triage,
            routing=state.routing,
            metadata=state.metadata,
            errors=state.errors,
        )
        state.logs = log_record
    except Exception as e:
        state.errors.append(str(e))
        raise
    return state


def response_node(state: WorkflowState) -> WorkflowState:
    # This node simply marks the end of the workflow.
    # The orchestrator will return state.routing as the API response.
    return state


# ---------------------------------------------------------
# Graph Definition
# ---------------------------------------------------------

def build_workflow_graph():
    graph = StateGraph(WorkflowState)

    # Register nodes
    graph.add_node("intake", intake_node)
    graph.add_node("extraction", extraction_node)
    graph.add_node("triage", triage_node)
    graph.add_node("routing", routing_node)
    graph.add_node("logging", logging_node)
    graph.add_node("response", response_node)

    # Edges (linear workflow)
    graph.add_edge("intake", "extraction")
    graph.add_edge("extraction", "triage")
    graph.add_edge("triage", "routing")
    graph.add_edge("routing", "logging")
    graph.add_edge("logging", "response")

    # Mark the final node
    graph.set_entry_point("intake")
    graph.set_finish_point("response")

    return graph.compile()


# ---------------------------------------------------------
# Public API for engine.py
# ---------------------------------------------------------

workflow_graph = build_workflow_graph()
