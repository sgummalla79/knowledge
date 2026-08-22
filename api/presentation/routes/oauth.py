from urllib.parse import urlencode
from uuid import UUID

from flask import Blueprint, jsonify, redirect, request, session, url_for

from api.application.oauth_authorization_service import OAuthAuthorizationService
from api.constants import ACCESS_TOKEN_TTL_MINUTES
from api.container import get_session
from api.domain import error_codes
from api.domain.errors import AuthenticationError, ForbiddenError, ValidationError
from api.infrastructure.repositories.application_oauth_client_repository import ApplicationOAuthClientRepository
from api.infrastructure.repositories.application_repository import ApplicationRepository
from api.infrastructure.repositories.authorization_code_repository import AuthorizationCodeRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.infrastructure.repositories.refresh_token_repository import RefreshTokenRepository
from api.presentation.web.csrf import validate_csrf
from api.presentation.web.spa import serve_spa_shell

# POST /oauth/token speaks standard OAuth 2.0 (RFC 6749), deliberately not this app's usual JSON
# error envelope ({"error": {"code","message","field"}}) — real OAuth2 client libraries, which is
# the entire point of offering these grant types, expect a form-encoded request and a JSON
# response shaped {access_token, token_type, expires_in, refresh_token?} on success or
# {error, error_description} on failure. It has no session/CSRF involved at all: it's a
# machine-to-machine, credential-in-body endpoint with no cookie in play, so CSRF (which protects
# cookie-authenticated browser requests) doesn't apply.
#
# GET/POST /oauth/authorize is the one genuinely browser-facing, session-authenticated piece —
# server-side validation of client_id/redirect_uri/PKCE params happens independently on *both* the
# GET (render) and POST (decision) legs, since POST never trusts client-echoed data for the
# security decision. If client_id or redirect_uri itself can't be validated, GET renders an error
# page directly rather than redirecting anywhere — redirect_uri isn't trusted yet at that point,
# and redirecting to an unproven URL would be an open-redirect risk. Once both check out, any
# further problem redirects to that now-trusted redirect_uri with ?error=..., per spec.
oauth_bp = Blueprint("oauth", __name__, url_prefix="/oauth")

# RFC 8414 requires this at the domain root, not under /oauth — a separate, unprefixed blueprint.
well_known_bp = Blueprint("well_known", __name__)

_GENERIC_INVALID_REQUEST_MESSAGE = (
    "This connection request is invalid or has expired. Please ask the application to try again."
)


def _service() -> OAuthAuthorizationService:
    session_ = get_session()
    return OAuthAuthorizationService(
        ApplicationRepository(session_),
        ApplicationOAuthClientRepository(session_),
        AuthorizationCodeRepository(session_),
        RefreshTokenRepository(session_),
    )


def _oauth_error(error: str, description: str, status: int):
    response = jsonify({"error": error, "error_description": description})
    response.status_code = status
    return response


@oauth_bp.post("/token")
def issue_token():
    grant_type = request.form.get("grant_type")

    if grant_type == "client_credentials":
        client_id = request.form.get("client_id", "")
        client_secret = request.form.get("client_secret", "")
        try:
            client_uuid = UUID(client_id)
            access_token = _service().issue_client_credentials_token(client_uuid, client_secret)
        except (ValueError, AuthenticationError):
            return _oauth_error(error_codes.OAUTH_INVALID_CLIENT, "Invalid client_id or client_secret.", 401)
        return jsonify(
            {"access_token": access_token, "token_type": "Bearer", "expires_in": ACCESS_TOKEN_TTL_MINUTES * 60}
        )

    if grant_type == "authorization_code":
        code = request.form.get("code", "")
        redirect_uri = request.form.get("redirect_uri", "")
        client_id = request.form.get("client_id", "")
        code_verifier = request.form.get("code_verifier", "")
        try:
            client_uuid = UUID(client_id)
        except ValueError:
            return _oauth_error(error_codes.OAUTH_INVALID_CLIENT, "Invalid client_id.", 401)
        try:
            access_token, refresh_token = _service().exchange_authorization_code(
                code, redirect_uri, client_uuid, code_verifier
            )
        except ValidationError as error:
            return _oauth_error(error_codes.OAUTH_INVALID_GRANT, error.message, 400)
        body = {"access_token": access_token, "token_type": "Bearer", "expires_in": ACCESS_TOKEN_TTL_MINUTES * 60}
        if refresh_token is not None:
            body["refresh_token"] = refresh_token
        return jsonify(body)

    if grant_type == "refresh_token":
        refresh_token = request.form.get("refresh_token", "")
        client_id = request.form.get("client_id", "")
        try:
            client_uuid = UUID(client_id)
        except ValueError:
            return _oauth_error(error_codes.OAUTH_INVALID_CLIENT, "Invalid client_id.", 401)
        try:
            access_token = _service().refresh_access_token(refresh_token, client_uuid)
        except ValidationError as error:
            return _oauth_error(error_codes.OAUTH_INVALID_GRANT, error.message, 400)
        return jsonify({"access_token": access_token, "token_type": "Bearer", "expires_in": ACCESS_TOKEN_TTL_MINUTES * 60})

    return _oauth_error(
        error_codes.OAUTH_UNSUPPORTED_GRANT_TYPE,
        "Only grant_type=client_credentials, authorization_code, or refresh_token is supported.",
        400,
    )


