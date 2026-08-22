from uuid import UUID

from api.domain.ports import OrgMemberRepositoryPort, ProfileRepositoryPort


class PermissionService:
    """The single source of truth for "can this identity read/write X in this org" — resolved
    fresh on every request (never cached in a session or a token claim) so a profile edit takes
    effect immediately, not after the next login/token refresh. Used identically for a human
    session and, in a later phase, client_credentials/authorization_code callers. The api_key auth
    method deliberately does not go through this — it keeps checking its own application_scopes,
    see ApplicationService/AppAuthService."""

    def __init__(self, org_members: OrgMemberRepositoryPort, profiles: ProfileRepositoryPort):
        self._org_members = org_members
        self._profiles = profiles

    def resolve_permissions(self, identity_id: UUID, org_id: UUID) -> frozenset[str]:
        member = self._org_members.get(org_id, identity_id)
        if member is None:
            return frozenset()
        return frozenset(self._profiles.list_permissions(member.profile_id))
