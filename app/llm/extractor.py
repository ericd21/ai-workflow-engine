import json
from typing import Any

from langsmith import traceable

from app.llm.client import call_llm
from app.llm.prompts.extraction import EXTRACTION_PROMPT
from app.logging_config import get_logger
from app.schemas.extraction import ExtractionResult
from app.schemas.intake import IntakeRequest

logger = get_logger(__name__)

# ---------------------------------------------------------
# Helper: Parse JSON with strict validation
# ---------------------------------------------------------

def _extract_first_json_object(text: str) -> str | None:
    """Return the first balanced ``{...}`` block in ``text`` (or None).

    Walks from the first ``{`` matching braces while ignoring any that appear
    inside string literals, so a trailing prose explanation — or nested objects
    in the payload — don't truncate or corrupt the slice.
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _parse_extraction_json(raw_output: str, run_id) -> dict[str, Any]:
    """
    Strict JSON parsing with helpful error messages.
    """

    logger.debug(
        "Parsing raw LLM output for JSON block",
        extra={"run_id": run_id, "event": "extractor_parse_start"}
    )
    
    json_block = _extract_first_json_object(raw_output)
    if json_block is None:
        raise ValueError("Model did not return a JSON object.")

    try:
        data = json.loads(json_block)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON from model: {e}")

    if not isinstance(data, dict):
        raise ValueError("Model returned JSON that is not an object.")

    required_fields = {
        "department",
        "department_confidence",
        "tone",
        "tone_confidence",
        "urgency",
        "urgency_confidence",
        "summary",
        "summary_confidence",
        "missing_info",
    }

    missing = required_fields - set(data.keys())
    if missing:
        logger.error(
            "Missing required fields in extraction JSON",
            extra={"run_id": run_id, "event": "extractor_missing_fields", "missing": list(missing)}
        )
        raise ValueError(f"Missing required fields: {missing}")

    logger.debug(
        "Extraction JSON parsed successfully",
        extra={"run_id": run_id, "event": "extractor_parse_success"}
    )

    return data

# ---------------------------------------------------------
# Main Extraction Function (with LangSmith tracing)
# ---------------------------------------------------------

@traceable(name="llm_extraction")
def run_extraction(intake: IntakeRequest, run_id) -> ExtractionResult:
    """
    Run the LLM extraction step with retry logic for malformed JSON.
    """

    user_message = intake.message

    logger.info(
        "Starting extraction step",
        extra={"run_id": run_id, "event": "extractor_start"}
    )

    # Build the final prompt
    prompt = EXTRACTION_PROMPT + f"\n\nUser message:\n{user_message}\n"

    # Retry loop
    max_attempts = 3
    last_error = None

    for attempt in range(1, max_attempts + 1):
        logger.info(
            "Calling LLM for extraction",
            extra={"run_id": run_id, "event": "extractor_llm_call", "attempt": attempt}
        )
        try:
            raw_output = call_llm(prompt)

            # Parse JSON strictly
            parsed = _parse_extraction_json(raw_output, run_id)

            # Convert to Pydantic model
            result = ExtractionResult(
                department=parsed["department"],
                department_confidence=parsed["department_confidence"],
                tone=parsed["tone"],
                tone_confidence=parsed["tone_confidence"],
                urgency=parsed["urgency"],
                urgency_confidence=parsed["urgency_confidence"],
                summary=parsed["summary"],
                summary_confidence=parsed["summary_confidence"],
                missing_info=parsed["missing_info"],
                raw_model_output=raw_output,
            )

            logger.info(
                "Extraction succeeded",
                extra={"run_id": run_id, "event": "extractor_success", "attempt": attempt}
            )

            return result

        except Exception as e:
            last_error = e

            logger.warning(
                "Extraction attempt failed",
                extra={
                    "run_id": run_id,
                    "event": "extractor_attempt_failed",
                    "attempt": attempt,
                    "error": str(e),
                },
            )

    # All attempts exhausted — raise with context.
    logger.error(
        "Extraction failed after all retries",
        extra={
            "run_id": run_id,
            "event": "extractor_failure",
            "error": str(last_error),
        },
    )
    raise RuntimeError(
        f"Extraction failed after {max_attempts} attempts: {last_error}"
    )
