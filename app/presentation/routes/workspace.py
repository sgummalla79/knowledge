from flask import Blueprint, g, redirect, url_for

from app.container import get_session
from app.infrastructure.repositories.user_repository import UserRepository
from app.presentation.routes.auth_ui import login_required
from app.presentation.web.spa import serve_spa_shell

workspace_bp = Blueprint("workspace", __name__)


def _serve_spa_page():
    """Shared by every top-level SPA entry point reachable once logged in (/workspace, /settings)
    — same must_change_password gate and username injection, just a different mount path each.
    Runs behind @login_required, which already resolved g.user_id — re-fetching by that id (not
    UserRepository.get()'s "first row in the table" shim) is what makes this actually reflect the
    logged-in user once more than one exists."""
    user = UserRepository(get_session()).get_by_id(g.user_id)
    if user is not None and user.must_change_password:
        return redirect(url_for("auth_ui.change_password"))
    return serve_spa_shell(extra_globals={"USERNAME": user.email if user is not None else ""})


@workspace_bp.get("/workspace")
@workspace_bp.get("/workspace/<path:subpath>")
@login_required
def workspace(subpath: str | None = None):
    return _serve_spa_page()


@workspace_bp.get("/settings")
@workspace_bp.get("/settings/<path:subpath>")
@login_required
def settings(subpath: str | None = None):
    return _serve_spa_page()
