"""Offline stand-in for the Anthropic LLM call.

Active when ``LLM_PROVIDER=mock``. Returns text shaped like a real extraction
response — a JSON object followed by a short prose explanation — so the rest of
the pipeline (parsing, validation, triage, routing) runs unchanged with no
network access and no API key. Light keyword heuristics keep the demo from
being completely static.
"""

import json

_DEPARTMENT_KEYWORDS = {
    "billing": ("bill", "invoice", "charge", "payment", "refund", "subscription", "price"),
    "sales": ("buy", "purchase", "quote", "pricing", "demo", "upgrade plan", "sales"),
    "support": ("error", "bug", "broken", "not working", "issue", "crash", "fail", "help"),
}
_NEGATIVE = (
    "angry", "frustrated", "terrible", "awful", "unacceptable", "worst", "furious",
    "disappointed",
)
_POSITIVE = ("thanks", "thank you", "great", "love", "awesome", "happy", "excellent", "appreciate")
_HIGH_URGENCY = ("urgent", "asap", "immediately", "critical", "emergency", "right now", "outage", "down")


def _first_match(text: str, keywords: dict[str, tuple[str, ...]], default: str) -> str:
    lowered = text.lower()
    for value, needles in keywords.items():
        if any(needle in lowered for needle in needles):
            return value
    return default


def generate_mock_response(prompt: str) -> str:
    """Return a canned-but-input-aware extraction response for ``prompt``."""
    # The extractor appends "User message:\n<message>" to the base prompt.
    message = prompt
    marker = "User message:"
    if marker in prompt:
        message = prompt.split(marker, 1)[1].strip()

    lowered = message.lower()
    department = _first_match(message, _DEPARTMENT_KEYWORDS, "other")

    if any(n in lowered for n in _NEGATIVE):
        tone = "negative"
    elif any(n in lowered for n in _POSITIVE):
        tone = "positive"
    else:
        tone = "neutral"

    urgency = "high" if any(n in lowered for n in _HIGH_URGENCY) else "medium"

    first_line = message.strip().splitlines()[0] if message.strip() else ""
    summary = first_line[:200] if len(first_line) >= 5 else "User submitted a request via the contact form."

    payload = {
        "department": department,
        "department_confidence": 0.82,
        "tone": tone,
        "tone_confidence": 0.8,
        "urgency": urgency,
        "urgency_confidence": 0.75,
        "summary": summary,
        "summary_confidence": 0.9,
        "missing_info": [],
    }

    return (
        json.dumps(payload, indent=2)
        + "\n\nExplanation: mock provider — classified via keyword heuristics, "
        "no live model call was made."
    )
