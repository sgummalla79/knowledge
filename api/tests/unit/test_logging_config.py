import json
import logging
import sys

import pytest

from api.logging_config import (
    ContextFilter,
    JsonFormatter,
    clear_job_id,
    configure_logging,
    reset_request_id,
    set_job_id,
    set_request_id,
)

# Tests the JsonFormatter/ContextFilter classes directly against manually-built LogRecords, rather
# than capturing real stderr output through the shared, idempotent configure_logging() handler —
# logging.StreamHandler binds to whatever `sys.stderr` object existed at construction time, which
# (since configure_logging is idempotent and likely already called earlier in the test session by
# some other test's create_app()) may not be the same object capsys swaps in for this test. Testing
# the formatter/filter in isolation is both more robust and more standard unit-testing practice.


@pytest.fixture(autouse=True)
def _restore_root_logger_level():
    original_level = logging.getLogger().level
    yield
    logging.getLogger().level = original_level


@pytest.fixture(autouse=True)
def _clear_context_after_test():
    # contextvars aren't function-scoped by pytest — a set_job_id/set_request_id call in one test
    # (or leaked from a bug elsewhere, as previously happened here) persists into later tests
    # running in the same thread unless explicitly cleared.
    yield
    clear_job_id()
    set_request_id(None)


def _make_record(level=logging.INFO, msg="hello", exc_info=None, extra=None):
    logger = logging.getLogger("test.logger")
    return logger.makeRecord("test.logger", level, __file__, 1, msg, (), exc_info, extra=extra)


def _format(record):
    ContextFilter().filter(record)
    return json.loads(JsonFormatter().format(record))


def test_json_formatter_basic_shape():
    payload = _format(_make_record())
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert payload["message"] == "hello"
    assert "timestamp" in payload
    assert "module" in payload
    assert "line" in payload
    assert "request_id" not in payload
    assert "job_id" not in payload


def test_json_formatter_includes_request_id_when_set():
    token = set_request_id("req-123")
    try:
        payload = _format(_make_record())
    finally:
        reset_request_id(token)
    assert payload["request_id"] == "req-123"


def test_json_formatter_includes_job_id_when_set():
    set_job_id("job-456")
    try:
        payload = _format(_make_record())
    finally:
        clear_job_id()
    assert payload["job_id"] == "job-456"


def test_json_formatter_includes_exception_traceback():
    try:
        raise ValueError("boom")
    except ValueError:
        record = _make_record(exc_info=sys.exc_info())
    payload = _format(record)
    assert "ValueError" in payload["exception"]
    assert "boom" in payload["exception"]


def test_json_formatter_includes_allowlisted_extra_field():
    payload = _format(_make_record(extra={"category_id": "cat-1"}))
    assert payload["category_id"] == "cat-1"


def test_json_formatter_drops_non_allowlisted_extra_field():
    payload = _format(_make_record(extra={"not_a_real_field": "y"}))
    assert "not_a_real_field" not in payload


def test_configure_logging_is_idempotent():
    configure_logging("INFO")
    configure_logging("DEBUG")
    marked = [h for h in logging.getLogger().handlers if getattr(h, "_knowledge_json_handler", False)]
    assert len(marked) == 1


def test_configure_logging_updates_level_on_repeat_calls():
    configure_logging("WARNING")
    assert logging.getLogger().getEffectiveLevel() == logging.WARNING
    configure_logging("INFO")
    assert logging.getLogger().getEffectiveLevel() == logging.INFO
