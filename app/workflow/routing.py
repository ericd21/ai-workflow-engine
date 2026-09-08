from langsmith import traceable

from app.logging_config import get_logger
from app.schemas.triage import TriageDecision
from app.schemas.routing import RoutingDecision, RoutingTarget, SLA
from app.schemas.extraction import Category, Urgency


logger = get_logger(__name__)


@traceable(name="deterministic_routing")
def run_routing(triage: TriageDecision, run_id: str) -> RoutingDecision:
    """
    Deterministic routing step.
    Consumes TriageDecision and produces RoutingDecision.
    """

    logger.info(
        "Starting routing step",
        extra={"run_id": run_id, "event": "routing_start"}
    )

    final_category: Category = triage.final_category
    urgency: Urgency = triage.urgency
    priority = triage.priority
    human_review_required = triage.human_review_required
    human_review_reason = triage.human_review_reason

    # ---------------------------------------------------------
    # 1. Determine routing target
    # ---------------------------------------------------------

    if human_review_required:
        target = RoutingTarget.human_review_queue

    else:
        if final_category == Category.support:
            target = RoutingTarget.support_queue
        elif final_category == Category.billing:
            target = RoutingTarget.billing_queue
        elif final_category == Category.sales:
            target = RoutingTarget.sales_queue
        else:
            target = RoutingTarget.general_queue

    # ---------------------------------------------------------
    # 2. Determine SLA (deterministic rules)
    # ---------------------------------------------------------

    if human_review_required:
        sla = SLA.one_hour

    else:
        if urgency == Urgency.high:
            sla = SLA.immediate
        elif urgency == Urgency.medium:
            sla = SLA.one_hour
        elif urgency == Urgency.low:
            sla = SLA.four_hours
        else:
            sla = SLA.low_priority

    # ---------------------------------------------------------
    # 3. Build RoutingDecision object
    # ---------------------------------------------------------

    decision = RoutingDecision(
        target=target,
        sla=sla,
        human_review_required=human_review_required,
        human_review_reason=human_review_reason,
        final_category=final_category,
        urgency=urgency,
        priority=priority,
        summary=triage.summary,
        routing_notes="Deterministic routing completed successfully",
    )

    # ---------------------------------------------------------
    # 4. Logging
    # ---------------------------------------------------------

    logger.info(
        "Routing completed",
        extra={
            "run_id": run_id,
            "event": "routing_complete",
            "target": decision.target,
            "sla": decision.sla,
            "human_review_required": decision.human_review_required,
            "final_category": decision.final_category,
            "urgency": decision.urgency,
            "priority": decision.priority,
        },
    )

    return decision
