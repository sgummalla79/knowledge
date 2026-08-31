from api.domain.entities import Document as DocumentEntity
from api.infrastructure.orm import Document as DocumentModel
from api.infrastructure.orm import DocumentShelf as DocumentShelfModel

_SORTABLE_COLUMNS = {
    "title": DocumentModel.title,
    "created_at": DocumentModel.created_at,
}


def _to_entity(model: DocumentModel) -> DocumentEntity:
    return DocumentEntity(
        id=model.id,
        org_id=model.org_id,
        source_id=model.source_id,
        category_id=model.category_id,
        owner_id=model.owner_id,
        title=model.title,
        type=model.type,
        file_type=model.file_type,
        content_uri=model.content_uri,
        description=model.description,
        status=model.status,
        error_message=model.error_message,
        size_bytes=model.size_bytes,
        chunk_count=model.chunk_count,
        split_group_id=model.split_group_id,
        split_part=model.split_part,
        split_total=model.split_total,
        created_by=model.created_by,
        last_modified_by=model.last_modified_by,
        created_at=model.created_at,
        last_modified_at=model.last_modified_at,
        indexed_at=model.indexed_at,
        raw_file_path=model.raw_file_path,
    )


def _apply_sort(query, sort: str):
    descending = sort.startswith("-")
    key = sort[1:] if descending else sort
    column = _SORTABLE_COLUMNS.get(key, DocumentModel.created_at)
    return query.order_by(column.desc() if descending else column.asc())


def _apply_filters(query, category_id, shelf_id, document_type=None, title_contains=None):
    if category_id is not None:
        query = query.filter(DocumentModel.category_id == category_id)
    if shelf_id is not None:
        # Documents don't carry shelf_id directly (many-to-many via document_shelves) — scoping to
        # a shelf means joining through the association table, the only place shelf_id lives.
        query = query.join(DocumentShelfModel, DocumentShelfModel.document_id == DocumentModel.id).filter(
            DocumentShelfModel.shelf_id == shelf_id
        )
    if document_type is not None:
        query = query.filter(DocumentModel.type == document_type)
    if title_contains is not None:
        query = query.filter(DocumentModel.title.ilike(f"%{title_contains}%"))
    return query


class DocumentRepository:
    def __init__(self, session):
        self._session = session

    def create(self, **fields) -> DocumentEntity:
        model = DocumentModel(**fields)
        self._session.add(model)
        self._session.flush()
        return _to_entity(model)

    def get(self, document_id) -> DocumentEntity | None:
        model = self._session.get(DocumentModel, document_id)
        return _to_entity(model) if model is not None else None

    def list_by_ids(self, document_ids: list) -> list[DocumentEntity]:
        if not document_ids:
            return []
        models = self._session.query(DocumentModel).filter(DocumentModel.id.in_(document_ids)).all()
        return [_to_entity(model) for model in models]

    def list_for_org(
        self,
        org_id,
        limit: int,
        offset: int,
        sort: str,
        category_id=None,
        shelf_id=None,
        document_type=None,
        title_contains=None,
    ) -> list[DocumentEntity]:
        query = self._session.query(DocumentModel).filter(DocumentModel.org_id == org_id)
        query = _apply_filters(query, category_id, shelf_id, document_type, title_contains)
        query = _apply_sort(query, sort)
        models = query.offset(offset).limit(limit).all()
        return [_to_entity(model) for model in models]

    def count_for_org(self, org_id, category_id=None, shelf_id=None, document_type=None, title_contains=None) -> int:
        query = self._session.query(DocumentModel).filter(DocumentModel.org_id == org_id)
        query = _apply_filters(query, category_id, shelf_id, document_type, title_contains)
        return query.count()

    def update_status(
        self, document_id, status: str, indexed_at=None, error_message=None, chunk_count=None
    ) -> DocumentEntity:
        model = self._session.get(DocumentModel, document_id)
        model.status = status
        if indexed_at is not None:
            model.indexed_at = indexed_at
        model.error_message = error_message
        if chunk_count is not None:
            model.chunk_count = chunk_count
        if status == "indexed":
            # The original file is only ever needed to retry a failed ingestion — once a document
            # is fully indexed, its content lives in `chunks` and the raw upload is dead weight.
            # Nulling the DB column here (not left to callers to remember) keeps this bounded by
            # currently-processing-or-failed documents, not total historical upload volume. The
            # physical file itself is deleted by the caller (IngestionService._process(), which
            # owns storage I/O -- this repository stays DB-only) using the path returned by the
            # entity this update_status() call replaces, before it's gone from here.
            model.raw_file_path = None
        self._session.flush()
        return _to_entity(model)

    def rename(self, document_id, new_title: str) -> DocumentEntity:
        model = self._session.get(DocumentModel, document_id)
        model.title = new_title
        self._session.flush()
        return _to_entity(model)

    def update_metadata(self, document_id, category_id, document_type: str) -> DocumentEntity:
        model = self._session.get(DocumentModel, document_id)
        model.category_id = category_id
        model.type = document_type
        self._session.flush()
        return _to_entity(model)

    def delete(self, document_id) -> None:
        model = self._session.get(DocumentModel, document_id)
        if model is not None:
            # Chunk rows cascade-delete at the DB level (chunks.document_id has ON DELETE CASCADE
            # — see migrations/versions/0001_initial_schema.py) — no explicit chunk cleanup needed.
            self._session.delete(model)
            self._session.flush()
