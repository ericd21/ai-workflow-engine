from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.extraction import Tone, Urgency
from app.schemas.intake import Department


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TriageDecision(BaseModel):
    # Final department after deterministic rules
    final_department: Department

    # Whether the submitted department was overridden
    department_overridden: bool = False
    department_override_reason: str | None = None

    # Priority assigned by rules engine
    priority: Priority

    # Human review flag
    human_review_required: bool = False
    human_review_reason: str | None = None

    # Missing info propagated from extraction
    missing_info: list[str] = Field(default_factory=list)

    # Confidence signals (copied from extraction)
    department_confidence: float = Field(..., ge=0.0, le=1.0)
    tone_confidence: float = Field(..., ge=0.0, le=1.0)
    urgency_confidence: float = Field(..., ge=0.0, le=1.0)
    summary_confidence: float = Field(..., ge=0.0, le=1.0)

    # Normalized fields from extraction
    tone: Tone
    urgency: Urgency
    summary: str

    # Optional: triage notes for logging/debugging
    triage_notes: str | None = None
