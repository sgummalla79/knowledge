from uuid import UUID

from flask import Blueprint, g, jsonify, request, session

from api.application.org_membership_service import OrgMembershipService
from api.application.permission_service import PermissionService
from api.application.shelf_service import ShelfService
from api.container import get_session
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.infrastructure.repositories.profile_repository import ProfileRepository
from api.infrastructure.repositories.shelf_repository import ShelfRepository
from api.presentation.routes.app_auth import require_permission
from api.presentation.routes.auth_ui import require_org_session
from api.presentation.schemas import (
    OrgCreateRequest,
    OrgInviteRequest,
    OrgMemberProfileUpdateRequest,
    OrgMemberResponse,
    OrgResponse,
    OrgUpdateRequest,
    ShelfSummaryResponse,
)

orgs_bp = Blueprint("orgs", __name__, url_prefix="/orgs")


def _service() -> OrgMembershipService:
    session_ = get_session()
    return OrgMembershipService(
        OrganizationRepository(session_), OrgMemberRepository(session_), IdentityRepository(session_), ProfileRepository(session_)
    )


def _permissions_for(identity_id: UUID, org_id: UUID) -> list[str]:
    session_ = get_session()
    return sorted(PermissionService(OrgMemberRepository(session_), ProfileRepository(session_)).resolve_permissions(identity_id, org_id))


def _member_response(member, identity, profile) -> dict:
    return OrgMemberResponse(
        identity_id=identity.id,
        email=identity.email,
        name=identity.name,
        profile_id=profile.id,
        profile_name=profile.name,
        profile_is_admin=profile.is_admin,
    ).model_dump(mode="json")


@orgs_bp.get("")
@require_org_session
def list_orgs():
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


@orgs_bp.post("")
@require_org_session
def create_org():
    dto = OrgCreateRequest.model_validate(request.get_json(silent=True) or {})
    organization = _service().create_org_with_owner(dto.name, g.user_id)
    response = jsonify(
        OrgResponse.from_entity(organization, _permissions_for(g.user_id, organization.id)).model_dump(mode="json")
    )
    response.status_code = 201
    return response


@orgs_bp.patch("/<uuid:org_id>")
@require_permission("org:write")
def update_org(org_id: UUID):
    dto = OrgUpdateRequest.model_validate(request.get_json(silent=True) or {})
    organization = _service().update_organization(org_id, dto.name, dto.description)
    return jsonify(OrgResponse.from_entity(organization, _permissions_for(g.user_id, org_id)).model_dump(mode="json"))


@orgs_bp.post("/<uuid:org_id>/switch")
@require_org_session
def switch_org(org_id: UUID):
    _service().switch_active_org(g.user_id, org_id)
    session["active_org_id"] = str(org_id)
    return jsonify({"org_id": str(org_id)})


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
    member = _service().update_member_profile(org_id, identity_id, dto.profile_id)
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
