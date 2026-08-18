from uuid import UUID

from flask import Blueprint, g, jsonify, request, session

from api.application.org_membership_service import OrgMembershipService
from api.container import get_session
from api.domain.errors import ForbiddenError
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.presentation.routes.auth_ui import require_org_session
from api.presentation.schemas import (
    OrgCreateRequest,
    OrgInviteRequest,
    OrgMemberResponse,
    OrgMemberRoleUpdateRequest,
    OrgResponse,
)

orgs_bp = Blueprint("orgs", __name__, url_prefix="/orgs")


def _service() -> OrgMembershipService:
    session_ = get_session()
    return OrgMembershipService(OrganizationRepository(session_), OrgMemberRepository(session_), IdentityRepository(session_))


def _require_admin(org_id: UUID) -> None:
    # Checked against the specific org_id being acted on, not g.role — g.role only reflects the
    # session's currently *active* org, which may differ from the org this route is managing.
    member = OrgMemberRepository(get_session()).get(org_id, g.user_id)
    if member is None or member.role != "admin":
        raise ForbiddenError("Only an org admin can manage members.")


@orgs_bp.get("")
@require_org_session
def list_orgs():
    organizations = OrganizationRepository(get_session())
    memberships = OrgMemberRepository(get_session()).list_for_identity(g.user_id)
    return jsonify(
        [
            OrgResponse.from_entity(organizations.get(member.org_id), member.role).model_dump(mode="json")
            for member in memberships
        ]
    )


@orgs_bp.post("")
@require_org_session
def create_org():
    dto = OrgCreateRequest.model_validate(request.get_json(silent=True) or {})
    organization = _service().create_org_with_owner(dto.name, g.user_id)
    response = jsonify(OrgResponse.from_entity(organization, "admin").model_dump(mode="json"))
    response.status_code = 201
    return response


@orgs_bp.post("/<uuid:org_id>/switch")
@require_org_session
def switch_org(org_id: UUID):
    role = _service().switch_active_org(g.user_id, org_id)
    session["active_org_id"] = str(org_id)
    session["active_role"] = role
    return jsonify({"org_id": str(org_id), "role": role})


@orgs_bp.get("/<uuid:org_id>/members")
@require_org_session
def list_members(org_id: UUID):
    members = _service().list_members(org_id)
    return jsonify(
        [
            OrgMemberResponse(
                identity_id=identity.id, email=identity.email, name=identity.name, role=member.role
            ).model_dump(mode="json")
            for member, identity in members
            if identity is not None
        ]
    )


@orgs_bp.post("/<uuid:org_id>/invites")
@require_org_session
def invite_member(org_id: UUID):
    _require_admin(org_id)
    dto = OrgInviteRequest.model_validate(request.get_json(silent=True) or {})
    member = _service().invite_member(org_id, dto.email, dto.role, g.user_id)
    identity = IdentityRepository(get_session()).get_by_id(member.identity_id)
    response = jsonify(
        OrgMemberResponse(identity_id=identity.id, email=identity.email, name=identity.name, role=member.role).model_dump(
            mode="json"
        )
    )
    response.status_code = 201
    return response


@orgs_bp.patch("/<uuid:org_id>/members/<uuid:identity_id>")
@require_org_session
def update_member_role(org_id: UUID, identity_id: UUID):
    _require_admin(org_id)
    dto = OrgMemberRoleUpdateRequest.model_validate(request.get_json(silent=True) or {})
    member = _service().update_role(org_id, identity_id, dto.role)
    identity = IdentityRepository(get_session()).get_by_id(identity_id)
    return jsonify(
        OrgMemberResponse(identity_id=identity.id, email=identity.email, name=identity.name, role=member.role).model_dump(
            mode="json"
        )
    )


@orgs_bp.delete("/<uuid:org_id>/members/<uuid:identity_id>")
@require_org_session
def remove_member(org_id: UUID, identity_id: UUID):
    _require_admin(org_id)
    _service().remove_member(org_id, identity_id)
    return "", 204
