from functools import wraps
from uuid import UUID

from flask import Blueprint, jsonify, redirect, request, session, url_for

from app.application.application_service import ApplicationService
from app.application.auth_service import AuthService
from app.constants import DEFAULT_DASHBOARD_APPLICATION_ID, DEFAULT_MCP_APPLICATION_ID, SUPPORTED_SCOPES
from app.container import get_session
from app.domain import error_codes
from app.domain.errors import AuthenticationError, NotFoundError, ValidationError
from app.infrastructure.repositories.application_repository import ApplicationRepository
from app.infrastructure.repositories.refresh_token_repository import RefreshTokenRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.presentation.schemas import (
    ApplicationResponse,
    RegisterApplicationRequest,
    RegisterApplicationResponse,
    ScopeGroupResponse,
)
from app.presentation.web.csrf import validate_csrf
from app.presentation.web.spa import serve_spa_shell

# Built-in service-account Applications — internal plumbing, never shown in or manageable from the
# Applications dashboard page (see _applications_with_status/revoke_token/delete_application below).
_HIDDEN_APPLICATION_IDS = {DEFAULT_MCP_APPLICATION_ID, DEFAULT_DASHBOARD_APPLICATION_ID}

auth_ui_bp = Blueprint("auth_ui", __name__)


def _grouped_scopes(scopes: list[str]) -> list[tuple[str, list[str]]]:
    """Buckets scopes by the part before ":" (e.g. "libraries:read" -> "Libraries"), so the
    dashboard can display them by resource group without a hardcoded scope->group mapping that
    would need updating every time a scope is added."""
    groups: dict[str, list[str]] = {}
    for scope in scopes:
        label = scope.split(":", 1)[0].replace("_", " ").title()
        groups.setdefault(label, []).append(scope)
    return list(groups.items())


def _auth_service() -> AuthService:
    return AuthService(UserRepository(get_session()))


def _application_service() -> ApplicationService:
    session_ = get_session()
    return ApplicationService(ApplicationRepository(session_), RefreshTokenRepository(session_))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            # Only GET requests get a `next` — redirecting a blocked POST back to itself would
            # just re-GET that URL after login, not resubmit the form.
            next_url = request.full_path if request.method == "GET" else None
            return redirect(url_for("auth_ui.login", next=next_url))
        return view(*args, **kwargs)

    return wrapped


def _is_safe_redirect(url: str) -> bool:
    # Relative path only — rules out "//evil.com/..." (scheme-relative) and absolute URLs, both of
    # which would send a post-login redirect off this host.
    return url.startswith("/") and not url.startswith("//")


def _consume_post_login_redirect() -> str:
    # /workspace is the default landing page for a plain login (no explicit `next`) — the rest of
    # the app (Settings > Applications, Web Crawler, API Documentation, Data Model) is still fully
    # reachable via the workspace sidebar's account menu.
    next_url = session.pop("post_login_redirect", None)
    return next_url if next_url and _is_safe_redirect(next_url) else url_for("workspace.workspace")


@auth_ui_bp.get("/login")
def login():
    next_url = request.args.get("next")
    if next_url and _is_safe_redirect(next_url):
        session["post_login_redirect"] = next_url
    if session.get("user_id"):
        return redirect(_consume_post_login_redirect())
    return serve_spa_shell()


@auth_ui_bp.post("/login")
def login_submit():
    # Served to the React login page (webui/src/pages/LoginPage.tsx) via fetch — JSON in/out,
    # CSRF via header rather than a form field, same convention as POST /dashboard/token.
    if not validate_csrf(request.headers.get("X-CSRF-Token")):
        raise AuthenticationError("Session expired — please reload the page.")
    body = request.get_json(silent=True) or {}
    user = _auth_service().login(body.get("username", ""), body.get("password", ""))
    session["user_id"] = str(user.id)
    redirect_url = url_for("auth_ui.change_password") if user.must_change_password else _consume_post_login_redirect()
    return jsonify({"redirect": redirect_url})


@auth_ui_bp.get("/change-password")
@login_required
def change_password():
    return serve_spa_shell()


