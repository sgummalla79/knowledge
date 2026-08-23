from datetime import datetime, timezone
from uuid import UUID

from api.constants import SESSION_TIMEOUT_DEFAULT_MINUTES
from api.domain.entities import SessionSettings
from api.domain.ports import SessionSettingsRepositoryPort


class SessionSettingsService:
    """Org-level browser-session inactivity timeout — an absent row means the default
    (SESSION_TIMEOUT_DEFAULT_MINUTES), the same "no row yet is not an error" convention this app's
    other global/org settings rows use, rather than requiring every org to be seeded with one up
    front."""

    def __init__(self, session_settings: SessionSettingsRepositoryPort):
        self._session_settings = session_settings

    def get(self, org_id: UUID) -> SessionSettings:
        settings = self._session_settings.get(org_id)
        if settings is not None:
            return settings
        return SessionSettings(
            org_id=org_id,
            inactivity_timeout_minutes=SESSION_TIMEOUT_DEFAULT_MINUTES,
            last_modified_by=None,
            last_modified_at=datetime.now(timezone.utc),
        )

    def update(self, org_id: UUID, inactivity_timeout_minutes: int, modified_by: UUID) -> SessionSettings:
        return self._session_settings.upsert(org_id, inactivity_timeout_minutes, modified_by)
