from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.logging_config import get_logger

logger = get_logger(__name__)


def write_log_record(
    *,
    run_id: str,
    intake: Any,
    extraction: Optional[Any],
    triage: Optional[Any],
    routing: Optional[Any],
    metadata: Dict[str, Any],
    errors: list[str],
) -> Dict[str, Any]:
    """
    Assemble a final structured workflow log record and write it to stdout.
    Returns the dict so the workflow graph can store it in state.logs.
    """

    record = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "intake": intake.model_dump() if hasattr(intake, "model_dump") else intake,
        "extraction": (
            extraction.model_dump() if hasattr(extraction, "model_dump") else extraction
        ),
        "triage": (
            triage.model_dump() if hasattr(triage, "model_dump") else triage
        ),
        "routing": (
            routing.model_dump() if hasattr(routing, "model_dump") else routing
        ),
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
