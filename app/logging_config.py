import contextvars
import json
import logging
import sys
from datetime import datetime, timezone

# Neither var propagates into a threading.Thread started via plain Thread(target=...).start() —
# each new OS thread gets a fresh, empty contextvars.Context. The background ingestion thread
# (app/application/document_service.py) sets job_id_var itself, as the first thing it does, using
# the job_id already passed to it as a function argument — it does not rely on inheriting a value
# set by the request thread that spawned it.
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
job_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("job_id", default=None)

# Fixed allow-list of call-site `extra` fields this app logs. Deliberately not a generic dump of
# every non-standard LogRecord attribute: an allow-list can't accidentally blow up a log line on a
# non-JSON-serializable value (bytes, an ORM object) and documents in one place every field this
# system ever logs. Cost: every new call-site `extra` key must be added here, or it's silently
# dropped from the JSON output.
_EXTRA_ALLOWLIST = (
    "library_id",
    "document_id",
    "source_filename",
    "provider",
    "model",
    "base_url",
    "chunk_count",
    "batch_size",
    "top_k",
    "dense_count",
    "sparse_count",
    "document_count",
)

_HANDLER_MARKER = "_knowledge_api_json_handler"


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.job_id = job_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if getattr(record, "request_id", None):
            payload["request_id"] = record.request_id
        if getattr(record, "job_id", None):
            payload["job_id"] = record.job_id
        for key in _EXTRA_ALLOWLIST:
            if key in record.__dict__:
                payload[key] = record.__dict__[key]
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    """Idempotent: safe to call from every create_app() (including the many per-test calls) and
    from mcp_server's module-level import without ever attaching duplicate handlers.

    Writes to stderr, universally — including for mcp_server, where stdout is the actual
    JSON-RPC protocol channel for its stdio transport. One rule everywhere removes an entire class
    of "accidentally corrupted the MCP protocol stream" bugs, and Docker's `docker logs` merges
    stdout+stderr for the Flask app regardless, so nothing is lost there.
    """
    root = logging.getLogger()
    if any(getattr(handler, _HANDLER_MARKER, False) for handler in root.handlers):
        root.setLevel(level)
        return
    handler = logging.StreamHandler(sys.stderr)
    setattr(handler, _HANDLER_MARKER, True)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(ContextFilter())
    root.addHandler(handler)
    root.setLevel(level)


def set_request_id(value: str | None) -> contextvars.Token:
    return request_id_var.set(value)


def reset_request_id(token: contextvars.Token) -> None:
    request_id_var.reset(token)


def set_job_id(value: str | None) -> None:
    job_id_var.set(value)


def clear_job_id() -> None:
    job_id_var.set(None)
