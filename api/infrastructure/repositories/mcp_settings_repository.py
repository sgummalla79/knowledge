from uuid import UUID

from api.domain.entities import MCPSettings as MCPSettingsEntity
from api.infrastructure.orm import MCPSettings as MCPSettingsModel


def _to_entity(model: MCPSettingsModel) -> MCPSettingsEntity:
    return MCPSettingsEntity(
        org_id=model.org_id,
        search_read_enabled=model.search_read_enabled,
        object_read_enabled=model.object_read_enabled,
        object_write_enabled=model.object_write_enabled,
        last_modified_by=model.last_modified_by,
        last_modified_at=model.last_modified_at,
    )


class MCPSettingsRepository:
    def __init__(self, session):
        self._session = session

    def get(self, org_id: UUID) -> MCPSettingsEntity | None:
        model = self._session.get(MCPSettingsModel, org_id)
        return _to_entity(model) if model is not None else None

    def upsert(
        self,
        org_id: UUID,
        search_read_enabled: bool,
        object_read_enabled: bool,
        object_write_enabled: bool,
        modified_by: UUID | None,
    ) -> MCPSettingsEntity:
        model = self._session.get(MCPSettingsModel, org_id)
        if model is None:
            model = MCPSettingsModel(org_id=org_id)
            self._session.add(model)
        model.search_read_enabled = search_read_enabled
        model.object_read_enabled = object_read_enabled
        model.object_write_enabled = object_write_enabled
        model.last_modified_by = modified_by
        self._session.flush()
        return _to_entity(model)