@auth_ui_bp.post("/change-password")
@login_required
def change_password_submit():
    if not validate_csrf(request.headers.get("X-CSRF-Token")):
        raise AuthenticationError("Session expired — please reload the page.")
    body = request.get_json(silent=True) or {}
    new_password = body.get("new_password", "")
    confirm_password = body.get("confirm_password", "")
    if len(new_password) < 8:
        raise ValidationError(
            error_codes.VALIDATION_ERROR, "Password must be at least 8 characters.", field="new_password"
        )
    if new_password != confirm_password:
        raise ValidationError(error_codes.VALIDATION_ERROR, "Passwords do not match.", field="confirm_password")
    _auth_service().change_password(UUID(session["user_id"]), new_password)
    return jsonify({"redirect": _consume_post_login_redirect()})


@auth_ui_bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth_ui.login"))


def _applications_with_status(
    service: ApplicationService, refresh_tokens: RefreshTokenRepository
) -> list[ApplicationResponse]:
    rows = []
    for application in service.list_applications():
        # Built-in service-account Applications (app/infrastructure/auth/bootstrap.py) are internal
        # plumbing, not something an admin registered or should manage here — deleting or
        # revoking either would silently break the bundled MCP server's or the /workspace SPA's
        # connection to this API.
        if application.id in _HIDDEN_APPLICATION_IDS:
            continue
        current = refresh_tokens.find_current_for_application(application.id)
        if current is None:
            status = "none"
            last_used_at = None
        elif current.revoked_at is not None:
            status = "revoked"
            last_used_at = current.last_used_at
        else:
            status = "active"
            last_used_at = current.last_used_at
        rows.append(
            ApplicationResponse(
                id=application.id,
                name=application.name,
                allowed_scopes=application.allowed_scopes,
                token_status=status,
                last_used_at=last_used_at,
            )
        )
    return rows


def _require_csrf_header() -> None:
    # Applications management is deliberately never part of the bearer-token OAuth2 API surface
    # (see CLAUDE.md item 4) — these routes authenticate the same way as /dashboard/token and
    # /change-password's JSON endpoints: the admin's session cookie plus a CSRF header, not a
    # scope-checked access token, since a delegable credential able to mint or delete other
    # credentials would be a privilege-escalation vector.
    if not validate_csrf(request.headers.get("X-CSRF-Token")):
        raise AuthenticationError("Session expired — please reload the page.")


def _reject_hidden_application(application_id: UUID) -> None:
    # Built-in service-account Applications aren't reachable through the Applications page (see
    # _applications_with_status) — this is defense in depth against a direct request to this URL.
    if application_id in _HIDDEN_APPLICATION_IDS:
        raise NotFoundError(error_codes.APPLICATION_NOT_FOUND, "Application not found.")


@auth_ui_bp.get("/dashboard/scopes")
@login_required
def list_scopes():
    groups = _grouped_scopes(SUPPORTED_SCOPES)
    return jsonify([ScopeGroupResponse(label=label, scopes=scopes).model_dump() for label, scopes in groups])


@auth_ui_bp.get("/dashboard/applications")
@login_required
def list_applications():
    service = _application_service()
    applications = _applications_with_status(service, RefreshTokenRepository(get_session()))
    return jsonify([application.model_dump(mode="json") for application in applications])


@auth_ui_bp.post("/dashboard/applications")
@login_required
def register_application():
    _require_csrf_header()
    dto = RegisterApplicationRequest.model_validate(request.get_json(silent=True) or {})
    raw_secret, application = _application_service().register(dto.name, dto.scopes)
    response = RegisterApplicationResponse(
        id=application.id,
        name=application.name,
        allowed_scopes=application.allowed_scopes,
        client_secret=raw_secret,
    )
    return jsonify(response.model_dump(mode="json"))


@auth_ui_bp.post("/dashboard/applications/<uuid:application_id>/revoke-token")
@login_required
def revoke_token(application_id: UUID):
    _require_csrf_header()
    _reject_hidden_application(application_id)
    _application_service().revoke_application_token(application_id)
    return "", 204


@auth_ui_bp.post("/dashboard/applications/<uuid:application_id>/delete")
@login_required
def delete_application(application_id: UUID):
    _require_csrf_header()
    _reject_hidden_application(application_id)
    _application_service().delete_application(application_id)
    return "", 204
