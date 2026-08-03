from functools import wraps
from uuid import UUID

from flask import Blueprint, abort, redirect, render_template, request, session, url_for

from app.application.application_service import ApplicationService
from app.application.auth_service import AuthService
from app.application.embedding_provider_settings_service import EmbeddingProviderConfigService
from app.application.web_crawl_settings_service import WebCrawlSettingsService
from app.constants import (
    DEFAULT_MCP_APPLICATION_ID,
    EMBEDDING_PROVIDER_DISPLAY_NAMES,
    EMBEDDING_PROVIDERS_REQUIRING_API_KEY,
    EMBEDDING_PROVIDERS_REQUIRING_BASE_URL,
    EMBEDDING_PROVIDERS_SUPPORTING_BASE_URL,
    SUPPORTED_SCOPES,
)
from app.container import get_session
from app.domain.errors import DomainError
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry
from app.infrastructure.repositories.application_repository import ApplicationRepository
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.embedding_provider_settings_repository import (
    EmbeddingProviderSettingsRepository,
)
from app.infrastructure.repositories.refresh_token_repository import RefreshTokenRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.repositories.web_crawl_settings_repository import WebCrawlSettingsRepository
from app.presentation.web.csrf import csrf_token, validate_csrf

auth_ui_bp = Blueprint("auth_ui", __name__)
auth_ui_bp.add_app_template_global(csrf_token)
# So _sidebar.html can render the "Voyage"/"OpenAI"/"Ollama" nav-sub links on every dashboard
# page without every route that includes it having to pass the list explicitly.
auth_ui_bp.add_app_template_global(EMBEDDING_PROVIDER_DISPLAY_NAMES, name="embedding_provider_display_names")


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


def _embedding_provider_config_service() -> EmbeddingProviderConfigService:
    session_ = get_session()
    return EmbeddingProviderConfigService(EmbeddingProviderSettingsRepository(session_), ChunkRepository(session_))


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
    next_url = session.pop("post_login_redirect", None)
    return next_url if next_url and _is_safe_redirect(next_url) else url_for("auth_ui.dashboard")


@auth_ui_bp.get("/login")
def login():
    next_url = request.args.get("next")
    if next_url and _is_safe_redirect(next_url):
        session["post_login_redirect"] = next_url
    if session.get("user_id"):
        return redirect(_consume_post_login_redirect())
    return render_template("login.html")


@auth_ui_bp.post("/login")
def login_submit():
    if not _csrf_valid():
        return render_template("login.html", error="Session expired — please try again."), 400
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    try:
        user = _auth_service().login(username, password)
    except DomainError as error:
        return render_template("login.html", error=error.message), 401
    session["user_id"] = str(user.id)
    if user.must_change_password:
        return redirect(url_for("auth_ui.change_password"))
    return redirect(_consume_post_login_redirect())


@auth_ui_bp.get("/change-password")
@login_required
def change_password():
    return render_template("change_password.html")


@auth_ui_bp.post("/change-password")
@login_required
def change_password_submit():
    if not _csrf_valid():
        return render_template("change_password.html", error="Session expired — please try again."), 400
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")
    if len(new_password) < 8:
        return render_template("change_password.html", error="Password must be at least 8 characters."), 400
    if new_password != confirm_password:
        return render_template("change_password.html", error="Passwords do not match."), 400
    _auth_service().change_password(UUID(session["user_id"]), new_password)
    return redirect(_consume_post_login_redirect())


@auth_ui_bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth_ui.login"))


def _applications_with_status(service: ApplicationService, refresh_tokens: RefreshTokenRepository) -> list[dict]:
    rows = []
    for application in service.list_applications():
        # The built-in MCP service-account Application (app/infrastructure/auth/bootstrap.py) is
        # internal plumbing, not something an admin registered or should manage here — deleting or
        # regenerating it would silently break the bundled MCP server's connection to this API.
        if application.id == DEFAULT_MCP_APPLICATION_ID:
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
    if _csrf_valid() and application_id != DEFAULT_MCP_APPLICATION_ID:
        service.revoke_application_token(application_id)
    return redirect(url_for("auth_ui.dashboard"))


