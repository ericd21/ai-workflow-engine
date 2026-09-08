from typing import Any
import uuid

from app.schemas.intake import IntakeRequest
from app.workflow.graph import workflow_graph
from app.logging_config import get_logger


logger = get_logger(__name__)

class WorkflowEngine:
    """
    Thin orchestration wrapper around the LangGraph workflow.
    This class provides a stable interface for FastAPI and any
    future execution modes (async, batch, human-review, etc.).
    """

    def __init__(self):
        self.graph = workflow_graph

    def run_workflow(self, intake: IntakeRequest) -> Any:
        """
        Execute the workflow graph with the provided intake payload.
        Returns the final routing decision (or full state if desired).
        """
        # see function def in main.py -- it should be somewhere else
        run_id = generate_run_id()

        logger.info(
            "Workflow execution started",
            extra={"run_id": run_id, "event": "workflow_start"}
        )
        
        # Prepare initial state for the graph
        initial_state = {
            "run_id": str,
            "intake": intake
            }

        # Execute the workflow
        final_state = self.graph.invoke(initial_state)

        logger.info(
            "Workflow execution completed",
            extra={"run_id": run_id, "event": "workflow_complete"}
        )
        # The API layer only needs the routing decision
        return final_state.routing


# Singleton engine instance
engine = WorkflowEngine()
