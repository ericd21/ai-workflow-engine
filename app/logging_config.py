import logging
import json
from logging.handlers import RotatingFileHandler


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "timestamp": self.formatTime(record, self.datefmt),
        }

        # Include extra fields if present
        if hasattr(record, "extra"):
            log_record.update(record.extra)

        return json.dumps(log_record)


def configure_logging(log_to_file: bool = False):
    """
    Configure project-wide logging.
    - JSON logs to console (stdout)
    - Optional rotating file logs
    """

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # JSON console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JsonFormatter())
    root.addHandler(console_handler)

    # Optional rotating file logs
    if log_to_file:
        file_handler = RotatingFileHandler(
            "app.log",
            maxBytes=5_000_000,
            backupCount=5,
        )
        file_handler.setFormatter(JsonFormatter())
        root.addHandler(file_handler)

def get_logger(name: str) -> logging.Logger:
    """
    Convenience helper so every module uses the same logging config.
    """
    return logging.getLogger(name)
