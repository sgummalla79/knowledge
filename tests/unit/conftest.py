from contextlib import ExitStack
from unittest.mock import patch
from uuid import uuid4

import pytest


@pytest.fixture(autouse=True)
def _mock_default_org_and_user_id():
    """Unit/route tests are HTTP-layer only (services mocked, no real DB) — container.
    get_default_org_id()/get_default_user_id() would otherwise need a real Postgres connection to
    bootstrap/query the default org and admin user (there's no auth layer yet to resolve these
    from — see docs/DATA_MODEL.md). Patched globally, at their single source in app.container, so
    every route calling them via `container.get_default_org_id()`/`container.get_default_user_id()`
    (module-qualified, not a direct name import) sees the mock without each test needing to know
    this plumbing exists."""
    with ExitStack() as stack:
        stack.enter_context(patch("app.container.get_default_org_id", return_value=uuid4()))
        stack.enter_context(patch("app.container.get_default_user_id", return_value=uuid4()))
        yield
