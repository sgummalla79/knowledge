from app.domain.entities import Document as DocumentEntity
from app.infrastructure.orm import Document as DocumentModel

_SORTABLE_COLUMNS = {
    "source_filename": DocumentModel.source_filename,
    "created_at": DocumentModel.created_at,
}


def _to_entity(model: DocumentModel) -> DocumentEntity:
    return DocumentEntity(
        id=model.id,
        library_id=model.library_id,
        source_filename=model.source_filename,
        file_type=model.file_type,
        status=model.status,
        error_message=model.error_message,
        size_bytes=model.size_bytes,
        chunk_count=model.chunk_count,
        split_group_id=model.split_group_id,
        split_part=model.split_part,
        split_total=model.split_total,
        ingested_at=model.ingested_at,
        created_at=model.created_at,
    )


def _apply_sort(query, sort: str):
    descending = sort.startswith("-")
    key = sort[1:] if descending else sort
    column = _SORTABLE_COLUMNS.get(key, DocumentModel.created_at)
    return query.order_by(column.desc() if descending else column.asc())


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

    def list_for_library(self, library_id, limit: int, offset: int, sort: str) -> list[DocumentEntity]:
        query = self._session.query(DocumentModel).filter(DocumentModel.library_id == library_id)
        query = _apply_sort(query, sort)
        models = query.offset(offset).limit(limit).all()
        return [_to_entity(model) for model in models]

    def count_for_library(self, library_id) -> int:
        return self._session.query(DocumentModel).filter(DocumentModel.library_id == library_id).count()

    def update_status(
        self, document_id, status: str, ingested_at=None, error_message=None, chunk_count=None
    ) -> DocumentEntity:
        model = self._session.get(DocumentModel, document_id)
        model.status = status
        if ingested_at is not None:
            model.ingested_at = ingested_at
        model.error_message = error_message
        if chunk_count is not None:
            model.chunk_count = chunk_count
        if status == "completed":
            # The original file is only ever needed to retry a failed ingestion — once a document
            # is fully ingested, its content lives in `chunks` and the raw upload is dead weight.
            # Reclaiming it here (not left to callers to remember) keeps storage bounded by
            # currently-processing-or-failed documents, not total historical upload volume.
            model.raw_file_bytes = None
        self._session.flush()
        return _to_entity(model)

    def get_raw_bytes(self, document_id) -> bytes | None:
        model = self._session.get(DocumentModel, document_id)
        return model.raw_file_bytes if model is not None else None

    def rename(self, document_id, new_name: str) -> DocumentEntity:
        model = self._session.get(DocumentModel, document_id)
        model.source_filename = new_name
        self._session.flush()
        return _to_entity(model)

    def delete(self, document_id) -> None:
        model = self._session.get(DocumentModel, document_id)
        if model is not None:
            # Chunk rows cascade-delete at the DB level (chunks.document_id has ON DELETE CASCADE
            # — see migrations/versions/0001_initial.py) — no explicit chunk cleanup needed here.
            self._session.delete(model)
            self._session.flush()
