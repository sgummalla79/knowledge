from datetime import datetime, timezone
from uuid import UUID

from flask import session

from api.application.session_settings_service import SessionSettingsService
from api.container import get_session
from api.domain.errors import AuthenticationError
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.session_settings_repository import SessionSettingsRepository

# Shared by require_org_session (api/presentation/routes/auth_ui.py) and require_permission's
# session-cookie branch (api/presentation/routes/app_auth.py) — before this module existed, both
# independently duplicated the session.get("identity_id")/session.get("active_org_id") read, which
# meant an inactivity check added to only one of them would leave the other unprotected.


def resolve_cookie_session() -> tuple[UUID, UUID] | None:
    """Resolves (identity_id, org_id) from the session cookie, enforcing the caller's org's
    configured inactivity timeout (session_settings.inactivity_timeout_minutes, default
    SESSION_TIMEOUT_DEFAULT_MINUTES) — even though the signed cookie itself hasn't
    cryptographically expired, a session idle longer than that gets rejected.

    Returns None if there's no session at all — the caller decides what that means
    (require_org_session: 401; require_permission: fall through to trying a bearer token instead).
    Raises AuthenticationError (and clears the session) if a session exists but has gone stale.

    A last_active_at of None (an identity that's never been touched — including a nonexistent
    identity_id, e.g. a test's faked session with no real DB row behind it) always skips the
    staleness check: a genuinely first-ever authenticated request has nothing to compare against,
    and a bogus identity_id already gets implicitly rejected downstream by
    PermissionService.resolve_permissions finding no membership — this function doesn't need to
    validate the identity actually exists itself."""
    raw_identity_id = session.get("identity_id")
    raw_org_id = session.get("active_org_id")
    if not raw_identity_id or not raw_org_id:
        return None

    identity_id = UUID(raw_identity_id)
    org_id = UUID(raw_org_id)

    db_session = get_session()
    identities = IdentityRepository(db_session)

    last_active_at = identities.get_last_active_at(identity_id)
    if last_active_at is not None:
        timeout_minutes = SessionSettingsService(SessionSettingsRepository(db_session)).get(org_id).inactivity_timeout_minutes
        elapsed_seconds = (datetime.now(timezone.utc) - last_active_at).total_seconds()
        if elapsed_seconds > timeout_minutes * 60:
            session.clear()
            raise AuthenticationError("Session expired due to inactivity — please sign in again.")

    identities.touch_last_active(identity_id)
    return identity_id, org_id
