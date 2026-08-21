from uuid import UUID

from flask import Blueprint, g, jsonify, request

from api.application.personal_access_token_service import PersonalAccessTokenService
from api.container import get_session
from api.infrastructure.repositories.personal_access_token_repository import PersonalAccessTokenRepository
from api.presentation.routes.auth_ui import require_org_session
from api.presentation.schemas import (
    PersonalAccessTokenCreateRequest,
    PersonalAccessTokenResponse,
    PersonalAccessTokenSecretResponse,
)

# Deliberately gated by require_org_session, not require_permission — self-service, no
# applications:write-style permission needed. Every method here only ever touches the caller's own
# tokens (identity_id) in their own currently-active org (org_id), the same self-scoping
# require_org_session already guarantees for g.user_id/g.org_id.
personal_access_tokens_bp = Blueprint("personal_access_tokens", __name__, url_prefix="/personal-access-tokens")


def _service() -> PersonalAccessTokenService:
    return PersonalAccessTokenService(PersonalAccessTokenRepository(get_session()))


@personal_access_tokens_bp.post("")
@require_org_session
def create_personal_access_token():
    dto = PersonalAccessTokenCreateRequest.model_validate(request.get_json(silent=True) or {})
    token, raw_token = _service().create(g.org_id, g.user_id, dto.name, mcp_access=dto.mcp_access)
    response = jsonify(PersonalAccessTokenSecretResponse.from_token_entity(token, raw_token).model_dump(mode="json"))
    response.status_code = 201
    return response


@personal_access_tokens_bp.get("")
@require_org_session
def list_personal_access_tokens():
    tokens = _service().list_for_identity(g.org_id, g.user_id)
    return jsonify([PersonalAccessTokenResponse.from_entity(token).model_dump(mode="json") for token in tokens])


@personal_access_tokens_bp.delete("/<uuid:token_id>")
@require_org_session
def delete_personal_access_token(token_id: UUID):
    _service().delete(g.user_id, token_id)
    return "", 204
