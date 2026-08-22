import asyncio
from unittest.mock import patch
from uuid import uuid4

from api.domain.entities import ResolvedCaller
from api.mcp_server.auth import KnowledgeTokenVerifier


def test_verify_token_maps_resolved_caller_to_access_token():
    org_id, identity_id, application_id = uuid4(), uuid4(), uuid4()
    caller = ResolvedCaller(
        org_id=org_id,
        identity_id=identity_id,
        application_id=application_id,
        scopes=frozenset({"documents:read", "categories:read"}),
        auth_method="oauth_client_credentials",
        mcp_access=True,
        api_access=True,
    )
    with patch("api.mcp_server.auth.AppAuthService.authenticate_bearer_token", return_value=caller):
        access_token = asyncio.run(KnowledgeTokenVerifier().verify_token("the-raw-token"))

    assert access_token is not None
    assert access_token.client_id == str(application_id)
    assert sorted(access_token.scopes) == ["categories:read", "documents:read"]
    assert access_token.claims == {
        "org_id": str(org_id),
        "identity_id": str(identity_id),
        "auth_method": "oauth_client_credentials",
        "mcp_access": True,
    }


def test_verify_token_returns_none_for_invalid_token():
    with patch("api.mcp_server.auth.AppAuthService.authenticate_bearer_token", return_value=None):
        access_token = asyncio.run(KnowledgeTokenVerifier().verify_token("bogus"))

    assert access_token is None
