from functools import wraps
from uuid import UUID

from flask import Blueprint, g, jsonify, redirect, request, session, url_for

from app.application.auth_service import AuthService
from app.container import get_session
from app.domain import error_codes
from app.domain.errors import AuthenticationError, ValidationError
from app.infrastructure.repositories.user_repository import UserRepository
from app.presentation.web.csrf import validate_csrf
from app.presentation.web.spa import serve_spa_shell

auth_ui_bp = Blueprint("auth_ui", __name__)


def _auth_service() -> AuthService:
    return AuthService(UserRepository(get_session()))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        raw_user_id = session.get("user_id")
        if not raw_user_id:
            # Only GET requests get a `next` — redirecting a blocked POST back to itself would
            # just re-GET that URL after login, not resubmit the form.
            next_url = request.full_path if request.method == "GET" else None
            return redirect(url_for("auth_ui.login", next=next_url))
        # org_id/role are cached in the session at login time (see login_submit) rather than
        # re-fetched from the DB on every gated request — keeps this decorator a pure session-dict
        # read so route tests can fake a session without seeding a real user row (see
        # tests/unit/test_workspace_routes.py). A view that needs the freshest possible user state
        # (e.g. must_change_password right after it's cleared) fetches it itself — see
        # workspace._serve_spa_page.
        g.user_id = UUID(raw_user_id)
        g.org_id = UUID(session["org_id"]) if session.get("org_id") else None
        g.role = session.get("role")
        return view(*args, **kwargs)

    return wrapped


def _is_safe_redirect(url: str) -> bool:
    # Relative path only — rules out "//evil.com/..." (scheme-relative) and absolute URLs, both of
    # which would send a post-login redirect off this host.
    return url.startswith("/") and not url.startswith("//")


def _consume_post_login_redirect() -> str:
    # /workspace is the default landing page for a plain login (no explicit `next`) — the rest of
    # the app is still fully reachable via the workspace sidebar's account menu.
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
    # CSRF via header rather than a form field.
    if not validate_csrf(request.headers.get("X-CSRF-Token")):
        raise AuthenticationError("Session expired — please reload the page.")
    body = request.get_json(silent=True) or {}
    user = _auth_service().login(body.get("username", ""), body.get("password", ""))
    session["user_id"] = str(user.id)
    session["org_id"] = str(user.org_id)
    session["role"] = user.role
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
