from langsmith import traceable

from app.logging_config import get_logger
from app.schemas.extraction import ExtractionResult, Category, Urgency
from app.schemas.triage import TriageDecision, Priority

logger = get_logger(__name__)


@traceable(name="deterministic_triage")
def run_triage(extraction: ExtractionResult, run_id: str) -> TriageDecision:
    """
    Deterministic triage step.
    Consumes ExtractionResult and produces a TriageDecision.
    """

    logger.info(
        "Starting triage step",
        extra={"run_id": run_id, "event": "triage_start"}
    )

    # ---------------------------------------------------------
    # 1. Determine final category (deterministic rules)
    # ---------------------------------------------------------

    extracted_category: Category = extraction.category
    extracted_urgency: Urgency = extraction.urgency

    category_overridden = False
    category_override_reason = None

    # Example deterministic override rules
    if extracted_category == Category.support and "error_code" in extraction.missing_info:
        final_category = Category.support
        category_overridden = True
        category_override_reason = "Support category forced due to missing error_code"
    else:
        final_category = extracted_category

    # ---------------------------------------------------------
    # 2. Determine priority (deterministic rules)
    # ---------------------------------------------------------

    if extracted_urgency == Urgency.high:
        priority = Priority.high
    elif extracted_urgency == Urgency.medium:
        priority = Priority.medium
    else:
        priority = Priority.low

    # ---------------------------------------------------------
    # 3. Determine human review requirement
    # ---------------------------------------------------------

    human_review_required = False
    human_review_reason = None

    # Example rule: low confidence → human review
    if extraction.category_confidence < 0.55:
        human_review_required = True
        human_review_reason = "Low category confidence"

    if extraction.summary_confidence < 0.50:
        human_review_required = True
        human_review_reason = "Low summary confidence"

    # Example rule: missing critical info
    if "order_number" in extraction.missing_info:
        human_review_required = True
        human_review_reason = "Missing critical field: order_number"

    # ---------------------------------------------------------
    # 4. Build TriageDecision object
    # ---------------------------------------------------------

    decision = TriageDecision(
        final_category=final_category,
        category_overridden=category_overridden,
        category_override_reason=category_override_reason,
        priority=priority,
        human_review_required=human_review_required,
        human_review_reason=human_review_reason,
        missing_info=extraction.missing_info,
        category_confidence=extraction.category_confidence,
        tone_confidence=extraction.tone_confidence,
        urgency_confidence=extraction.urgency_confidence,
        summary_confidence=extraction.summary_confidence,
        tone=extraction.tone,
        urgency=extraction.urgency,
        summary=extraction.summary,
        triage_notes="Deterministic triage completed successfully",
    )

    # ---------------------------------------------------------
    # 5. Logging
    # ---------------------------------------------------------

    logger.info(
        "Triage completed",
        extra={
            "run_id": run_id,
            "event": "triage_complete",
            "final_category": decision.final_category,
            "priority": decision.priority,
            "human_review_required": decision.human_review_required,
            "missing_info": decision.missing_info,
        },
    )

    return decision
