"""The app/main.py CLI, exercised in-process."""

import json

import pytest

from app import main as cli
from app.llm import extractor as extractor_mod
from tests.helpers import make_triage, raw_llm_response


def test_serialize_helper():
    assert cli._serialize(None) is None
    assert cli._serialize({"x": 1}) == {"x": 1}
    assert cli._serialize(make_triage())["final_department"] == "support"


def test_cli_success(capsys, monkeypatch):
    monkeypatch.setattr(extractor_mod, "call_llm", lambda _p: raw_llm_response(department="support"))
    rc = cli.main(["The app crashed on login", "--department", "support"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"
    assert out["routing"]["target"] == "support_queue"
    assert out["run_id"]


def test_cli_failure_returns_1(capsys, monkeypatch):
    def boom(_p):
        raise RuntimeError("llm down")

    monkeypatch.setattr(extractor_mod, "call_llm", boom)
    rc = cli.main(["Something is wrong here", "--department", "other"])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "failed"
    assert out["errors"]


def test_cli_rejects_bad_department():
    with pytest.raises(SystemExit):
        cli.main(["a message", "--department", "hr"])


def test_cli_rejects_short_message(capsys):
    with pytest.raises(SystemExit):
        cli.main(["short", "--department", "other"])
