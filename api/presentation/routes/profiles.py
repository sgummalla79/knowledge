from uuid import UUID

from flask import Blueprint, g, jsonify, request

from api.application.profile_service import ProfileService
from api.container import get_session
from api.infrastructure.repositories.profile_repository import ProfileRepository
from api.presentation.permission_catalog import PERMISSION_GROUPS
from api.presentation.routes.app_auth import require_permission
from api.presentation.schemas import PermissionCatalogResponse, ProfileCreateRequest, ProfileResponse, ProfileUpdateRequest

profiles_bp = Blueprint("profiles", __name__, url_prefix="/profiles")


def _service() -> ProfileService:
    return ProfileService(ProfileRepository(get_session()))


@profiles_bp.get("/permissions")
@require_permission("profiles:read")
def list_permission_catalog():
    # The full labeled permission vocabulary ProfileFormPage renders as its checkbox list — see
    # permission_catalog.py's docstring for why this replaced a hand-duplicated frontend constant.
    return jsonify(PermissionCatalogResponse(groups=PERMISSION_GROUPS).model_dump(mode="json"))


@profiles_bp.post("")
@require_permission("profiles:write")
def create_profile():
    dto = ProfileCreateRequest.model_validate(request.get_json(silent=True) or {})
    profile, permissions = _service().create(g.org_id, dto.name, dto.description, dto.permissions, g.user_id)
    response = jsonify(ProfileResponse.from_entity(profile, permissions).model_dump(mode="json"))
    response.status_code = 201
    response.headers["Location"] = f"/profiles/{profile.id}"
    return response


@profiles_bp.get("")
@require_permission("profiles:read")
def list_profiles():
    profiles = _service().list_for_org(g.org_id)
    return jsonify([ProfileResponse.from_entity(profile, permissions).model_dump(mode="json") for profile, permissions in profiles])


@profiles_bp.get("/<uuid:profile_id>")
@require_permission("profiles:read")
def get_profile(profile_id: UUID):
    profile, permissions = _service().get(g.org_id, profile_id)
    return jsonify(ProfileResponse.from_entity(profile, permissions).model_dump(mode="json"))


@profiles_bp.patch("/<uuid:profile_id>")
@require_permission("profiles:write")
def update_profile(profile_id: UUID):
    dto = ProfileUpdateRequest.model_validate(request.get_json(silent=True) or {})
    profile, permissions = _service().update(g.org_id, profile_id, dto.name, dto.description, dto.permissions)
    return jsonify(ProfileResponse.from_entity(profile, permissions).model_dump(mode="json"))


@profiles_bp.delete("/<uuid:profile_id>")
@require_permission("profiles:write")
def delete_profile(profile_id: UUID):
    _service().delete(g.org_id, profile_id)
    return "", 204
