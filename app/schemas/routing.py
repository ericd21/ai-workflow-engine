from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional

from app.schemas.triage import TriageDecision
from app.schemas.extraction import Category, Urgency


class RoutingTarget(str, Enum):
    support_queue = "support_queue"
    billing_queue = "billing_queue"
    sales_queue = "sales_queue"
    general_queue = "general_queue"
    human_review_queue = "human_review_queue"


class SLA(str, Enum):
    immediate = "immediate"
    one_hour = "one_hour"
    four_hours = "four_hours"
    one_day = "one_day"
    low_priority = "low_priority"


class RoutingDecision(BaseModel):
    # Where the issue is routed
    target: RoutingTarget

    # SLA determined by urgency + category + triage rules
    sla: SLA

    # Whether human review is required
    human_review_required: bool = False

    # Reason for human review (if applicable)
    human_review_reason: Optional[str] = None

    # Final category after triage
    final_category: Category

    # Urgency from triage
    urgency: Urgency

    # Priority from triage
    priority: str

    # Summary propagated from triage
    summary: str

    # Notes for logging/debugging
    routing_notes: Optional[str] = None
