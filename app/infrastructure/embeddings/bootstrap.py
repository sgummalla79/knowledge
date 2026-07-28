from sqlalchemy.exc import IntegrityError

from app.constants import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_PROVIDER,
    DEFAULT_OLLAMA_BASE_URL,
)
from app.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository


def bootstrap_default_embedding_settings(session) -> None:
    """Idempotent: only seeds a row if none exists yet, so the app works fully locally out of the
    box (Ollama needs no api_key) without requiring a PUT /embedding-settings call first."""
    repository = EmbeddingSettingsRepository(session)
    if repository.get() is not None:
        return
    try:
        repository.upsert(
            DEFAULT_EMBEDDING_PROVIDER,
            DEFAULT_EMBEDDING_MODEL,
            None,
            DEFAULT_CHUNK_SIZE,
            DEFAULT_CHUNK_OVERLAP,
            DEFAULT_OLLAMA_BASE_URL,
        )
        session.commit()
    except IntegrityError:
        session.rollback()
