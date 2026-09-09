from typing import Any

from app.config import generate_run_id
from app.logging_config import get_logger
from app.schemas.intake import IntakeRequest
from app.workflow.errors import WorkflowError
from app.workflow.graph import workflow_graph

logger = get_logger(__name__)


def _state_get(state: Any, key: str) -> Any:
    """Read ``key`` from a compiled-graph result (dict or state model)."""
    if isinstance(state, dict):
        return state.get(key)
    return getattr(state, key, None)


class WorkflowEngine:
    """
    Thin orchestration wrapper around the LangGraph workflow.
    Provides a stable interface for FastAPI and any future execution modes
    (async, batch, human-review, etc.).
    """

    def __init__(self):
        self.graph = workflow_graph

    def run_workflow(
        self, intake: IntakeRequest, run_id: str | None = None
    ) -> dict[str, Any]:
        """
        Execute the workflow graph with the provided intake payload.

        Returns a dict with the ``run_id`` and the final decisions. Raises
        ``WorkflowError`` if the graph recorded any errors (the failed run
        still has a persisted structured log record).
        """
        run_id = run_id or generate_run_id()

        logger.info(
            "Workflow execution started",
            extra={"run_id": run_id, "event": "workflow_start"},
        )

        initial_state = {"run_id": run_id, "intake": intake}
        final_state = self.graph.invoke(initial_state)

        errors = _state_get(final_state, "errors") or []
        if errors:
            logger.error(
                "Workflow execution failed",
                extra={"run_id": run_id, "event": "workflow_failure", "errors": errors},
            )
            raise WorkflowError(run_id, errors)

        logger.info(
            "Workflow execution completed",
            extra={"run_id": run_id, "event": "workflow_complete"},
        )

        return {
            "run_id": run_id,
            "routing": _state_get(final_state, "routing"),
            "triage": _state_get(final_state, "triage"),
            "extraction": _state_get(final_state, "extraction"),
            "logs": _state_get(final_state, "logs"),
        }


# Singleton engine instance
engine = WorkflowEngine()
