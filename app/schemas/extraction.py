from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.intake import Department


class Tone(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class Urgency(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ExtractionResult(BaseModel):
    department: Department
    department_confidence: float = Field(..., ge=0.0, le=1.0)

    tone: Tone
    tone_confidence: float = Field(..., ge=0.0, le=1.0)

    urgency: Urgency
    urgency_confidence: float = Field(..., ge=0.0, le=1.0)

    summary: str = Field(..., min_length=5, max_length=1000)
    summary_confidence: float = Field(..., ge=0.0, le=1.0)

    missing_info: list[str] = Field(default_factory=list)

    raw_model_output: str = Field(
        ...,
        description="The unparsed raw LLM output for logging and debugging."
    )
