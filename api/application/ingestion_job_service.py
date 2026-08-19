from uuid import UUID

from api.domain.entities import IngestionJob
from api.domain.ports import IngestionJobRepositoryPort


class IngestionJobService:
    def __init__(self, repository: IngestionJobRepositoryPort):
        self._repository = repository

    def list_jobs(self, org_id: UUID, limit: int, offset: int) -> list[IngestionJob]:
        return self._repository.list_by_org(org_id, limit, offset)
