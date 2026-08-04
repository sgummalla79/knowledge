from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from flask import Blueprint, jsonify, redirect, request, url_for

from app.application.authorize_service import AuthorizeService
from app.application.client_registration_service import ClientRegistrationService
from app.application.token_service import TokenService
from app.constants import SUPPORTED_SCOPES
from app.container import get_session
from app.domain import error_codes
from app.domain.errors import AuthenticationError, DomainError, InvalidRedirectUriError, ValidationError
from app.infrastructure.auth.pkce import SUPPORTED_CODE_CHALLENGE_METHOD
from app.infrastructure.repositories.application_repository import ApplicationRepository
from app.infrastructure.repositories.authorization_code_repository import AuthorizationCodeRepository
from app.infrastructure.repositories.refresh_token_repository import RefreshTokenRepository
from app.presentation.routes.auth_ui import login_required
from app.presentation.web.csrf import validate_csrf
from app.presentation.web.spa import serve_spa_shell

oauth_bp = Blueprint("oauth", __name__)


def _service() -> TokenService:
    session = get_session()
    return TokenService(
        ApplicationRepository(session), RefreshTokenRepository(session), AuthorizationCodeRepository(session)
    )


def _authorize_service() -> AuthorizeService:
    session = get_session()
    return AuthorizeService(ApplicationRepository(session), AuthorizationCodeRepository(session))


def _registration_service() -> ClientRegistrationService:
    return ClientRegistrationService(ApplicationRepository(get_session()))


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

    if grant_type == "authorization_code":
        client_id_raw = request.form.get("client_id", "")
        try:
            client_id = UUID(client_id_raw)
        except ValueError:
            raise ValidationError(error_codes.INVALID_REQUEST, "client_id must be a valid UUID.", field="client_id")
        result = _service().authorization_code_grant(
            raw_code=request.form.get("code", ""),
            redirect_uri=request.form.get("redirect_uri", ""),
            client_id=client_id,
            client_secret=request.form.get("client_secret", ""),
            code_verifier=request.form.get("code_verifier", ""),
        )
        return jsonify(result)

    raise ValidationError(
        error_codes.UNSUPPORTED_GRANT_TYPE, f"Unsupported grant_type '{grant_type}'.", field="grant_type"
    )


@oauth_bp.post("/oauth/register")
def register_client():
    # RFC 7591 Dynamic Client Registration — deliberately unauthenticated, matching the rest of
    # this endpoint's trust boundary: knowledge only ever binds to 127.0.0.1 (see CLAUDE.md),
    # so anything that can reach this route is already a local process on this machine.
    body = request.get_json(silent=True) or {}
    client_name = body.get("client_name", "")
    redirect_uris = body.get("redirect_uris") or []
    raw_secret, application = _registration_service().register_client(client_name, redirect_uris)
    return (
        jsonify(
            {
                "client_id": str(application.id),
                "client_secret": raw_secret,
                "client_name": application.name,
                "redirect_uris": application.redirect_uris,
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "client_secret_post",
                "scope": " ".join(application.allowed_scopes),
            }
        ),
        201,
    )


def _authorize_params(source) -> dict:
    return {
        "response_type": source.get("response_type", ""),
        "client_id": source.get("client_id", ""),
        "redirect_uri": source.get("redirect_uri", ""),
        "scope": source.get("scope", "").split(),
        "state": source.get("state", ""),
        "code_challenge": source.get("code_challenge", ""),
        "code_challenge_method": source.get("code_challenge_method", ""),
    }


def _authorize_params_from_json(body: dict) -> dict:
    # The React consent page (AuthorizePage.tsx) POSTs back exactly the params it was handed by
    # the GET request below, as JSON — scope travels as an array here (what GET already injected
    # into window.__OAUTH_AUTHORIZE__), not the space-separated string request.args uses.
    return {
        "response_type": body.get("response_type", ""),
        "client_id": body.get("client_id", ""),
        "redirect_uri": body.get("redirect_uri", ""),
        "scope": body.get("scope") or [],
        "state": body.get("state", ""),
        "code_challenge": body.get("code_challenge", ""),
        "code_challenge_method": body.get("code_challenge_method", ""),
    }


