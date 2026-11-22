import json
import logging
from datetime import datetime, timezone
from typing import Any


class StructuredJSONFormatter(logging.Formatter):
    # Model names, counts, schema names and fixed reason codes (e.g. "gemini:http_429") are
    # configuration or classification, never case data, prompts or model output.
    _safe_fields = ("request_id", "method", "path", "status_code", "exception_type", "provider", "model",
                    "attempts", "schema", "reason")

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": (
                datetime.fromtimestamp(record.created, tz=timezone.utc)
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z")
            ),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": getattr(record, "event", "application.log"),
        }
        for field in self._safe_fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str) -> logging.Logger:
    logger = logging.getLogger("pokkhoai")
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredJSONFormatter())
        logger.addHandler(handler)
    return logger
