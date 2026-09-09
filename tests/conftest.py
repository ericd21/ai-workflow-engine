import logging

import pytest

from app import logging_config
from app.llm import client as llm_client


@pytest.fixture(autouse=True)
def _safe_env(monkeypatch):
    """Every test runs offline by default.

    - ``LLM_PROVIDER=mock`` so an un-mocked ``call_llm`` never hits the network.
    - A fake key + tracing off so imports and ``@traceable`` stay inert.
    Tests that exercise the real Anthropic code path override ``LLM_PROVIDER``
    and patch ``app.llm.client.get_client``.
    """
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("DEPARTMENT_CONFIDENCE_THRESHOLD", "0.6")
    _clear_client_cache()
    yield
    _clear_client_cache()


def _clear_client_cache():
    # Tests may monkeypatch get_client with a plain callable that has no cache.
    clear = getattr(llm_client.get_client, "cache_clear", None)
    if clear is not None:
        clear()


@pytest.fixture(autouse=True)
def _reset_logging():
    """Undo anything configure_logging() attached to the root logger."""
    yield
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, logging_config._HANDLER_MARKER, False):
            root.removeHandler(handler)
    logging_config._CONFIGURED = False
