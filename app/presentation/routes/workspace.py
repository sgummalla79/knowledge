from flask import Blueprint, jsonify, redirect, request, url_for

from app.application.token_service import TokenService
from app.config import config
from app.constants import DEFAULT_DASHBOARD_APPLICATION_ID, DEFAULT_DASHBOARD_APPLICATION_SCOPES
from app.container import get_session
from app.domain.errors import AuthenticationError
from app.infrastructure.auth.secrets import derive_default_dashboard_client_secret
from app.infrastructure.repositories.application_repository import ApplicationRepository
from app.infrastructure.repositories.authorization_code_repository import AuthorizationCodeRepository
from app.infrastructure.repositories.refresh_token_repository import RefreshTokenRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.presentation.routes.auth_ui import login_required
from app.presentation.web.csrf import validate_csrf
from app.presentation.web.spa import serve_spa_shell

workspace_bp = Blueprint("workspace", __name__)


def _token_service() -> TokenService:
    session = get_session()
    return TokenService(
        ApplicationRepository(session), RefreshTokenRepository(session), AuthorizationCodeRepository(session)
    )


@workspace_bp.post("/dashboard/token")
@login_required
def dashboard_token():
    # The SPA has no OAuth2 credential of its own — it authenticates this call with the admin's
    # session cookie instead, so CSRF is checked the same way as every other state-changing
    # dashboard route, just via a header (this is a fetch() call, not a form submission).
    if not validate_csrf(request.headers.get("X-CSRF-Token")):
        raise AuthenticationError("Session expired — please reload the page.")

    secret = derive_default_dashboard_client_secret(config.secret_key)
    result = _token_service().client_credentials_grant(
        DEFAULT_DASHBOARD_APPLICATION_ID, secret, DEFAULT_DASHBOARD_APPLICATION_SCOPES
    )
    return jsonify({"access_token": result["access_token"], "expires_in": result["expires_in"]})


@workspace_bp.get("/workspace")
@workspace_bp.get("/workspace/<path:subpath>")
@login_required
def workspace(subpath: str | None = None):
    user = UserRepository(get_session()).get()
    if user is not None and user.must_change_password:
        return redirect(url_for("auth_ui.change_password"))
    return serve_spa_shell()
