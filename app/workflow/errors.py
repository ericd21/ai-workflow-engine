"""Workflow-level exceptions."""

from __future__ import annotations


class WorkflowError(Exception):
    """Raised by ``WorkflowEngine.run_workflow`` when the graph finished with
    one or more errors recorded in state.

    Carries the ``run_id`` and the list of collected error strings so the API
    layer can return a 502 with a useful ``detail`` while the failed run still
    has a persisted structured log record.
    """

    def __init__(self, run_id: str, errors: list[str]):
        self.run_id = run_id
        self.errors = list(errors)
        detail = "; ".join(self.errors) if self.errors else "unknown error"
        super().__init__(f"Workflow {run_id} failed: {detail}")
