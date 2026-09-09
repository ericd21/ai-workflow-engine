import json
import logging
from logging.handlers import RotatingFileHandler

# Attribute names present on a stock LogRecord. Anything on a record that is
# NOT in here was supplied by the caller via `logger.info(..., extra={...})`.
_RESERVED_ATTRS = set(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
    "taskName",
}

# Marker so configure_logging() can find and replace its own handlers on a
# re-run instead of stacking duplicates.
_HANDLER_MARKER = "_workflow_json_handler"
_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Merge structured `extra=` fields (flattened onto the record by logging).
        for key, value in record.__dict__.items():
            if key not in _RESERVED_ATTRS and not key.startswith("_"):
                log_record[key] = value

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            log_record["stack_info"] = self.formatStack(record.stack_info)

        # default=str keeps enums / datetimes / models from breaking json.dumps.
        return json.dumps(log_record, default=str)


def _make_handler(handler: logging.Handler) -> logging.Handler:
    handler.setFormatter(JsonFormatter())
    setattr(handler, _HANDLER_MARKER, True)
    return handler


def configure_logging(log_to_file: bool | None = None, *, force: bool = False) -> None:
    """
    Configure project-wide logging: JSON to stdout, optional rotating file.

    Idempotent — calling it again replaces the handlers it added rather than
    appending new ones (so main + FastAPI startup don't double every line).
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    if log_to_file is None:
        # Imported lazily to avoid a circular import at module load.
        from app.config import get_settings

        log_to_file = get_settings().log_to_file

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    for existing in list(root.handlers):
        if getattr(existing, _HANDLER_MARKER, False):
            root.removeHandler(existing)

    root.addHandler(_make_handler(logging.StreamHandler()))

    if log_to_file:
        root.addHandler(
            _make_handler(
                RotatingFileHandler("app.log", maxBytes=5_000_000, backupCount=5)
            )
        )

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Convenience helper so every module uses the same logging config."""
    return logging.getLogger(name)