def _append_query_params(url: str, extra: dict) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query.update(extra)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _error_redirect(redirect_uri: str, error_code: str, state: str) -> str:
    extra = {"error": error_code}
    if state:
        extra["state"] = state
    return _append_query_params(redirect_uri, extra)


def _code_redirect(redirect_uri: str, code: str, state: str) -> str:
    extra = {"code": code}
    if state:
        extra["state"] = state
    return _append_query_params(redirect_uri, extra)


def _parsed_client_id(raw: str) -> UUID | None:
    try:
        return UUID(raw)
    except ValueError:
        return None


@oauth_bp.get("/oauth/authorize")
@login_required
def authorize():
    params = _authorize_params(request.args)
    client_id = _parsed_client_id(params["client_id"])
    if client_id is None:
        return serve_spa_shell(extra_globals={"OAUTH_ERROR": "client_id must be a valid UUID."})

    service = _authorize_service()
    try:
        application = service.validate_request(client_id, params["redirect_uri"])
    except InvalidRedirectUriError as error:
        return serve_spa_shell(extra_globals={"OAUTH_ERROR": error.message})

    # From here redirect_uri is trusted (registered to this application), so any further problem
    # is reported back to the client via redirect rather than an error page.
    if not params["code_challenge"]:
        return redirect(_error_redirect(params["redirect_uri"], error_codes.INVALID_REQUEST, params["state"]))
    try:
        service.validate_authorization_params(
            application, params["response_type"], params["scope"], params["code_challenge_method"]
        )
    except DomainError as error:
        return redirect(_error_redirect(params["redirect_uri"], error.code, params["state"]))

    return serve_spa_shell(
        extra_globals={"OAUTH_AUTHORIZE": {"application_name": application.name, "params": params}}
    )


@oauth_bp.post("/oauth/authorize")
@login_required
def authorize_submit():
    # Session+CSRF authenticated JSON, matching /login and /change-password's convention — the
    # React consent page (AuthorizePage.tsx) POSTs here with the params it was handed by the GET
    # above, plus the chosen action. Not part of the bearer-token API: this is a browser-session
    # flow, never something a scoped access token would call.
    if not validate_csrf(request.headers.get("X-CSRF-Token")):
        raise AuthenticationError("Session expired — please reload the page.")

    body = request.get_json(silent=True) or {}
    params = _authorize_params_from_json(body)

    client_id = _parsed_client_id(params["client_id"])
    if client_id is None:
        raise ValidationError(error_codes.INVALID_REQUEST, "client_id must be a valid UUID.", field="client_id")

    service = _authorize_service()
    application = service.validate_request(client_id, params["redirect_uri"])

    if body.get("action") != "approve":
        return jsonify({"redirect": _error_redirect(params["redirect_uri"], error_codes.ACCESS_DENIED, params["state"])})

    try:
        service.validate_authorization_params(
            application, params["response_type"], params["scope"], params["code_challenge_method"]
        )
        code = service.create_authorization_code(
            application,
            params["redirect_uri"],
            params["code_challenge"],
            params["code_challenge_method"],
            params["scope"],
        )
    except DomainError as error:
        return jsonify({"redirect": _error_redirect(params["redirect_uri"], error.code, params["state"])})

    return jsonify({"redirect": _code_redirect(params["redirect_uri"], code, params["state"])})


@oauth_bp.get("/.well-known/oauth-authorization-server")
def authorization_server_metadata():
    base = request.host_url.rstrip("/")
    return jsonify(
        {
            "issuer": base,
            "authorization_endpoint": url_for("oauth.authorize", _external=True),
            "token_endpoint": url_for("oauth.issue_token", _external=True),
            "registration_endpoint": url_for("oauth.register_client", _external=True),
            "scopes_supported": SUPPORTED_SCOPES,
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "client_credentials", "refresh_token"],
            "code_challenge_methods_supported": [SUPPORTED_CODE_CHALLENGE_METHOD],
            "token_endpoint_auth_methods_supported": ["client_secret_post"],
        }
    )
