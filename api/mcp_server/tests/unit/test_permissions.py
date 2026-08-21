from unittest.mock import patch
from uuid import uuid4

import pytest
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from mcp.server.fastmcp.exceptions import ToolError

from api.domain.entities import MCPSettings
from api.mcp_server.permissions import current_caller, require_tier_permission

# require_tier_permission's DB read (MCPSettingsRepository.get) is mocked here rather than using a
# real session — the session parameter is only ever passed through opaquely to that repository, so
# a sentinel object is enough; real DB-backed coverage of the three gates together lives in
# mcp_server/tests/integration/.

_SESSION = object()


def _set_access_token(org_id, identity_id, application_id, scopes, mcp_access=True):
    access_token = AccessToken(
        token="irrelevant",
        client_id=str(application_id),
        scopes=list(scopes),
        claims={
            "org_id": str(org_id),
            "identity_id": str(identity_id),
            "auth_method": "personal_access_token",
            "mcp_access": mcp_access,
        },
    )
    auth_context_var.set(AuthenticatedUser(access_token))


def _settings(**overrides):
    fields = dict(
        org_id=uuid4(),
        rag_read_enabled=False,
        object_read_enabled=False,
        object_write_enabled=False,
        last_modified_by=None,
        last_modified_at=None,
    )
    fields.update(overrides)
    return MCPSettings(**fields)


@pytest.fixture(autouse=True)
def _clear_auth_context():
    yield
    auth_context_var.set(None)


def test_current_caller_raises_when_unauthenticated():
    with pytest.raises(ToolError):
        current_caller()


def test_current_caller_reads_claims_scopes_and_mcp_access():
    org_id, identity_id, application_id = uuid4(), uuid4(), uuid4()
    _set_access_token(org_id, identity_id, application_id, ["documents:read"], mcp_access=True)

    caller = current_caller()

    assert caller["org_id"] == org_id
    assert caller["identity_id"] == identity_id
    assert caller["application_id"] == application_id
    assert caller["scopes"] == frozenset({"documents:read"})
    assert caller["mcp_access"] is True


def test_require_tier_permission_denied_when_mcp_access_off():
    org_id, identity_id, application_id = uuid4(), uuid4(), uuid4()
    _set_access_token(org_id, identity_id, application_id, ["documents:read"], mcp_access=False)

    with pytest.raises(ToolError, match="MCP access"):
        require_tier_permission(_SESSION, "rag", "documents:read")


def test_require_tier_permission_denied_when_tier_disabled_for_org():
    org_id, identity_id, application_id = uuid4(), uuid4(), uuid4()
    _set_access_token(org_id, identity_id, application_id, ["documents:read"], mcp_access=True)

    with patch(
        "api.mcp_server.permissions.MCPSettingsRepository.get",
        return_value=_settings(org_id=org_id, rag_read_enabled=False),
    ):
        with pytest.raises(ToolError, match="not enabled"):
            require_tier_permission(_SESSION, "rag", "documents:read")


def test_require_tier_permission_denied_when_no_settings_row_exists():
    # Absent row means every tier is off — same "no row yet" default MCPSettingsService.get uses.
    org_id, identity_id, application_id = uuid4(), uuid4(), uuid4()
    _set_access_token(org_id, identity_id, application_id, ["documents:read"], mcp_access=True)

    with patch("api.mcp_server.permissions.MCPSettingsRepository.get", return_value=None):
        with pytest.raises(ToolError, match="not enabled"):
            require_tier_permission(_SESSION, "rag", "documents:read")


def test_require_tier_permission_denied_when_permission_not_granted():
    org_id, identity_id, application_id = uuid4(), uuid4(), uuid4()
    _set_access_token(org_id, identity_id, application_id, ["documents:read"], mcp_access=True)

    with patch(
        "api.mcp_server.permissions.MCPSettingsRepository.get",
        return_value=_settings(org_id=org_id, rag_read_enabled=True),
    ):
        with pytest.raises(ToolError, match="not authorized"):
            require_tier_permission(_SESSION, "rag", "documents:write")


def test_require_tier_permission_allowed_when_all_three_gates_pass():
    org_id, identity_id, application_id = uuid4(), uuid4(), uuid4()
    _set_access_token(org_id, identity_id, application_id, ["documents:read"], mcp_access=True)

    with patch(
        "api.mcp_server.permissions.MCPSettingsRepository.get",
        return_value=_settings(org_id=org_id, rag_read_enabled=True),
    ):
        caller = require_tier_permission(_SESSION, "rag", "documents:read")

    assert caller["org_id"] == org_id


def test_require_tier_permission_allows_no_permission_check_when_none_given():
    org_id, identity_id, application_id = uuid4(), uuid4(), uuid4()
    _set_access_token(org_id, identity_id, application_id, [], mcp_access=True)

    with patch(
        "api.mcp_server.permissions.MCPSettingsRepository.get",
        return_value=_settings(org_id=org_id, object_write_enabled=True),
    ):
        caller = require_tier_permission(_SESSION, "write", None)

    assert caller["org_id"] == org_id


def test_require_tier_permission_checks_the_right_tier_column():
    # object_read_enabled being on doesn't grant the "write" tier.
    org_id, identity_id, application_id = uuid4(), uuid4(), uuid4()
    _set_access_token(org_id, identity_id, application_id, ["documents:write"], mcp_access=True)

    with patch(
        "api.mcp_server.permissions.MCPSettingsRepository.get",
        return_value=_settings(org_id=org_id, object_read_enabled=True, object_write_enabled=False),
    ):
        with pytest.raises(ToolError, match="not enabled"):
            require_tier_permission(_SESSION, "write", "documents:write")
