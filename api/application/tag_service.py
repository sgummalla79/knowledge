from uuid import UUID

from api.domain import error_codes
from api.domain.entities import Tag
from api.domain.errors import NotFoundError
from api.domain.ports import TagRepositoryPort


class TagService:
    def __init__(self, repository: TagRepositoryPort):
        self._repository = repository

    def create_tag(self, org_id: UUID, name: str) -> Tag:
        return self._repository.create(org_id, name=name)

    def list_tags(self, org_id: UUID) -> list[Tag]:
        return self._repository.list_by_org(org_id)

    def tag_document(self, org_id: UUID, document_id: UUID, tag_id: UUID) -> None:
        self._get_org_tag(org_id, tag_id)
        self._repository.tag_document(document_id, tag_id)

    def untag_document(self, org_id: UUID, document_id: UUID, tag_id: UUID) -> None:
        self._get_org_tag(org_id, tag_id)
        self._repository.untag_document(document_id, tag_id)

    def list_document_tags(self, document_id: UUID) -> list[Tag]:
        return self._repository.list_for_document(document_id)

    def _get_org_tag(self, org_id: UUID, tag_id: UUID) -> Tag:
        tag = self._repository.get(tag_id)
        if tag is None or tag.org_id != org_id:
            raise NotFoundError(error_codes.TAG_NOT_FOUND, "Tag not found.")
        return tag
