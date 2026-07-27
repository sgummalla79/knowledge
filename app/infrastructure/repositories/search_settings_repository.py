from app.domain.entities import SearchSettings as SearchSettingsEntity
from app.infrastructure.orm import SearchSettings as SearchSettingsModel


def _to_entity(model: SearchSettingsModel) -> SearchSettingsEntity:
    return SearchSettingsEntity(
        rerank_enabled=model.rerank_enabled,
        rerank_provider=model.rerank_provider,
        rerank_model=model.rerank_model,
        dense_k=model.dense_k,
        sparse_k=model.sparse_k,
        rerank_candidates=model.rerank_candidates,
        rrf_k=model.rrf_k,
        updated_at=model.updated_at,
    )


class SearchSettingsRepository:
    """Single global row — application-level singleton (mirrors EmbeddingSettingsRepository).

    Unlike embedding settings, an absent row is not an error state: SearchSettingsService fills
    in defaults when get() returns None, so callers always have usable values.
    """

    def __init__(self, session):
        self._session = session

    def get(self) -> SearchSettingsEntity | None:
        model = self._session.query(SearchSettingsModel).first()
        return _to_entity(model) if model is not None else None

    def upsert(
        self,
        rerank_enabled: bool,
        rerank_provider: str,
        rerank_model: str,
        dense_k: int,
        sparse_k: int,
        rerank_candidates: int,
        rrf_k: int,
    ) -> SearchSettingsEntity:
        existing = self._session.query(SearchSettingsModel).first()
        if existing is None:
            existing = SearchSettingsModel(
                rerank_enabled=rerank_enabled,
                rerank_provider=rerank_provider,
                rerank_model=rerank_model,
                dense_k=dense_k,
                sparse_k=sparse_k,
                rerank_candidates=rerank_candidates,
                rrf_k=rrf_k,
            )
            self._session.add(existing)
        else:
            existing.rerank_enabled = rerank_enabled
            existing.rerank_provider = rerank_provider
            existing.rerank_model = rerank_model
            existing.dense_k = dense_k
            existing.sparse_k = sparse_k
            existing.rerank_candidates = rerank_candidates
            existing.rrf_k = rrf_k
        self._session.flush()
        return _to_entity(existing)
