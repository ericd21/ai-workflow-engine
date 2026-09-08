from typing import Any, Dict
from langsmith import traceable
import json
from app.schemas.intake import IntakePayload
from app.schemas.extraction import ExtractionResult
from app.llm.prompts.extraction import EXTRACTION_PROMPT
from app.llm.client import call_llm
from app.logging_config import get_logger


logger = get_logger(__name__)

# ---------------------------------------------------------
# Helper: Parse JSON with strict validation
# ---------------------------------------------------------

def _parse_extraction_json(raw_output: str, run_id) -> Dict[str, Any]:
    """
    Strict JSON parsing with helpful error messages.
    """

    logger.debug(
        "Parsing raw LLM output for JSON block",
        extra={"run_id": run_id, "event": "extractor_parse_start"}
    )
    
    try:
        # Extract only the first JSON object
        json_start = raw_output.find("{")
        json_end = raw_output.find("}") + 1

        if json_start == -1 or json_end == -1:
            raise ValueError("Model did not return a JSON object.")

        json_block = raw_output[json_start:json_end]
        data = json.loads(json_block)
    except Exception as e:
        # could log the effor here or in the calling function with attempt #
        raise ValueError(f"Malformed JSON from model: {e}")

    required_fields = {
        "category",
        "category_confidence",
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
def run_extraction(intake: IntakePayload, run_id) -> ExtractionResult:
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
            # ---------------------------------------------------------
            # Call your model here (OpenAI, Anthropic, Azure, etc.)
            # ---------------------------------------------------------
            raw_output = call_llm(prompt)  # You will implement this

            # Parse JSON strictly
            parsed = _parse_extraction_json(raw_output)

            # Convert to Pydantic model
            result = ExtractionResult(
                category=parsed["category"],
                category_confidence=parsed["category_confidence"],
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

            # If malformed JSON, retry
            if attempt < max_attempts:
                continue
            else:
                # Final failure — raise with context
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
            