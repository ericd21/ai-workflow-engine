import json
import logging
import sys
from enum import Enum

import app.logging_config as lc
from app.logging_config import JsonFormatter, configure_logging


def _record(level=logging.INFO, msg="hello", exc_info=None, **extra):
    rec = logging.LogRecord("test.logger", level, "path.py", 10, msg, None, exc_info)
    for key, value in extra.items():
        setattr(rec, key, value)
    return rec


def test_formatter_emits_extra_fields():
    out = json.loads(JsonFormatter().format(_record(run_id="abc", event="thing")))
    assert out["run_id"] == "abc"
    assert out["event"] == "thing"
    assert out["message"] == "hello"
    assert out["level"] == "INFO"
    assert out["logger"] == "test.logger"


def test_formatter_serializes_non_json_types():
    class E(str, Enum):
        x = "x"

    out = json.loads(JsonFormatter().format(_record(dept=E.x, nested={"k": E.x})))
    assert out["dept"] == "x"
    assert out["nested"] == {"k": "x"}


def test_formatter_renders_exception():
    try:
        raise ValueError("boom")
    except ValueError:
        rec = _record(level=logging.ERROR, exc_info=sys.exc_info())
    out = json.loads(JsonFormatter().format(rec))
    assert "ValueError: boom" in out["exception"]


def test_formatter_ignores_standard_record_attrs():
    out = json.loads(JsonFormatter().format(_record()))
    assert set(out) == {"timestamp", "level", "logger", "message"}


def test_formatter_renders_stack_info():
    rec = _record()
    rec.stack_info = 'Stack (most recent call last):\n  File "x", line 1'
    out = json.loads(JsonFormatter().format(rec))
    assert "Stack" in out["stack_info"]


def test_configure_logging_adds_file_handler(tmp_path, monkeypatch):
    from logging.handlers import RotatingFileHandler

    monkeypatch.chdir(tmp_path)
    lc._CONFIGURED = False
    configure_logging(log_to_file=True)
    handlers = [h for h in logging.getLogger().handlers if getattr(h, lc._HANDLER_MARKER, False)]
    assert any(isinstance(h, RotatingFileHandler) for h in handlers)


def test_configure_logging_reads_log_to_file_from_settings(monkeypatch):
    monkeypatch.setenv("LOG_TO_FILE", "false")
    lc._CONFIGURED = False
    configure_logging()  # no arg → consult settings
    from logging.handlers import RotatingFileHandler

    handlers = [h for h in logging.getLogger().handlers if getattr(h, lc._HANDLER_MARKER, False)]
    assert not any(isinstance(h, RotatingFileHandler) for h in handlers)


def test_configure_logging_is_idempotent():
    lc._CONFIGURED = False
    configure_logging(log_to_file=False)
    configure_logging(log_to_file=False)
    configure_logging(log_to_file=False, force=True)
    ours = [h for h in logging.getLogger().handlers if getattr(h, lc._HANDLER_MARKER, False)]
    assert len(ours) == 1


def test_configure_logging_skips_when_already_configured():
    lc._CONFIGURED = True
    before = list(logging.getLogger().handlers)
    configure_logging()
    assert logging.getLogger().handlers == before
