from functools import wraps
from uuid import UUID

from flask import Blueprint, redirect, render_template, request, session, url_for

from app.application.application_service import ApplicationService
from app.application.auth_service import AuthService
from app.constants import SUPPORTED_SCOPES
from app.container import get_session
from app.domain.errors import DomainError
from app.infrastructure.repositories.application_repository import ApplicationRepository
from app.infrastructure.repositories.refresh_token_repository import RefreshTokenRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.presentation.web.csrf import csrf_token, validate_csrf

auth_ui_bp = Blueprint("auth_ui", __name__)
auth_ui_bp.add_app_template_global(csrf_token)


def _auth_service() -> AuthService:
    return AuthService(UserRepository(get_session()))


def _application_service() -> ApplicationService:
    session_ = get_session()
    return ApplicationService(ApplicationRepository(session_), RefreshTokenRepository(session_))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth_ui.login"))
        return view(*args, **kwargs)

    return wrapped


def _csrf_valid() -> bool:
    return validate_csrf(request.form.get("csrf_token"))


@auth_ui_bp.get("/login")
def login():
    if session.get("user_id"):
        return redirect(url_for("auth_ui.dashboard"))
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
    return redirect(url_for("auth_ui.dashboard"))


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
    return redirect(url_for("auth_ui.dashboard"))


@auth_ui_bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth_ui.login"))


def _applications_with_status(service: ApplicationService, refresh_tokens: RefreshTokenRepository) -> list[dict]:
    rows = []
    for application in service.list_applications():
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
    return render_template("dashboard.html", applications=applications, supported_scopes=SUPPORTED_SCOPES)


@auth_ui_bp.post("/dashboard/applications")
@login_required
def register_application():
    service = _application_service()
    applications = _applications_with_status(service, RefreshTokenRepository(get_session()))
    if not _csrf_valid():
        return render_template(
            "dashboard.html", applications=applications, supported_scopes=SUPPORTED_SCOPES,
            error="Session expired — please try again.",
        ), 400
    name = request.form.get("name", "").strip()
    scopes = request.form.getlist("scopes")
    try:
        raw_secret, application = service.register(name, scopes)
    except DomainError as error:
        return render_template(
            "dashboard.html", applications=applications, supported_scopes=SUPPORTED_SCOPES, error=error.message,
        ), 400
    applications = _applications_with_status(service, RefreshTokenRepository(get_session()))
    return render_template(
        "dashboard.html",
        applications=applications,
        supported_scopes=SUPPORTED_SCOPES,
        new_credential={"name": application.name, "client_id": application.id, "client_secret": raw_secret},
    )


@auth_ui_bp.post("/dashboard/applications/<uuid:application_id>/revoke-token")
@login_required
def revoke_token(application_id: UUID):
    service = _application_service()
    if _csrf_valid():
        service.revoke_application_token(application_id)
    return redirect(url_for("auth_ui.dashboard"))


@auth_ui_bp.post("/dashboard/applications/<uuid:application_id>/delete")
@login_required
def delete_application(application_id: UUID):
    service = _application_service()
    if _csrf_valid():
        service.delete_application(application_id)
    return redirect(url_for("auth_ui.dashboard"))
