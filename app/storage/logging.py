from datetime import datetime, timezone
from typing import Any

from app.logging_config import get_logger

logger = get_logger(__name__)


def _dump(obj: Any) -> Any:
    """JSON-safe representation of a pydantic model (enums/datetimes as strings)."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return obj


def write_log_record(
    *,
    run_id: str,
    intake: Any,
    extraction: Any | None,
    triage: Any | None,
    routing: Any | None,
    metadata: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    """
    Assemble a final structured workflow log record and write it to stdout.
    Returns the dict so the workflow graph can store it in state.logs.
    """

    record = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "intake": _dump(intake),
        "extraction": _dump(extraction),
        "triage": _dump(triage),
        "routing": _dump(routing),
        "metadata": metadata,
        "errors": errors,
    }

    # Emit final workflow summary to stdout
    logger.info(
        "Workflow summary record",
        extra={
            "run_id": run_id,
            "event": "workflow_summary",
            "summary": record,
        },
    )

    return record
