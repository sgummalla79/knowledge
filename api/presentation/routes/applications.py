from uuid import UUID

from flask import Blueprint, g, jsonify, request

from api.application.application_service import ApplicationService
from api.container import get_session
from api.domain import error_codes
from api.domain.errors import ValidationError
from api.infrastructure.repositories.application_api_key_repository import ApplicationApiKeyRepository
from api.infrastructure.repositories.application_oauth_client_repository import ApplicationOAuthClientRepository
from api.infrastructure.repositories.application_repository import ApplicationRepository
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.profile_repository import ProfileRepository
from api.presentation.routes.app_auth import require_permission
from api.presentation.schemas import (
    ApplicationCreateRequest,
    ApplicationOAuthClientSecretResponse,
    ApplicationResponse,
    ApplicationSecretResponse,
    ApplicationUpdateRequest,
)

# Gated by the applications:read/applications:write permissions like any other resource — fully
# delegable through a custom profile (an org can build e.g. an "IT Admin" persona that manages
# connected applications but nothing else), not hardcoded Admin-only.
applications_bp = Blueprint("applications", __name__, url_prefix="/applications")


def _service() -> ApplicationService:
    session_ = get_session()
    return ApplicationService(
        ApplicationRepository(session_),
        ApplicationApiKeyRepository(session_),
        IdentityRepository(session_),
        OrgMemberRepository(session_),
        ProfileRepository(session_),
        ApplicationOAuthClientRepository(session_),
    )


@applications_bp.post("")
@require_permission("applications:write")
def create_application():
    dto = ApplicationCreateRequest.model_validate(request.get_json(silent=True) or {})
    if dto.auth_method == "api_key":
        application, api_key = _service().create(
            g.org_id,
            dto.name,
            dto.description,
            "api_key",
            dto.scopes,
            g.user_id,
            mcp_access=dto.mcp_access,
            api_access=dto.api_access,
        )
        response = jsonify(
            ApplicationSecretResponse.from_application_entity(application, dto.scopes, api_key).model_dump(mode="json")
        )
    elif dto.auth_method == "oauth_client_credentials":
        if dto.execute_as_identity_id is None:
            raise ValidationError(
                error_codes.VALIDATION_ERROR,
                "execute_as_identity_id is required for oauth_client_credentials.",
                field="execute_as_identity_id",
            )
        application, client_secret = _service().create_client_credentials(
            g.org_id,
            dto.name,
            dto.description,
            dto.execute_as_identity_id,
            g.user_id,
            mcp_access=dto.mcp_access,
            api_access=dto.api_access,
        )
        response = jsonify(
            ApplicationOAuthClientSecretResponse.from_application_entity(application, client_secret).model_dump(mode="json")
        )
    else:
        # oauth_authorization_code — a public, PKCE-only client, nothing secret to reveal.
        application = _service().create_authorization_code_client(
            g.org_id,
            dto.name,
            dto.description,
            dto.redirect_uris,
            g.user_id,
            mcp_access=dto.mcp_access,
            api_access=dto.api_access,
        )
        response = jsonify(ApplicationResponse.from_entity(application, []).model_dump(mode="json"))
    response.status_code = 201
    response.headers["Location"] = f"/applications/{application.id}"
    return response


@applications_bp.get("")
@require_permission("applications:read")
def list_applications():
    applications = _service().list_for_org(g.org_id)
    return jsonify(
        [ApplicationResponse.from_entity(application, scopes).model_dump(mode="json") for application, scopes in applications]
    )


@applications_bp.get("/<uuid:application_id>")
@require_permission("applications:read")
def get_application(application_id: UUID):
    application, scopes = _service().get(g.org_id, application_id)
    return jsonify(ApplicationResponse.from_entity(application, scopes).model_dump(mode="json"))


@applications_bp.patch("/<uuid:application_id>")
@require_permission("applications:write")
def update_application(application_id: UUID):
    dto = ApplicationUpdateRequest.model_validate(request.get_json(silent=True) or {})
    application, scopes = _service().update(g.org_id, application_id, dto.name, dto.description, dto.scopes)
    return jsonify(ApplicationResponse.from_entity(application, scopes).model_dump(mode="json"))


@applications_bp.post("/<uuid:application_id>/rotate-key")
@require_permission("applications:write")
def rotate_application_key(application_id: UUID):
    service = _service()
    existing, _ = service.get(g.org_id, application_id)
    if existing.auth_method == "api_key":
        application, api_key = service.rotate_api_key(g.org_id, application_id)
        scopes = ApplicationRepository(get_session()).list_scopes(application_id)
        return jsonify(ApplicationSecretResponse.from_application_entity(application, scopes, api_key).model_dump(mode="json"))
    if existing.auth_method == "oauth_client_credentials":
        application, client_secret = service.rotate_client_secret(g.org_id, application_id)
        return jsonify(ApplicationOAuthClientSecretResponse.from_application_entity(application, client_secret).model_dump(mode="json"))
    # oauth_authorization_code — PKCE has no long-lived credential to rotate.
    raise ValidationError(error_codes.VALIDATION_ERROR, "This application has no rotatable secret.")


@applications_bp.post("/<uuid:application_id>/revoke")
@require_permission("applications:write")
def revoke_application(application_id: UUID):
    application, scopes = _service().revoke(g.org_id, application_id, g.user_id)
    return jsonify(ApplicationResponse.from_entity(application, scopes).model_dump(mode="json"))


@applications_bp.delete("/<uuid:application_id>")
@require_permission("applications:write")
def delete_application(application_id: UUID):
    _service().delete(g.org_id, application_id)
    return "", 204
