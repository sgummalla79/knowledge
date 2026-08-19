from flask import Blueprint, current_app, g, redirect, send_from_directory, url_for

from api.container import get_session
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.presentation.routes.auth_ui import login_required
from api.presentation.web.spa import serve_spa_shell

# Serves the SPA shell for every logged-in page (/, /browse, /item/<id>, /org/settings, ...) — the
# new nav is a single top bar, not the old two-sidebar /workspace + /settings split, so one
# catch-all replaces those two narrower mounts (see the old workspace.py, now removed).
app_shell_bp = Blueprint("app_shell", __name__)


@app_shell_bp.get("/favicon.ico")
def favicon():
    # Without this, a browser's automatic favicon request falls through to the /<path:subpath>
    # catch-all below, which is @login_required — that redirects it to /sign-in?next=/favicon.ico,
    # and sign_in() stashes that next value in the session, later hijacking the real post-login/
    # post-signup redirect target. Registering this first keeps favicon requests off that path
    # entirely (a static route always wins over the dynamic one below, regardless of order).
    return send_from_directory(current_app.static_folder, "brand-icon.png")


@app_shell_bp.get("/")
@app_shell_bp.get("/<path:subpath>")
@login_required
def app_shell(subpath: str | None = None):
    identity = IdentityRepository(get_session()).get_by_id(g.user_id)
    if identity is not None and identity.must_change_password:
        return redirect(url_for("auth_ui.change_password"))
    organization = OrganizationRepository(get_session()).get(g.org_id) if g.org_id is not None else None
    return serve_spa_shell(
        extra_globals={
            "USERNAME": identity.email if identity is not None else "",
            "ORG_ID": str(g.org_id) if g.org_id is not None else None,
            "ORG_NAME": organization.name if organization is not None else None,
            "ROLE": g.role,
        }
    )
