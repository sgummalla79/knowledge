from app.constants import EMBEDDING_PROVIDER_DISPLAY_NAMES
from app.domain.entities import EmbeddingProviderConfig
from app.infrastructure.orm import EmbeddingModel
from app.infrastructure.repositories.default_org import get_default_org_id


def _to_entity(model: EmbeddingModel) -> EmbeddingProviderConfig:
    return EmbeddingProviderConfig(
        id=model.id,
        provider=model.provider,
        enabled=model.is_default,
        model=model.model_identifier,
        api_key=model.api_key,
        base_url=model.endpoint_url,
        dimensions=model.dimensions,
        chunk_size=model.chunk_size,
        chunk_overlap=model.chunk_overlap,
        created_at=model.created_at,
        updated_at=model.last_modified_at,
    )


class EmbeddingProviderSettingsRepository:
    """Backed by embedding_models (see migration 0019) instead of the old one-row-per-known-
    provider embedding_provider_settings table — a row here only exists once a provider has
    actually been configured via upsert_config(), unlike the old table's always-present
    placeholder rows (EmbeddingProviderConfigService already treats "no row for this provider" as
    a valid state, so nothing is lost). `enabled` on the returned entity is `is_default`; this
    repository keeps `is_default` and `status` moving in lockstep (see EmbeddingModel's docstring)
    since nothing yet needs them to diverge.

    Still scoped to a single implicit organization (get_default_org_id) — real per-request org
    resolution is a later phase of the multi-tenant migration, not this one.
    """

    def __init__(self, session):
        self._session = session

    def list(self) -> list[EmbeddingProviderConfig]:
        org_id = get_default_org_id(self._session)
        rows = (
            self._session.query(EmbeddingModel)
            .filter(EmbeddingModel.org_id == org_id)
            .order_by(EmbeddingModel.provider)
            .all()
        )
        return [_to_entity(row) for row in rows]

    def get(self, provider: str) -> EmbeddingProviderConfig | None:
        org_id = get_default_org_id(self._session)
        row = (
            self._session.query(EmbeddingModel)
            .filter(EmbeddingModel.org_id == org_id, EmbeddingModel.provider == provider)
            .first()
        )
        return _to_entity(row) if row is not None else None

    def upsert_config(
        self,
        provider: str,
        model: str,
        api_key: str | None,
        base_url: str | None,
        dimensions: int,
        chunk_size: int,
        chunk_overlap: int,
    ) -> EmbeddingProviderConfig:
        org_id = get_default_org_id(self._session)
        existing = (
            self._session.query(EmbeddingModel)
            .filter(EmbeddingModel.org_id == org_id, EmbeddingModel.provider == provider)
            .first()
        )
        if existing is None:
            existing = EmbeddingModel(
                org_id=org_id,
                provider=provider,
                name=EMBEDDING_PROVIDER_DISPLAY_NAMES.get(provider, provider),
                is_default=False,
                status="disabled",
            )
            self._session.add(existing)
        existing.model_identifier = model
        existing.api_key = api_key
        existing.endpoint_url = base_url
        existing.dimensions = dimensions
        existing.chunk_size = chunk_size
        existing.chunk_overlap = chunk_overlap
        self._session.flush()
        return _to_entity(existing)

    def set_enabled(self, provider: str, enabled: bool) -> EmbeddingProviderConfig:
        # Only ever called (by EmbeddingProviderConfigService) for a provider that already has a
        # configured row — enable() requires config.model/.dimensions to be set first, and
        # disable() only reaches here after confirming config.enabled is already true.
        org_id = get_default_org_id(self._session)
        existing = (
            self._session.query(EmbeddingModel)
            .filter(EmbeddingModel.org_id == org_id, EmbeddingModel.provider == provider)
            .one()
        )
        existing.is_default = enabled
        existing.status = "active" if enabled else "disabled"
        self._session.flush()
        return _to_entity(existing)
