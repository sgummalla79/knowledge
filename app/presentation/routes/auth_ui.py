from functools import wraps
from uuid import UUID

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from app.application.application_service import ApplicationService
from app.application.auth_service import AuthService
from app.application.web_crawl_settings_service import WebCrawlSettingsService
from app.constants import (
    DEFAULT_DASHBOARD_APPLICATION_ID,
    DEFAULT_MCP_APPLICATION_ID,
    EMBEDDING_PROVIDER_DISPLAY_NAMES,
    SUPPORTED_SCOPES,
)
from app.container import get_session
from app.domain import error_codes
from app.domain.errors import AuthenticationError, DomainError, ValidationError
from app.infrastructure.repositories.application_repository import ApplicationRepository
from app.infrastructure.repositories.embedding_provider_settings_repository import (
    EmbeddingProviderSettingsRepository,
)
from app.infrastructure.repositories.refresh_token_repository import RefreshTokenRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.repositories.web_crawl_settings_repository import WebCrawlSettingsRepository
from app.presentation.web.csrf import csrf_token, validate_csrf
from app.presentation.web.spa import serve_spa_shell

# Built-in service-account Applications — internal plumbing, never shown in or manageable from the
# Applications dashboard page (see _applications_with_status/revoke_token/delete_application below).
_HIDDEN_APPLICATION_IDS = {DEFAULT_MCP_APPLICATION_ID, DEFAULT_DASHBOARD_APPLICATION_ID}

auth_ui_bp = Blueprint("auth_ui", __name__)
auth_ui_bp.add_app_template_global(csrf_token)


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


@auth_ui_bp.context_processor
def _inject_embedding_provider_nav_status():
    """Every dashboard page's sidebar shows which embedding provider (if any) is currently
    active, since it's a single global setting relevant no matter which page you're on — not
    just something you'd notice by visiting Configuration. Skips the DB round-trip on
    unauthenticated requests (login) this blueprint also serves."""
    if not session.get("user_id"):
        return {}
    configs = EmbeddingProviderSettingsRepository(get_session()).list()
    enabled_by_provider = {config.provider: config.enabled for config in configs}
    return {
        "sidebar_embedding_providers": [
            {"provider": provider, "display_name": display_name, "enabled": enabled_by_provider.get(provider, False)}
            for provider, display_name in EMBEDDING_PROVIDER_DISPLAY_NAMES.items()
        ]
    }


def _web_crawl_settings_service() -> WebCrawlSettingsService:
    return WebCrawlSettingsService(WebCrawlSettingsRepository(get_session()))


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


def _csrf_valid() -> bool:
    return validate_csrf(request.form.get("csrf_token"))


def _is_safe_redirect(url: str) -> bool:
    # Relative path only — rules out "//evil.com/..." (scheme-relative) and absolute URLs, both of
    # which would send a post-login redirect off this host.
    return url.startswith("/") and not url.startswith("//")


def _consume_post_login_redirect() -> str:
    # The React /workspace SPA is the default landing page post-login — the Jinja /dashboard (and
    # the rest of the admin area) is still fully intact and reachable via the workspace sidebar's
    # account menu, just no longer where a plain login (no explicit `next`) lands.
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


def _applications_with_status(service: ApplicationService, refresh_tokens: RefreshTokenRepository) -> list[dict]:
    rows = []
    for application in service.list_applications():
        # Built-in service-account Applications (app/infrastructure/auth/bootstrap.py) are internal
        # plumbing, not something an admin registered or should manage here — deleting or
        # regenerating either would silently break the bundled MCP server's or the /workspace SPA's
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
            {
                "id": application.id,
                "name": application.name,
                "allowed_scopes": application.allowed_scopes,
                "token_status": status,
                "last_used_at": last_used_at,
            }
        )
    return rows


@auth_ui_bp.get("/dashboard")
@login_required
def dashboard():
    user = UserRepository(get_session()).get()
    if user is not None and user.must_change_password:
        return redirect(url_for("auth_ui.change_password"))
    service = _application_service()
    applications = _applications_with_status(service, RefreshTokenRepository(get_session()))
    return render_template("dashboard.html", applications=applications)


@auth_ui_bp.get("/dashboard/configuration")
@login_required
def configuration():
    user = UserRepository(get_session()).get()
    if user is not None and user.must_change_password:
        return redirect(url_for("auth_ui.change_password"))
    return render_template("configuration.html", web_crawl_settings=_web_crawl_settings_service().get_status())


@auth_ui_bp.get("/api-docs")
@login_required
def api_docs():
    user = UserRepository(get_session()).get()
    if user is not None and user.must_change_password:
        return redirect(url_for("auth_ui.change_password"))
    return render_template("api_docs.html")


@auth_ui_bp.get("/dashboard/schema")
@login_required
def schema():
    user = UserRepository(get_session()).get()
    if user is not None and user.must_change_password:
        return redirect(url_for("auth_ui.change_password"))
    return render_template("schema.html")


@auth_ui_bp.get("/dashboard/clients/register")
@login_required
def register_application_page():
    user = UserRepository(get_session()).get()
    if user is not None and user.must_change_password:
        return redirect(url_for("auth_ui.change_password"))
    return render_template("register_application.html", scope_groups=_grouped_scopes(SUPPORTED_SCOPES))


@auth_ui_bp.post("/dashboard/applications")
@login_required
def register_application():
    if not _csrf_valid():
        return render_template(
            "register_application.html",
            scope_groups=_grouped_scopes(SUPPORTED_SCOPES),
            error="Session expired — please try again.",
        ), 400
    name = request.form.get("name", "").strip()
    scopes = request.form.getlist("scopes")
    try:
        raw_secret, application = _application_service().register(name, scopes)
    except DomainError as error:
        return render_template(
            "register_application.html",
            scope_groups=_grouped_scopes(SUPPORTED_SCOPES),
            error=error.message,
        ), 400
    return render_template(
        "register_application.html",
        scope_groups=_grouped_scopes(SUPPORTED_SCOPES),
        new_credential={"name": application.name, "client_id": application.id, "client_secret": raw_secret},
    )


@auth_ui_bp.post("/dashboard/applications/<uuid:application_id>/revoke-token")
@login_required
def revoke_token(application_id: UUID):
    service = _application_service()
    # Not reachable through the dashboard UI (filtered out of _applications_with_status) — this
    # guard is defense in depth against a direct POST to this URL.
    if _csrf_valid() and application_id not in _HIDDEN_APPLICATION_IDS:
        service.revoke_application_token(application_id)
    return redirect(url_for("auth_ui.dashboard"))


@auth_ui_bp.post("/dashboard/applications/<uuid:application_id>/delete")
@login_required
def delete_application(application_id: UUID):
    service = _application_service()
    if _csrf_valid() and application_id not in _HIDDEN_APPLICATION_IDS:
        service.delete_application(application_id)
    return redirect(url_for("auth_ui.dashboard"))


@auth_ui_bp.post("/dashboard/web-crawl-settings")
@login_required
def update_web_crawl_settings():
    if _csrf_valid():
        user_agent = request.form.get("user_agent", "").strip()
        if user_agent:
            _web_crawl_settings_service().update(user_agent)
    return redirect(url_for("auth_ui.configuration"))