def _invalid_request_reason(response_type: str | None, code_challenge: str | None, code_challenge_method: str | None) -> str | None:
    if response_type != "code":
        return "response_type must be 'code'."
    if not code_challenge:
        return "code_challenge is required."
    if code_challenge_method != "S256":
        return "code_challenge_method must be 'S256'."
    return None


def _append_redirect_params(redirect_uri: str, params: dict[str, str]) -> str:
    separator = "&" if "?" in redirect_uri else "?"
    return f"{redirect_uri}{separator}{urlencode(params)}"


def _authorize_context(client_id_raw: str, redirect_uri: str):
    """Resolves + validates client_id/redirect_uri, shared by GET and POST — raises
    AuthenticationError (caller renders an error page, never a redirect) for anything wrong with
    the client itself."""
    client_id = UUID(client_id_raw)
    application, oauth_client = _service().get_authorization_code_client(client_id)
    _service().validate_redirect_uri(oauth_client, redirect_uri)
    return client_id, application


@oauth_bp.get("/authorize")
def authorize():
    try:
        client_id, application = _authorize_context(request.args.get("client_id", ""), request.args.get("redirect_uri", ""))
    except (ValueError, AuthenticationError):
        return serve_spa_shell(extra_globals={"OAUTH_ERROR": {"message": _GENERIC_INVALID_REQUEST_MESSAGE}})

    redirect_uri = request.args.get("redirect_uri", "")
    state = request.args.get("state", "")
    invalid_reason = _invalid_request_reason(
        request.args.get("response_type"), request.args.get("code_challenge"), request.args.get("code_challenge_method")
    )
    if invalid_reason:
        return redirect(
            _append_redirect_params(redirect_uri, {"error": "invalid_request", "error_description": invalid_reason, **({"state": state} if state else {})})
        )

    raw_identity_id = session.get("identity_id")
    if not raw_identity_id:
        return redirect(url_for("auth_ui.sign_in", next=request.full_path))

    member = OrgMemberRepository(get_session()).get(application.org_id, UUID(raw_identity_id))
    if member is None:
        return serve_spa_shell(
            extra_globals={"OAUTH_ERROR": {"message": "You're not a member of the organization this application connects to."}}
        )

    organization = OrganizationRepository(get_session()).get(application.org_id)
    return serve_spa_shell(
        extra_globals={
            "OAUTH_AUTHORIZE": {
                "application_name": application.name,
                "org_name": organization.name if organization is not None else "",
                "client_id": str(client_id),
                "redirect_uri": redirect_uri,
                "response_type": request.args.get("response_type", ""),
                "code_challenge": request.args.get("code_challenge", ""),
                "code_challenge_method": request.args.get("code_challenge_method", ""),
                "scope": request.args.get("scope", ""),
                "state": state,
            }
        }
    )


@oauth_bp.post("/authorize")
def authorize_submit():
    raw_identity_id = session.get("identity_id")
    if not raw_identity_id:
        raise AuthenticationError("Not authenticated.")
    if not validate_csrf(request.headers.get("X-CSRF-Token")):
        raise AuthenticationError("Session expired — please reload the page.")

    body = request.get_json(silent=True) or {}
    redirect_uri = body.get("redirect_uri", "")
    try:
        client_id, application = _authorize_context(body.get("client_id", ""), redirect_uri)
    except (ValueError, AuthenticationError):
        raise ValidationError(error_codes.VALIDATION_ERROR, "Invalid authorization request.")

    state = body.get("state", "")
    invalid_reason = _invalid_request_reason(
        body.get("response_type"), body.get("code_challenge"), body.get("code_challenge_method")
    )
    if invalid_reason:
        return jsonify(
            {"redirect": _append_redirect_params(redirect_uri, {"error": "invalid_request", "error_description": invalid_reason, **({"state": state} if state else {})})}
        )

    identity_id = UUID(raw_identity_id)
    member = OrgMemberRepository(get_session()).get(application.org_id, identity_id)
    if member is None:
        raise ForbiddenError("You're not a member of the organization this application connects to.")

    if not body.get("allow", False):
        return jsonify(
            {"redirect": _append_redirect_params(redirect_uri, {"error": "access_denied", "error_description": "The user denied the request.", **({"state": state} if state else {})})}
        )

    code = _service().create_authorization_code(
        application.id, application.org_id, identity_id, redirect_uri, body.get("code_challenge", ""), body.get("scope", "")
    )
    return jsonify({"redirect": _append_redirect_params(redirect_uri, {"code": code, **({"state": state} if state else {})})})


@well_known_bp.get("/.well-known/oauth-authorization-server")
def discovery():
    base = request.url_root.rstrip("/")
    return jsonify(
        {
            "issuer": base,
            "authorization_endpoint": f"{base}/oauth/authorize",
            "token_endpoint": f"{base}/oauth/token",
            "response_types_supported": ["code"],
            "grant_types_supported": ["client_credentials", "authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["client_secret_post", "none"],
        }
    )
