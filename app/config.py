"""Central configuration.

Loads `.env` once on import and exposes runtime settings plus a couple of
shared helpers. Every module that needs an environment value should go through
`get_settings()` rather than reading `os.environ` directly.
"""

import os
import uuid

from dotenv import load_dotenv

load_dotenv()


def generate_run_id() -> str:
    """Create a unique identifier for a single workflow run."""
    return str(uuid.uuid4())


def _get_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    """Runtime settings resolved from the environment.

    A fresh instance is cheap to build; `get_settings()` returns a new one on
    each call so tests can `monkeypatch.setenv(...)` without cache juggling.
    """

    def __init__(self) -> None:
        # LLM provider: "anthropic" (real API) or "mock" (offline stand-in).
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()

        # Anthropic client config.
        self.anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
        self.anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
        self.anthropic_temperature: float = float(os.getenv("ANTHROPIC_TEMPERATURE", "0.2"))
        self.anthropic_max_tokens: int = int(os.getenv("ANTHROPIC_MAX_TOKENS", "1000"))

        # LangSmith tracing (the @traceable decorators are no-ops without this).
        self.langsmith_tracing: bool = _get_bool("LANGSMITH_TRACING", False)

        # Logging.
        self.log_to_file: bool = _get_bool("LOG_TO_FILE", False)

        # Triage: minimum extraction confidence required before the LLM is
        # allowed to override the submitted department (see app/workflow/triage.py).
        self.department_confidence_threshold: float = float(
            os.getenv("DEPARTMENT_CONFIDENCE_THRESHOLD", "0.6")
        )


def get_settings() -> Settings:
    """Return the current runtime settings (re-read from the environment)."""
    return Settings()
