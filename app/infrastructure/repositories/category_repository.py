from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.domain import error_codes
from app.domain.entities import Category as CategoryEntity
from app.domain.errors import ConflictError
from app.infrastructure.orm import Category as CategoryModel


def _to_entity(model: CategoryModel) -> CategoryEntity:
    return CategoryEntity(
        id=model.id,
        org_id=model.org_id,
        parent_id=model.parent_id,
        name=model.name,
        slug=model.slug,
        description=model.description,
        created_by=model.created_by,
        last_modified_by=model.last_modified_by,
        created_at=model.created_at,
        last_modified_at=model.last_modified_at,
    )


class CategoryRepository:
    def __init__(self, session):
        self._session = session

    def create(self, org_id: UUID, name: str, slug: str, **fields) -> CategoryEntity:
        model = CategoryModel(org_id=org_id, name=name, slug=slug, **fields)
        self._session.add(model)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError(
                error_codes.CATEGORY_SLUG_TAKEN,
                f"A category with slug '{slug}' already exists in this organization.",
                field="slug",
            )
        return _to_entity(model)

    def get(self, category_id: UUID) -> CategoryEntity | None:
        model = self._session.get(CategoryModel, category_id)
        return _to_entity(model) if model is not None else None

    def update(self, category_id: UUID, name: str, description: str | None) -> CategoryEntity:
        model = self._session.get(CategoryModel, category_id)
        model.name = name
        model.description = description
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError(
                error_codes.CATEGORY_SLUG_TAKEN,
                f"A category named '{name}' already exists in this organization.",
                field="name",
            )
        return _to_entity(model)

    def list_by_org(self, org_id: UUID) -> list[CategoryEntity]:
        models = self._session.query(CategoryModel).filter(CategoryModel.org_id == org_id).all()
        return [_to_entity(model) for model in models]

    def delete(self, category_id: UUID) -> None:
        model = self._session.get(CategoryModel, category_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()

    # Router RAG — the direct successor of what LibraryRepository's equivalent methods did
    # against libraries.description_embedding before categories replaced libraries.

    def set_description_embedding(self, category_id: UUID, embedding: list[float] | None) -> None:
        model = self._session.get(CategoryModel, category_id)
        if model is not None:
            model.description_embedding = embedding
            self._session.flush()

    def list_all_with_description(self, org_id: UUID) -> list[CategoryEntity]:
        models = (
            self._session.query(CategoryModel)
            .filter(CategoryModel.org_id == org_id, CategoryModel.description.isnot(None))
            .all()
        )
        return [_to_entity(model) for model in models]

    def clear_all_description_embeddings(self, org_id: UUID) -> None:
        self._session.query(CategoryModel).filter(CategoryModel.org_id == org_id).update(
            {CategoryModel.description_embedding: None}
        )
        self._session.flush()

    def search_by_description_similarity(
        self, org_id: UUID, query_embedding: list[float], top_n: int, min_similarity: float
    ) -> list[tuple[CategoryEntity, float]]:
        distance = CategoryModel.description_embedding.cosine_distance(query_embedding)
        # Same higher-is-better convention as ChunkRepository.similarity_search — cosine distance
        # is 0 (identical) to 2 (opposite), inverted so router-level scores never mix conventions
        # with ScoredChunk.score.
        similarity = (1 - distance).label("similarity")
        rows = (
            self._session.query(CategoryModel, similarity)
            .filter(CategoryModel.org_id == org_id)
            .filter(CategoryModel.description_embedding.isnot(None))
            .filter(similarity >= min_similarity)
            .order_by(distance)
            .limit(top_n)
            .all()
        )
        return [(_to_entity(model), float(sim)) for model, sim in rows]
