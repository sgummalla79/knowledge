from functools import wraps
from uuid import UUID

from flask import Blueprint, g, jsonify, request, session

from api.application.auth_service import AuthService
from api.application.org_membership_service import OrgMembershipService
from api.application.org_name_validation import validate_org_slug
from api.application.signup_service import SignupService
from api.constants import LOGIN_RATE_LIMIT
from api.container import get_session, set_rls_session_vars
from api.domain import error_codes
from api.domain.errors import AuthenticationError, ValidationError
from api.infrastructure.auth.password_identity_verifier import PasswordIdentityVerifier
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.infrastructure.repositories.profile_repository import ProfileRepository
from api.presentation.web.csrf import csrf_token, validate_csrf
from api.presentation.web.session_guard import resolve_cookie_session
from api.rate_limit import _login_rate_limit_key, limiter

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
    return OrgMembershipService(
        OrganizationRepository(session_),
        OrgMemberRepository(session_),
        IdentityRepository(session_),
        ProfileRepository(session_),
    )


def _signup_service() -> SignupService:
    return SignupService(_identities(), _org_membership_service())


def require_org_session(view):
    """JSON API gate — every resource route (categories/documents/query/...) needs both an
    authenticated identity and an active org membership. Raises AuthenticationError (401 JSON)
    rather than redirecting, since these are fetch()-called from within the already-gated SPA.
    Does not check any specific permission itself (see require_permission in app_auth.py, which
    wraps this for routes that need one) — only identity/org-membership (and, via
    resolve_cookie_session, the org's configured session-inactivity timeout)."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        resolved = resolve_cookie_session()
        if resolved is None:
            raise AuthenticationError("Not authenticated.")
        g.user_id, g.org_id = resolved
        set_rls_session_vars(g.org_id, g.user_id)
        return view(*args, **kwargs)

    return wrapped


def _is_safe_redirect(url: str) -> bool:
    # Relative path only — rules out "//evil.com/..." (scheme-relative) and absolute URLs, both of
    # which would send a post-login redirect off this host.
    return url.startswith("/") and not url.startswith("//")


def _consume_post_login_redirect() -> str:
    # The org's own home ("/<org-slug>") is the default landing page for a plain login (no
    # explicit `next`) — the rest of the app is still fully reachable via the nav bar. Falls back
    # to bare "/" only for the sliver of a window where a membership doesn't exist yet (mid-signup
    # failure — see _establish_session) and there's no org to land on at all.
    #
    # Plain string paths, not url_for() — this API no longer serves any HTML shell itself (see
    # deleted app_shell.py); these are just redirect-target data handed to whatever frontend is
    # calling, which owns interpreting/routing them.
    next_url = session.pop("post_login_redirect", None)
    if next_url and _is_safe_redirect(next_url):
        return next_url
    org_id = session.get("active_org_id")
    if org_id:
        organization = OrganizationRepository(get_session()).get(UUID(org_id))
        if organization is not None:
            return f"/{organization.slug}"
    return "/"


def _establish_session(identity_id: UUID) -> None:
    """Sets the session's active org for a freshly authenticated identity — always its one and
    only org membership (an identity belongs to exactly one org for its whole life; see
    domain/entities.py's Identity docstring), or none yet for the rare case a membership hasn't
    been created (mid-signup failure)."""
    memberships = _auth_service().list_orgs_for_identity(identity_id)
    session["identity_id"] = str(identity_id)
    if memberships:
        session["active_org_id"] = str(memberships[0])


@auth_ui_bp.post("/sign-in")
@limiter.limit(LOGIN_RATE_LIMIT, key_func=_login_rate_limit_key)
def sign_in_submit():
    # Served to the React sign-in page via fetch — JSON in/out, CSRF via header rather than a
    # form field. `next` (e.g. "come back to the OAuth consent screen after signing in") now
    # arrives as a body field rather than a GET ?next= query param — this API no longer has a GET
    # /sign-in route to read one from (see deleted app_shell.py); the frontend reads its own
    # client-side route's ?next= and passes it along here instead.
    if not validate_csrf(request.headers.get("X-CSRF-Token")):
        raise AuthenticationError("Session expired — please reload the page.")
    body = request.get_json(silent=True) or {}
    identity = _auth_service().login(body.get("username", ""), body.get("password", ""))
    next_url = body.get("next")
    if next_url and _is_safe_redirect(next_url):
        session["post_login_redirect"] = next_url
    _establish_session(identity.id)
    redirect_url = "/change-password" if identity.must_change_password else _consume_post_login_redirect()
    return jsonify({"redirect": redirect_url})


@auth_ui_bp.post("/sign-up")
def sign_up_submit():
    if not validate_csrf(request.headers.get("X-CSRF-Token")):
        raise AuthenticationError("Session expired — please reload the page.")
    body = request.get_json(silent=True) or {}
    password = body.get("password", "")
    if len(password) < 8:
        raise ValidationError(error_codes.VALIDATION_ERROR, "Password must be at least 8 characters.", field="password")
    identity, _organization = _signup_service().signup(
        body.get("username", ""), password, body.get("name", ""), body.get("org_name", ""), body.get("email", "")
    )
    _establish_session(identity.id)
    return jsonify({"redirect": _consume_post_login_redirect()})


@auth_ui_bp.get("/check-org-name")
def check_org_name():
    """Live availability check for the org name field on the sign-up form — unauthenticated (no
    identity/session exists yet at signup) and deliberately never errors on a taken or malformed
    name; that's an ordinary, expected outcome for a probe endpoint, not a failure."""
    name = request.args.get("name", "")
    try:
        validate_org_slug(name)
    except ValidationError as exc:
        return jsonify({"available": False, "message": exc.message})
    if OrganizationRepository(get_session()).get_by_slug(name) is not None:
        return jsonify({"available": False, "message": "That org name is already taken."})
    return jsonify({"available": True, "message": None})


@auth_ui_bp.post("/change-password")
def change_password_submit():
    # Not @require_org_session: this must also work for the rare mid-signup identity that has no
    # org yet (see _establish_session) — only an authenticated identity is required, same
    # inline-check pattern oauth.py's authorize_submit() already uses for the same reason.
    raw_identity_id = session.get("identity_id")
    if not raw_identity_id:
        raise AuthenticationError("Not authenticated.")
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
    _auth_service().change_password(UUID(raw_identity_id), new_password)
    return jsonify({"redirect": _consume_post_login_redirect()})


@auth_ui_bp.post("/logout")
def logout():
    # JSON, not a redirect — this API serves no HTML page to redirect to (see deleted
    # app_shell.py); the caller (a browser frontend) navigates itself after this succeeds.
    session.clear()
    return jsonify({"success": True})


@auth_ui_bp.get("/csrf-token")
def get_csrf_token():
    """Bootstrap endpoint for any browser-based frontend: fetch a token once at load, before any
    session even exists yet (sign-in itself needs one). Calling csrf_token() both returns the
    token and — via Flask writing session["csrf_token"] — sets the session cookie on this
    response, exactly as the old serve_spa_shell()-embedded flow did (see api/presentation/web/
    csrf.py; Flask sets the session cookie on any response that writes to the session dict, not
    specifically an HTML one)."""
    return jsonify({"csrf_token": csrf_token()})


@auth_ui_bp.get("/session")
@require_org_session
def get_session_info():
    """Bootstrap endpoint replacing the data the deleted app_shell.py catch-all used to embed
    directly into the served HTML (USERNAME/ORG_ID/ORG_SLUG globals) — a browser frontend now
    fetches this once instead. 401 (via require_org_session) if not logged in, deliberately no
    redirect — that's a frontend concern now, not this API's."""
    identity = IdentityRepository(get_session()).get_by_id(g.user_id)
    organization = OrganizationRepository(get_session()).get(g.org_id)
    return jsonify(
        {
            "username": identity.username if identity is not None else "",
            "org_id": str(g.org_id),
            "org_slug": organization.slug if organization is not None else None,
        }
    )
