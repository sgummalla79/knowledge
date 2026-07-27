from uuid import UUID

from flask import Blueprint, jsonify, request

from app.application.token_service import TokenService
from app.container import get_session
from app.domain import error_codes
from app.domain.errors import ValidationError
from app.infrastructure.repositories.application_repository import ApplicationRepository
from app.infrastructure.repositories.refresh_token_repository import RefreshTokenRepository

oauth_bp = Blueprint("oauth", __name__)


def _service() -> TokenService:
    session = get_session()
    return TokenService(ApplicationRepository(session), RefreshTokenRepository(session))


@oauth_bp.post("/oauth/token")
def issue_token():
    # Standard OAuth2 convention: form-encoded body, dispatched on grant_type. Errors flow through
    # this app's existing DomainError -> structured-envelope machinery, using OAuth2's own error
    # vocabulary (invalid_client/invalid_grant/invalid_scope) as the `code` value.
    grant_type = request.form.get("grant_type", "")

    if grant_type == "client_credentials":
        client_id_raw = request.form.get("client_id", "")
        client_secret = request.form.get("client_secret", "")
        scope = request.form.get("scope", "").split()
        try:
            client_id = UUID(client_id_raw)
        except ValueError:
            raise ValidationError(error_codes.INVALID_REQUEST, "client_id must be a valid UUID.", field="client_id")
        result = _service().client_credentials_grant(client_id, client_secret, scope)
        return jsonify(result)

    if grant_type == "refresh_token":
        raw_refresh_token = request.form.get("refresh_token", "")
        result = _service().refresh_token_grant(raw_refresh_token)
        return jsonify(result)

    raise ValidationError(
        error_codes.UNSUPPORTED_GRANT_TYPE, f"Unsupported grant_type '{grant_type}'.", field="grant_type"
    )
