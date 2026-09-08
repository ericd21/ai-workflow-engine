from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, List

from app.schemas.extraction import Category, Tone, Urgency


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TriageDecision(BaseModel):
    # Final category after deterministic rules
    final_category: Category

    # Whether the dropdown was overridden
    category_overridden: bool = False
    category_override_reason: Optional[str] = None

    # Priority assigned by rules engine
    priority: Priority

    # Human review flag
    human_review_required: bool = False
    human_review_reason: Optional[str] = None

    # Missing info propagated from extraction
    missing_info: List[str] = Field(default_factory=list)

    # Confidence signals (copied from extraction)
    category_confidence: float = Field(..., ge=0.0, le=1.0)
    tone_confidence: float = Field(..., ge=0.0, le=1.0)
    urgency_confidence: float = Field(..., ge=0.0, le=1.0)
    summary_confidence: float = Field(..., ge=0.0, le=1.0)

    # Normalized fields from extraction
    tone: Tone
    urgency: Urgency
    summary: str

    # Optional: triage notes for logging/debugging
    triage_notes: Optional[str] = None
