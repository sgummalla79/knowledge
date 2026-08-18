from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _skip_rls_session_vars():
    """Unit/route tests are HTTP-layer only (services mocked, no real DB involved) —
    require_org_session/login_required call container.set_rls_session_vars() on every
    authenticated request, which needs a real Postgres connection (see docs/DATA_MODEL.md's Row-
    level security section). Patched globally, at the name auth_ui actually calls (imported
    directly via `from api.container import set_rls_session_vars`, so patching api.container's
    copy wouldn't reach it), so no route test needs its own DB just to pass through auth."""
    with patch("api.presentation.routes.auth_ui.set_rls_session_vars"):
        yield
