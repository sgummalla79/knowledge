import logging

import pytest

from api.infrastructure.orm.db_fault_logging import _handle_error, _operation_keyword, _sqlstate_of


class _FakeOriginalException:
    def __init__(self, pgcode=None, sqlstate=None):
        self.pgcode = pgcode
        self.sqlstate = sqlstate


class _FakeExceptionContext:
    def __init__(self, original_exception=None, statement=None):
        self.original_exception = original_exception
        self.statement = statement


@pytest.mark.parametrize("statement,expected", [("select 1", "SELECT"), ("  UPDATE t set x=1", "UPDATE"), ("", "UNKNOWN"), (None, "UNKNOWN")])
def test_operation_keyword(statement, expected):
    assert _operation_keyword(statement) == expected


def test_sqlstate_of_prefers_sqlstate_attr():
    ctx = _FakeExceptionContext(original_exception=_FakeOriginalException(pgcode="ignored", sqlstate="40P01"))
    assert _sqlstate_of(ctx) == "40P01"


def test_sqlstate_of_falls_back_to_pgcode():
    ctx = _FakeExceptionContext(original_exception=_FakeOriginalException(pgcode="55P03"))
    assert _sqlstate_of(ctx) == "55P03"


def test_sqlstate_of_none_when_no_original_exception():
    assert _sqlstate_of(_FakeExceptionContext(original_exception=None)) is None


def test_handle_error_logs_known_fault_at_warning(caplog):
    ctx = _FakeExceptionContext(
        original_exception=_FakeOriginalException(pgcode="25P03"),
        statement="UPDATE identities SET last_active_at = now()",
    )
    with caplog.at_level(logging.WARNING, logger="api.infrastructure.orm.db_fault_logging"):
        _handle_error(ctx)
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.WARNING
    assert record.sqlstate == "25P03"
    assert record.db_fault == "db_idle_in_transaction_timeout"
    assert record.operation == "UPDATE"


def test_handle_error_logs_deadlock_at_error(caplog):
    ctx = _FakeExceptionContext(original_exception=_FakeOriginalException(pgcode="40P01"), statement="SELECT 1")
    with caplog.at_level(logging.WARNING, logger="api.infrastructure.orm.db_fault_logging"):
        _handle_error(ctx)
    assert caplog.records[0].levelno == logging.ERROR
    assert caplog.records[0].db_fault == "db_deadlock"


def test_handle_error_ignores_unknown_sqlstate(caplog):
    ctx = _FakeExceptionContext(original_exception=_FakeOriginalException(pgcode="42P01"), statement="SELECT 1")
    with caplog.at_level(logging.WARNING, logger="api.infrastructure.orm.db_fault_logging"):
        _handle_error(ctx)
    assert caplog.records == []


def test_handle_error_ignores_non_dbapi_errors(caplog):
    ctx = _FakeExceptionContext(original_exception=None, statement=None)
    with caplog.at_level(logging.WARNING, logger="api.infrastructure.orm.db_fault_logging"):
        _handle_error(ctx)
    assert caplog.records == []
