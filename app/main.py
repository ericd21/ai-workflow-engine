"""Command-line entry point: run a single workflow from the terminal.

Thin wrapper around ``WorkflowEngine`` — handy for quick manual checks. Pair it
with ``LLM_PROVIDER=mock`` to run end to end with no API key and no network:

    python -m app.main "The billing page shows the wrong amount" --department billing
"""

import argparse
import json
import sys

from app.logging_config import configure_logging
from app.schemas.intake import Department, IntakeRequest
from app.workflow.engine import engine
from app.workflow.errors import WorkflowError


def _serialize(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app.main",
        description="Run one AI workflow (intake → extraction → triage → routing).",
    )
    parser.add_argument("message", help="The inbound user message to process.")
    parser.add_argument("--name", default="CLI User", help="Submitter name.")
    parser.add_argument(
        "--department",
        default="other",
        choices=[d.value for d in Department],
        help="Department picked on the form (default: other).",
    )
    parser.add_argument("--email", default="cli@example.com", help="Contact email.")
    parser.add_argument("--phone", default=None, help="Contact phone (optional).")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    configure_logging()

    try:
        intake = IntakeRequest(
            name=args.name,
            email=args.email,
            phone=args.phone,
            department=Department(args.department),
            message=args.message,
        )
    except Exception as e:  # pydantic ValidationError, etc.
        parser.error(f"invalid intake: {e}")

    try:
        result = engine.run_workflow(intake)
    except WorkflowError as e:
        print(
            json.dumps(
                {"run_id": e.run_id, "status": "failed", "errors": e.errors}, indent=2
            )
        )
        return 1

    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "status": "ok",
                "routing": _serialize(result.get("routing")),
                "triage": _serialize(result.get("triage")),
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
