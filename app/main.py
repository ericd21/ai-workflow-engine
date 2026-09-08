import logging
import uuid
from langsmith import traceable

from llm.extractor import extract_structured_payload
from workflow.triage import triage
from workflow.routing import route
from app.logging_config import configure_logging  # your JSON logging setup

logger = logging.getLogger(__name__)


def generate_run_id() -> str:
    return str(uuid.uuid4())


@traceable(name="run_workflow")
def run_workflow(user_message: str, run_id: str | None = None):
    """
    Orchestrates the full workflow:
    intake -> extraction -> triage -> routing
    All steps are traceable and share run_id.
    """

    if run_id is None:
        run_id = generate_run_id()

    logger.info(
        "Workflow started",
        extra={
            "run_id": run_id,
            "event": "workflow_start",
        },
    )

    try:
        # Intake could have its own @traceable if you add validation
        structured_payload = extract_structured_payload(
            user_message=user_message,
            run_id=run_id,
        )

        triage_result = triage(structured_payload=structured_payload, run_id=run_id)

        routing_decision = route(triage_result=triage_result, run_id=run_id)

        logger.info(
            "Workflow completed successfully",
            extra={
                "run_id": run_id,
                "event": "workflow_success",
                "routing_decision": routing_decision,
            },
        )

        return {
            "run_id": run_id,
            "structured_payload": structured_payload,
            "triage_result": triage_result,
            "routing_decision": routing_decision,
        }

    except Exception as e:
        logger.exception(
            "Workflow failed",
            extra={
                "run_id": run_id,
                "event": "workflow_failure",
                "error": str(e),
            },
        )
        # You can choose to re‑raise or return an error envelope
        raise


def main():
    configure_logging()

    user_message = "Example inbound message from user..."
    run_id = generate_run_id()

    result = run_workflow(user_message=user_message, run_id=run_id)
    print(result)


if __name__ == "__main__":
    main()
