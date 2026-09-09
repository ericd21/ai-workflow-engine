import time
from functools import lru_cache

from langchain_anthropic import ChatAnthropic
from pydantic import SecretStr

from app.config import get_settings
from app.llm.mock import generate_mock_response
from app.logging_config import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_client() -> ChatAnthropic:
    """Build (once) and return the shared ChatAnthropic client.

    Constructed lazily so importing this module never requires an API key —
    only an actual ``anthropic``-provider call does. A missing key is passed
    through as ``None`` so LangChain can still pick it up from the environment.
    """
    settings = get_settings()
    key = settings.anthropic_api_key
    # langchain-anthropic's type hints are stricter than its runtime: `model` /
    # `max_tokens` are pydantic aliases, and `api_key=None` is valid (it then
    # reads ANTHROPIC_API_KEY from the environment).
    return ChatAnthropic(  # type: ignore[call-arg]
        model=settings.anthropic_model,
        api_key=SecretStr(key) if key else None,  # type: ignore[arg-type]
        temperature=settings.anthropic_temperature,
        max_tokens=settings.anthropic_max_tokens,
    )


def _coerce_text(content) -> str:
    """Normalize a LangChain message ``content`` (str or block list) to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(part.get("text", ""))
            else:
                parts.append(str(part))
        return "".join(parts)
    return str(content)


def call_llm(prompt: str) -> str:
    """Call the configured LLM provider and return the raw text response.

    - ``LLM_PROVIDER=mock`` → deterministic offline response, no network.
    - ``LLM_PROVIDER=anthropic`` → ChatAnthropic via LangChain, with
      API-level retry, latency measurement, and structured logging.
    """
    settings = get_settings()

    if settings.llm_provider == "mock":
        logger.info("LLM call served by mock provider", extra={"model": "mock"})
        return generate_mock_response(prompt)

    model_name = settings.anthropic_model
    max_attempts = 2
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        start_time = time.time()

        try:
            response = get_client().invoke(prompt)
            latency_ms = (time.time() - start_time) * 1000

            output_text = _coerce_text(response.content)

            logger.info(
                "LLM call succeeded",
                extra={
                    "model": model_name,
                    "attempt": attempt,
                    "latency_ms": round(latency_ms, 2),
                },
            )

            return output_text

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            last_error = e

            logger.warning(
                "LLM call failed",
                extra={
                    "model": model_name,
                    "attempt": attempt,
                    "latency_ms": round(latency_ms, 2),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )

    logger.error(
        "LLM call failed after max attempts",
        extra={
            "model": model_name,
            "max_attempts": max_attempts,
            "final_error_type": type(last_error).__name__,
            "final_error_message": str(last_error),
        },
    )
    raise RuntimeError(f"LLM API failed after {max_attempts} attempts: {last_error}")
