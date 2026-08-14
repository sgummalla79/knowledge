from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.domain import error_codes
from app.domain.entities import Library as LibraryEntity
from app.domain.errors import ConflictError
from app.infrastructure.orm import Library as LibraryModel

_SORTABLE_COLUMNS = {
    "name": LibraryModel.name,
    "created_at": LibraryModel.created_at,
}


def _to_entity(model: LibraryModel) -> LibraryEntity:
    return LibraryEntity(
        id=model.id,
        name=model.name,
        description=model.description,
        document_count=model.document_count,
        chunk_count=model.chunk_count,
        last_ingested_at=model.last_ingested_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _apply_sort(query, sort: str):
    descending = sort.startswith("-")
    key = sort[1:] if descending else sort
    column = _SORTABLE_COLUMNS.get(key, LibraryModel.created_at)
    return query.order_by(column.desc() if descending else column.asc())


class LibraryRepository:
    def __init__(self, session):
        self._session = session

    def create(self, **fields) -> LibraryEntity:
        model = LibraryModel(**fields)
        self._session.add(model)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError(
                error_codes.LIBRARY_NAME_TAKEN,
                f"A library named '{fields.get('name')}' already exists.",
                field="name",
            )
        return _to_entity(model)

    def get(self, library_id) -> LibraryEntity | None:
        model = self._session.get(LibraryModel, library_id)
        return _to_entity(model) if model is not None else None

    def update(self, library_id, name: str, description: str | None) -> LibraryEntity:
        model = self._session.get(LibraryModel, library_id)
        model.name = name
        model.description = description
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError(
                error_codes.LIBRARY_NAME_TAKEN,
                f"A library named '{name}' already exists.",
                field="name",
            )
        return _to_entity(model)

    def list(self, limit: int, offset: int, sort: str) -> list[LibraryEntity]:
        query = _apply_sort(self._session.query(LibraryModel), sort)
        models = query.offset(offset).limit(limit).all()
        return [_to_entity(model) for model in models]

    def count(self) -> int:
        return self._session.query(LibraryModel).count()

    def delete(self, library_id) -> None:
        model = self._session.get(LibraryModel, library_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()

    def increment_counts(self, library_id, document_delta: int, chunk_delta: int) -> None:
        model = self._session.get(LibraryModel, library_id)
        model.document_count += document_delta
        model.chunk_count += chunk_delta
        self._session.flush()

    def set_description_embedding(self, library_id, embedding: list[float] | None) -> None:
        model = self._session.get(LibraryModel, library_id)
        if model is not None:
            model.description_embedding = embedding
            self._session.flush()

    def list_all_with_description(self) -> list[LibraryEntity]:
        models = self._session.query(LibraryModel).filter(LibraryModel.description.isnot(None)).all()
        return [_to_entity(model) for model in models]

    def clear_all_description_embeddings(self) -> None:
        self._session.query(LibraryModel).update({LibraryModel.description_embedding: None})
        self._session.flush()

    def search_by_description_similarity(
        self, query_embedding: list[float], top_n: int, min_similarity: float
    ) -> list[tuple[LibraryEntity, float]]:
        distance = LibraryModel.description_embedding.cosine_distance(query_embedding)
        # Same higher-is-better convention as ChunkRepository.similarity_search — cosine distance
        # is 0 (identical) to 2 (opposite), inverted so router-level scores never mix conventions
        # with ScoredChunk.score.
        similarity = (1 - distance).label("similarity")
        rows = (
            self._session.query(LibraryModel, similarity)
            .filter(LibraryModel.description_embedding.isnot(None))
            .filter(similarity >= min_similarity)
            .order_by(distance)
            .limit(top_n)
            .all()
        )
        return [(_to_entity(model), float(sim)) for model, sim in rows]
