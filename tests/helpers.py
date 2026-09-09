"""Builders for valid domain objects and canned LLM output used across tests."""

import json
from typing import Any

from app.schemas.extraction import ExtractionResult
from app.schemas.intake import IntakeRequest
from app.schemas.triage import TriageDecision

_EXTRACTION_DEFAULTS: dict[str, Any] = {
    "department": "support",
    "department_confidence": 0.9,
    "tone": "neutral",
    "tone_confidence": 0.9,
    "urgency": "medium",
    "urgency_confidence": 0.9,
    "summary": "A representative request summary that clears the min length.",
    "summary_confidence": 0.9,
    "missing_info": [],
}


def extraction_payload(**overrides: Any) -> dict[str, Any]:
    """The 9 fields the extraction prompt asks the model to return."""
    data = dict(_EXTRACTION_DEFAULTS)
    data.update(overrides)
    return data


def raw_llm_response(*, explanation: str = "Because the keywords say so.", **overrides: Any) -> str:
    """A string shaped like a real model response: JSON object then prose."""
    payload = extraction_payload(**overrides)
    return json.dumps(payload, indent=2) + f"\n\nExplanation: {explanation}"


def make_extraction(**overrides: Any) -> ExtractionResult:
    data = extraction_payload(**overrides)
    data.setdefault("raw_model_output", json.dumps(data))
    return ExtractionResult(**data)


def make_intake(**overrides: Any) -> IntakeRequest:
    data: dict[str, Any] = {
        "name": "Test User",
        "email": "test@example.com",
        "phone": None,
        "department": "support",
        "message": "This is a sufficiently long message for validation.",
    }
    data.update(overrides)
    return IntakeRequest(**data)


def make_triage(**overrides: Any) -> TriageDecision:
    ext = make_extraction()
    data: dict[str, Any] = {
        "final_department": ext.department,
        "department_overridden": False,
        "department_override_reason": None,
        "priority": "medium",
        "human_review_required": False,
        "human_review_reason": None,
        "missing_info": [],
        "department_confidence": ext.department_confidence,
        "tone_confidence": ext.tone_confidence,
        "urgency_confidence": ext.urgency_confidence,
        "summary_confidence": ext.summary_confidence,
        "tone": ext.tone,
        "urgency": ext.urgency,
        "summary": ext.summary,
        "triage_notes": "test",
    }
    data.update(overrides)
    return TriageDecision(**data)