@auth_ui_bp.post("/dashboard/applications/<uuid:application_id>/delete")
@login_required
def delete_application(application_id: UUID):
    service = _application_service()
    if _csrf_valid() and application_id != DEFAULT_MCP_APPLICATION_ID:
        service.delete_application(application_id)
    return redirect(url_for("auth_ui.dashboard"))


def _require_known_provider(provider: str) -> None:
    if provider not in EmbeddingProviderRegistry.known_providers():
        abort(404)


@auth_ui_bp.get("/dashboard/configuration/embeddings/<provider>")
@login_required
def embedding_provider_settings(provider: str, error: str | None = None):
    _require_known_provider(provider)
    user = UserRepository(get_session()).get()
    if user is not None and user.must_change_password:
        return redirect(url_for("auth_ui.change_password"))
    return render_template(
        "embedding_provider_settings.html",
        provider=provider,
        display_name=EMBEDDING_PROVIDER_DISPLAY_NAMES.get(provider, provider),
        status=_embedding_provider_config_service().get_status(provider),
        api_key_required=provider in EMBEDDING_PROVIDERS_REQUIRING_API_KEY,
        base_url_required=provider in EMBEDDING_PROVIDERS_REQUIRING_BASE_URL,
        base_url_supported=provider in EMBEDDING_PROVIDERS_SUPPORTING_BASE_URL,
        error=error,
    )


@auth_ui_bp.post("/dashboard/configuration/embeddings/<provider>")
@login_required
def update_embedding_provider_settings(provider: str):
    _require_known_provider(provider)
    if not _csrf_valid():
        return embedding_provider_settings(provider, error="Session expired — please try again."), 400

    try:
        dimensions = int(request.form.get("dimensions", "").strip())
        chunk_size = int(request.form.get("chunk_size", "").strip())
        chunk_overlap = int(request.form.get("chunk_overlap", "").strip())
    except ValueError:
        return embedding_provider_settings(
            provider, error="Dimensions, chunk size, and chunk overlap must be whole numbers."
        )

    model = request.form.get("model", "").strip()
    base_url = request.form.get("base_url", "").strip() or None
    api_key = request.form.get("api_key", "").strip() or None
    if api_key is None:
        # "Leave blank to keep the current key" — the form never round-trips a saved key back
        # into the page, so a blank submission means "unchanged", not "clear it".
        existing = EmbeddingProviderSettingsRepository(get_session()).get(provider)
        api_key = existing.api_key if existing is not None else None

    try:
        _embedding_provider_config_service().update_config(
            provider, model, api_key, base_url, dimensions, chunk_size, chunk_overlap
        )
    except DomainError as error:
        return embedding_provider_settings(provider, error=error.message)
    return redirect(url_for("auth_ui.embedding_provider_settings", provider=provider))


@auth_ui_bp.post("/dashboard/configuration/embeddings/<provider>/enable")
@login_required
def enable_embedding_provider_settings(provider: str):
    _require_known_provider(provider)
    if _csrf_valid():
        try:
            _embedding_provider_config_service().enable(provider)
        except DomainError as error:
            return embedding_provider_settings(provider, error=error.message)
    return redirect(url_for("auth_ui.embedding_provider_settings", provider=provider))


@auth_ui_bp.post("/dashboard/configuration/embeddings/<provider>/disable")
@login_required
def disable_embedding_provider_settings(provider: str):
    _require_known_provider(provider)
    if _csrf_valid():
        try:
            _embedding_provider_config_service().disable(provider)
        except DomainError as error:
            return embedding_provider_settings(provider, error=error.message)
    return redirect(url_for("auth_ui.embedding_provider_settings", provider=provider))


@auth_ui_bp.post("/dashboard/web-crawl-settings")
@login_required
def update_web_crawl_settings():
    if _csrf_valid():
        user_agent = request.form.get("user_agent", "").strip()
        if user_agent:
            _web_crawl_settings_service().update(user_agent)
    return redirect(url_for("auth_ui.configuration"))
