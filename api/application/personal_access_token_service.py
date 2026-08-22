import secrets
from uuid import UUID

from api.constants import PERSONAL_ACCESS_TOKEN_BYTES
from api.domain import error_codes
from api.domain.entities import PersonalAccessToken
from api.domain.errors import NotFoundError
from api.domain.ports import PersonalAccessTokenRepositoryPort
from api.infrastructure.auth.token_hashing import hash_token


class PersonalAccessTokenService:
    """Self-service personal API keys: created by an identity for themselves, in whichever org is
    active at creation time. No admin permission gates any method here (see require_org_session on
    the route side, not require_permission) — every method is scoped to the caller's own
    identity_id, checked explicitly rather than relying on a permission the caller might happen to
    hold."""

    def __init__(self, tokens: PersonalAccessTokenRepositoryPort):
        self._tokens = tokens

    def create(
        self, org_id: UUID, identity_id: UUID, name: str, mcp_access: bool = False
    ) -> tuple[PersonalAccessToken, str]:
        raw_token = secrets.token_urlsafe(PERSONAL_ACCESS_TOKEN_BYTES)
        token = self._tokens.create(identity_id, org_id, name, hash_token(raw_token), raw_token[:12], mcp_access)
        return token, raw_token

    def list_for_identity(self, org_id: UUID, identity_id: UUID) -> list[PersonalAccessToken]:
        return self._tokens.list_for_identity_in_org(identity_id, org_id)

    def delete(self, identity_id: UUID, token_id: UUID) -> None:
        # "Not found" for both a missing token and one that belongs to someone else — same
        # don't-leak-existence convention ApplicationService._get_or_404 already uses for
        # cross-tenant lookups, applied here to cross-identity ones instead.
        token = self._tokens.get_by_id(token_id)
        if token is None or token.identity_id != identity_id:
            raise NotFoundError(error_codes.PERSONAL_ACCESS_TOKEN_NOT_FOUND, "API key not found.")
        self._tokens.delete(token_id)
