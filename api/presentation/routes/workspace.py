from flask import Blueprint, g, redirect, url_for

from api.container import get_session
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.presentation.routes.auth_ui import login_required
from api.presentation.web.spa import serve_spa_shell

workspace_bp = Blueprint("workspace", __name__)


def _serve_spa_page():
    """Shared by every top-level SPA entry point reachable once logged in (/workspace, /settings)
    — same must_change_password gate and username injection, just a different mount path each.
    Runs behind @login_required, which already resolved g.user_id — re-fetching by that id (not
    IdentityRepository.get()'s "first row in the table" shim) is what makes this actually reflect
    the logged-in identity once more than one exists."""
    identity = IdentityRepository(get_session()).get_by_id(g.user_id)
    if identity is not None and identity.must_change_password:
        return redirect(url_for("auth_ui.change_password"))
    return serve_spa_shell(extra_globals={"USERNAME": identity.email if identity is not None else ""})


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
