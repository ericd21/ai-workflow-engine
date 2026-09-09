import pytest
from langchain_anthropic import ChatAnthropic

from app.llm import client as client_mod
from app.llm.client import _coerce_text, call_llm, get_client


class _FakeMsg:
    def __init__(self, content):
        self.content = content


def test_mock_provider_path(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    out = call_llm("User message:\nhello there this is fine")
    assert "department" in out


def test_anthropic_success(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(client_mod, "get_client", lambda: _Client(["ok text"]))
    assert call_llm("hi") == "ok text"


def test_anthropic_retry_then_success(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    client = _Client([RuntimeError("transient"), "second try"])
    monkeypatch.setattr(client_mod, "get_client", lambda: client)
    assert call_llm("hi") == "second try"
    assert client.calls == 2


def test_anthropic_all_attempts_fail(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    client = _Client([RuntimeError("down"), RuntimeError("down")])
    monkeypatch.setattr(client_mod, "get_client", lambda: client)
    with pytest.raises(RuntimeError, match="after 2 attempts"):
        call_llm("hi")


def test_coerce_text_variants():
    assert _coerce_text("plain") == "plain"
    assert _coerce_text([{"text": "a"}, {"text": "b"}]) == "ab"
    assert _coerce_text([{"type": "text", "text": "x"}, "y"]) == "xy"
    assert _coerce_text(None) == "None"  # fallback for unexpected shapes


def test_get_client_builds_chatanthropic(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    get_client.cache_clear()
    client = get_client()  # construction only, no network
    assert isinstance(client, ChatAnthropic)


class _Client:
    """Fake ChatAnthropic: each invoke() yields the next scripted value/exception."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    def invoke(self, _prompt):
        item = self._script[self.calls]
        self.calls += 1
        if isinstance(item, Exception):
            raise item
        return _FakeMsg(item)
