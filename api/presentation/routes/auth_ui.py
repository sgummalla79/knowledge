from functools import wraps
from uuid import UUID

from flask import Blueprint, g, jsonify, redirect, request, session, url_for

from api.application.auth_service import AuthService
from api.application.org_membership_service import OrgMembershipService
from api.application.signup_service import SignupService
from api.container import get_session, set_rls_session_vars
from api.domain import error_codes
from api.domain.errors import AuthenticationError, ValidationError
from api.infrastructure.auth.password_identity_verifier import PasswordIdentityVerifier
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.presentation.web.csrf import validate_csrf
from api.presentation.web.spa import serve_spa_shell

auth_ui_bp = Blueprint("auth_ui", __name__)


def _identities() -> IdentityRepository:
    return IdentityRepository(get_session())


def _org_members() -> OrgMemberRepository:
    return OrgMemberRepository(get_session())


def _auth_service() -> AuthService:
    session_ = get_session()
    identities = IdentityRepository(session_)
    return AuthService(identities, PasswordIdentityVerifier(identities), OrgMemberRepository(session_))


def _org_membership_service() -> OrgMembershipService:
    session_ = get_session()
    return OrgMembershipService(OrganizationRepository(session_), OrgMemberRepository(session_), IdentityRepository(session_))


def _signup_service() -> SignupService:
    return SignupService(_identities(), _org_membership_service())


def login_required(view):
    """Browser-facing gate for the SPA shell pages (/workspace, /settings) — redirects to /login
    rather than the 401 JSON require_org_session below returns for the JSON API, since a browser
    navigation following a redirect makes sense but a fetch() call following one silently would
    just get back an HTML login page instead of the JSON it expected."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        raw_identity_id = session.get("identity_id")
        if not raw_identity_id:
            # Only GET requests get a `next` — redirecting a blocked POST back to itself would
            # just re-GET that URL after login, not resubmit the form.
            next_url = request.full_path if request.method == "GET" else None
            return redirect(url_for("auth_ui.sign_in", next=next_url))
        # identity_id/active_org_id/active_role are cached in the session at login/switch time
        # (see login_submit/switch_org) rather than re-fetched from the DB on every gated request —
        # keeps this decorator a pure session-dict read so route tests can fake a session without
        # seeding a real identity row (see tests/unit/test_workspace_routes.py). A view that needs
        # the freshest possible state (e.g. must_change_password right after it's cleared) fetches
        # it itself — see workspace._serve_spa_page.
        g.user_id = UUID(raw_identity_id)
        g.org_id = UUID(session["active_org_id"]) if session.get("active_org_id") else None
        g.role = session.get("active_role")
        if g.org_id is not None:
            set_rls_session_vars(g.org_id, g.user_id)
        return view(*args, **kwargs)

    return wrapped


def require_org_session(view):
    """JSON API gate — every resource route (categories/documents/query/...) needs both an
    authenticated identity and an active org membership. Raises AuthenticationError (401 JSON)
    rather than redirecting, since these are fetch()-called from within the already-gated SPA."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        raw_identity_id = session.get("identity_id")
        raw_org_id = session.get("active_org_id")
        if not raw_identity_id or not raw_org_id:
            raise AuthenticationError("Not authenticated.")
        g.user_id = UUID(raw_identity_id)
        g.org_id = UUID(raw_org_id)
        g.role = session.get("active_role")
        set_rls_session_vars(g.org_id, g.user_id)
        return view(*args, **kwargs)

    return wrapped


def _is_safe_redirect(url: str) -> bool:
    # Relative path only — rules out "//evil.com/..." (scheme-relative) and absolute URLs, both of
    # which would send a post-login redirect off this host.
    return url.startswith("/") and not url.startswith("//")


def _consume_post_login_redirect() -> str:
    # Home ("/") is the default landing page for a plain login (no explicit `next`) — the rest of
    # the app is still fully reachable via the nav bar.
    next_url = session.pop("post_login_redirect", None)
    return next_url if next_url and _is_safe_redirect(next_url) else url_for("app_shell.app_shell")


def _establish_session(identity_id: UUID) -> None:
    """Picks an active org for a freshly authenticated identity — deterministically the first
    membership for now (an org switcher UI, backed by POST /orgs/<id>/switch, picks a different
    one later without needing to touch this)."""
    memberships = _auth_service().list_orgs_for_identity(identity_id)
    session["identity_id"] = str(identity_id)
    if memberships:
        org_id, role = memberships[0]
        session["active_org_id"] = str(org_id)
        session["active_role"] = role


@auth_ui_bp.get("/sign-in")
def sign_in():
    next_url = request.args.get("next")
    if next_url and _is_safe_redirect(next_url):
        session["post_login_redirect"] = next_url
    if session.get("identity_id"):
        return redirect(_consume_post_login_redirect())
    return serve_spa_shell()


@auth_ui_bp.post("/sign-in")
def sign_in_submit():
    # Served to the React sign-in page via fetch — JSON in/out, CSRF via header rather than a
    # form field.
    if not validate_csrf(request.headers.get("X-CSRF-Token")):
        raise AuthenticationError("Session expired — please reload the page.")
    body = request.get_json(silent=True) or {}
    identity = _auth_service().login(body.get("email", ""), body.get("password", ""))
    _establish_session(identity.id)
    redirect_url = (
        url_for("auth_ui.change_password") if identity.must_change_password else _consume_post_login_redirect()
    )
    return jsonify({"redirect": redirect_url})


@auth_ui_bp.get("/sign-up")
def sign_up():
    if session.get("identity_id"):
        return redirect(_consume_post_login_redirect())
    return serve_spa_shell()


@auth_ui_bp.post("/sign-up")
def sign_up_submit():
    if not validate_csrf(request.headers.get("X-CSRF-Token")):
        raise AuthenticationError("Session expired — please reload the page.")
    body = request.get_json(silent=True) or {}
    password = body.get("password", "")
    if len(password) < 8:
        raise ValidationError(error_codes.VALIDATION_ERROR, "Password must be at least 8 characters.", field="password")
    identity, _organization = _signup_service().signup(body.get("email", ""), password, body.get("name", ""))
    _establish_session(identity.id)
    return jsonify({"redirect": _consume_post_login_redirect()})


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
    _auth_service().change_password(UUID(session["identity_id"]), new_password)
    return jsonify({"redirect": _consume_post_login_redirect()})


@auth_ui_bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth_ui.sign_in"))
