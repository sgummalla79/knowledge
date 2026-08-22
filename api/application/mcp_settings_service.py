from datetime import datetime, timezone
from uuid import UUID

from api.domain.entities import MCPSettings
from api.domain.ports import MCPSettingsRepositoryPort


class MCPSettingsService:
    """Org-level on/off switches for each of the three MCP tool tiers (api/mcp_server/) — an absent
    row means all three off, the same "no row yet is not an error" convention this app's other
    global/org settings rows use, rather than requiring every org to be seeded with one up front."""

    def __init__(self, mcp_settings: MCPSettingsRepositoryPort):
        self._mcp_settings = mcp_settings

    def get(self, org_id: UUID) -> MCPSettings:
        settings = self._mcp_settings.get(org_id)
        if settings is not None:
            return settings
        return MCPSettings(
            org_id=org_id,
            rag_read_enabled=False,
            object_read_enabled=False,
            object_write_enabled=False,
            last_modified_by=None,
            last_modified_at=datetime.now(timezone.utc),
        )

    def update(
        self,
        org_id: UUID,
        rag_read_enabled: bool,
        object_read_enabled: bool,
        object_write_enabled: bool,
        modified_by: UUID,
    ) -> MCPSettings:
        return self._mcp_settings.upsert(org_id, rag_read_enabled, object_read_enabled, object_write_enabled, modified_by)
