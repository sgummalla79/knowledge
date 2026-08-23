from unittest.mock import patch

import pytest

from api.constants import OBJECT_PERMISSIONS


@pytest.fixture(autouse=True)
def _skip_rls_session_vars():
    """Unit/route tests are HTTP-layer only (services mocked, no real DB involved) —
    require_org_session/require_permission call container.set_rls_session_vars() on every
    authenticated request, which needs a real Postgres connection (see docs/DATA_MODEL.md's
    Row-level security section). Patched globally, at each name that actually calls it (both
    import it directly via `from api.container import set_rls_session_vars`, so patching
    api.container's copy wouldn't reach either), so no route test needs its own DB just to pass
    through auth."""
    with (
        patch("api.presentation.routes.auth_ui.set_rls_session_vars"),
        patch("api.presentation.routes.app_auth.set_rls_session_vars"),
    ):
        yield


@pytest.fixture(autouse=True)
def _grant_every_permission():
    """require_permission's session branch resolves the caller's profile permissions via a real
    DB query (PermissionService) — mocked globally to "every permission granted," the same
    implicit assumption every route test's session fixture made before profiles existed (seeding
    `sess["active_role"] = "admin"`, back when that alone bypassed every check). A test that
    specifically wants to verify a permission *denial* overrides this in its own `with patch(...)`
    block, same pattern already used for `_require_admin`-style overrides."""
    with patch(
        "api.presentation.routes.app_auth.PermissionService.resolve_permissions",
        return_value=frozenset(OBJECT_PERMISSIONS),
    ):
        yield


@pytest.fixture(autouse=True)
def _skip_session_inactivity_check():
    """resolve_cookie_session() (api/presentation/web/session_guard.py — shared by
    require_org_session and require_permission's cookie branch) calls two more real-DB
    IdentityRepository methods on every authenticated cookie request, to enforce the org's
    configured session-inactivity timeout. Patched globally at the canonical class location (both
    session_guard.py and any test-local patch reach the same underlying attribute regardless of
    which module's name they patch through) — get_last_active_at returning None is exactly the
    correct "never checked before, allow" behavior every existing route test's faked session
    (no real Identity row behind it) should get, so no route test needs a real DB just to pass
    through auth. A test that specifically wants to verify timeout behavior overrides these in its
    own `with patch(...)` block."""
    with (
        patch("api.infrastructure.repositories.identity_repository.IdentityRepository.get_last_active_at", return_value=None),
        patch("api.infrastructure.repositories.identity_repository.IdentityRepository.touch_last_active"),
    ):
        yield
