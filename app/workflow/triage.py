from langsmith import traceable

from app.config import get_settings
from app.logging_config import get_logger
from app.schemas.extraction import ExtractionResult, Urgency
from app.schemas.intake import Department
from app.schemas.triage import Priority, TriageDecision

logger = get_logger(__name__)


@traceable(name="deterministic_triage")
def run_triage(
    extraction: ExtractionResult,
    run_id: str,
    submitted_department: Department,
) -> TriageDecision:
    """
    Deterministic triage step.

    Consumes the LLM ``ExtractionResult`` plus the department the user picked on
    the form (``submitted_department``) and produces a ``TriageDecision``.
    """

    logger.info(
        "Starting triage step",
        extra={"run_id": run_id, "event": "triage_start"}
    )

    settings = get_settings()
    threshold = settings.department_confidence_threshold

    extracted_department: Department = extraction.department
    extracted_urgency: Urgency = extraction.urgency

    department_overridden = False
    department_override_reason = None
    human_review_required = False
    human_review_reason = None

    # ---------------------------------------------------------
    # 1. Reconcile submitted vs. extracted department
    # ---------------------------------------------------------

    if extracted_department == submitted_department:
        final_department = submitted_department
    elif extraction.department_confidence >= threshold:
        # Confident disagreement → the LLM wins.
        final_department = extracted_department
        department_overridden = True
        department_override_reason = (
            f"LLM reclassified from '{submitted_department.value}' to "
            f"'{extracted_department.value}' "
            f"(confidence {extraction.department_confidence:.2f} >= {threshold:.2f})"
        )
    else:
        # Unconfident disagreement → keep the user's choice, flag for a human.
        final_department = submitted_department
        human_review_required = True
        human_review_reason = (
            f"Ambiguous department: user chose '{submitted_department.value}', "
            f"LLM suggested '{extracted_department.value}' at low confidence "
            f"({extraction.department_confidence:.2f} < {threshold:.2f})"
        )

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
    # 3. Additional human-review triggers (never clears an existing flag)
    # ---------------------------------------------------------

    if extraction.summary_confidence < 0.50:
        human_review_required = True
        human_review_reason = "Low summary confidence"

    if "order_number" in extraction.missing_info:
        human_review_required = True
        human_review_reason = "Missing critical field: order_number"

    # ---------------------------------------------------------
    # 4. Build TriageDecision object
    # ---------------------------------------------------------

    decision = TriageDecision(
        final_department=final_department,
        department_overridden=department_overridden,
        department_override_reason=department_override_reason,
        priority=priority,
        human_review_required=human_review_required,
        human_review_reason=human_review_reason,
        missing_info=extraction.missing_info,
        department_confidence=extraction.department_confidence,
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
            "final_department": decision.final_department,
            "department_overridden": decision.department_overridden,
            "priority": decision.priority,
            "human_review_required": decision.human_review_required,
            "missing_info": decision.missing_info,
        },
    )

    return decision
