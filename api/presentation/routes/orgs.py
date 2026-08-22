from uuid import UUID

from flask import Blueprint, g, jsonify, request

from api.application.auth_service import AuthService
from api.application.org_membership_service import OrgMembershipService
from api.application.permission_service import PermissionService
from api.application.shelf_service import ShelfService
from api.container import get_session
from api.infrastructure.auth.password_identity_verifier import PasswordIdentityVerifier
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.infrastructure.repositories.profile_repository import ProfileRepository
from api.infrastructure.repositories.shelf_repository import ShelfRepository
from api.presentation.routes.app_auth import require_permission
from api.presentation.routes.auth_ui import require_org_session
from api.presentation.schemas import (
    MeUpdateRequest,
    MeUsernameUpdateRequest,
    OrgInviteRequest,
    OrgMemberProfileUpdateRequest,
    OrgMemberResponse,
    OrgNameUpdateRequest,
    OrgResponse,
    ShelfSummaryResponse,
)

orgs_bp = Blueprint("orgs", __name__, url_prefix="/orgs")


def _service() -> OrgMembershipService:
    session_ = get_session()
    return OrgMembershipService(
        OrganizationRepository(session_), OrgMemberRepository(session_), IdentityRepository(session_), ProfileRepository(session_)
    )


def _auth_service() -> AuthService:
    session_ = get_session()
    identities = IdentityRepository(session_)
    return AuthService(identities, PasswordIdentityVerifier(identities), OrgMemberRepository(session_))


def _permissions_for(identity_id: UUID, org_id: UUID) -> list[str]:
    session_ = get_session()
    return sorted(PermissionService(OrgMemberRepository(session_), ProfileRepository(session_)).resolve_permissions(identity_id, org_id))


def _member_response(member, identity, profile) -> dict:
    return OrgMemberResponse(
        identity_id=identity.id,
        username=identity.username,
        email=identity.email,
        name=identity.name,
        profile_id=profile.id,
        profile_name=profile.name,
        profile_is_admin=profile.is_admin,
    ).model_dump(mode="json")


def _me_response(identity) -> dict:
    session_ = get_session()
    member = OrgMemberRepository(session_).get(g.org_id, identity.id)
    profile = ProfileRepository(session_).get(member.profile_id)
    return _member_response(member, identity, profile)


@orgs_bp.get("")
@require_org_session
def list_orgs():
    # Always 0 or 1 entries — an identity belongs to exactly one org for its whole life (see
    # domain/entities.py's Identity docstring) — kept list-shaped since several webui pages already
    # do `orgs.data?.find(...)` against this response rather than expecting a single object.
    organizations = OrganizationRepository(get_session())
    memberships = OrgMemberRepository(get_session()).list_for_identity(g.user_id)
    return jsonify(
        [
            OrgResponse.from_entity(
                organizations.get(member.org_id), _permissions_for(g.user_id, member.org_id)
            ).model_dump(mode="json")
            for member in memberships
        ]
    )


@orgs_bp.get("/me")
@require_org_session
def get_me():
    """The caller's own account/profile info in the active org — unlike list_members
    (org_members:read), this needs no specific permission, since it only ever returns the caller's
    own data and every member is always allowed to see that."""
    identity = IdentityRepository(get_session()).get_by_id(g.user_id)
    return jsonify(_me_response(identity))


@orgs_bp.patch("/me")
@require_org_session
def update_me():
    """Full name and email — no current-password confirmation, unlike update_me_username below:
    neither is a login credential, so there's nothing for a hijacked session to escalate into."""
    dto = MeUpdateRequest.model_validate(request.get_json(silent=True) or {})
    identity = _auth_service().update_profile(g.user_id, dto.name, dto.email)
    return jsonify(_me_response(identity))


@orgs_bp.patch("/me/username")
@require_org_session
def update_me_username():
    """Username is the login credential, so this requires the caller's current password —
    unlike update_me above — to confirm it's really them and not just whoever holds the session
    cookie right now (see AuthService.change_username)."""
    dto = MeUsernameUpdateRequest.model_validate(request.get_json(silent=True) or {})
    identity = _auth_service().change_username(g.user_id, dto.current_password, dto.username)
    return jsonify(_me_response(identity))


@orgs_bp.patch("/<uuid:org_id>")
@require_permission("org:write")
def update_organization(org_id: UUID):
    """Admin-only (org:write is only on the Admin profile by default) and re-verifies the acting
    admin's own current password — the org name doubles as every member's URL slug, so this is a
    credential-weight change, not a plain profile edit (see OrgMembershipService.
    change_organization_name)."""
    dto = OrgNameUpdateRequest.model_validate(request.get_json(silent=True) or {})
    organization = _service().change_organization_name(org_id, g.user_id, dto.current_password, dto.name)
    return jsonify(OrgResponse.from_entity(organization, _permissions_for(g.user_id, org_id)).model_dump(mode="json"))


@orgs_bp.get("/<uuid:org_id>/members")
@require_permission("org_members:read")
def list_members(org_id: UUID):
    profiles = ProfileRepository(get_session())
    members = _service().list_members(org_id)
    return jsonify(
        [
            _member_response(member, identity, profiles.get(member.profile_id))
            for member, identity in members
            if identity is not None
        ]
    )


@orgs_bp.post("/<uuid:org_id>/invites")
@require_permission("org_members:write")
def invite_member(org_id: UUID):
    dto = OrgInviteRequest.model_validate(request.get_json(silent=True) or {})
    member = _service().invite_member(org_id, dto.email, dto.profile_id, g.user_id)
    session_ = get_session()
    identity = IdentityRepository(session_).get_by_id(member.identity_id)
    profile = ProfileRepository(session_).get(member.profile_id)
    response = jsonify(_member_response(member, identity, profile))
    response.status_code = 201
    return response


@orgs_bp.patch("/<uuid:org_id>/members/<uuid:identity_id>")
@require_permission("org_members:write")
def update_member_profile(org_id: UUID, identity_id: UUID):
    dto = OrgMemberProfileUpdateRequest.model_validate(request.get_json(silent=True) or {})
    member = _service().update_member_profile(org_id, identity_id, dto.profile_id, acting_identity_id=g.user_id)
    session_ = get_session()
    identity = IdentityRepository(session_).get_by_id(identity_id)
    profile = ProfileRepository(session_).get(member.profile_id)
    return jsonify(_member_response(member, identity, profile))


@orgs_bp.delete("/<uuid:org_id>/members/<uuid:identity_id>")
@require_permission("org_members:write")
def remove_member(org_id: UUID, identity_id: UUID):
    _service().remove_member(org_id, identity_id)
    return "", 204


@orgs_bp.get("/<uuid:org_id>/members/<uuid:identity_id>/shelf-access")
@require_permission("org_members:read")
def get_member_shelf_access(org_id: UUID, identity_id: UUID):
    shelves = ShelfService(ShelfRepository(get_session())).list_accessible_shelves(identity_id)
    return jsonify([ShelfSummaryResponse.from_entity(shelf).model_dump(mode="json") for shelf in shelves])
