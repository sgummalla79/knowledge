from flask import Blueprint, jsonify, request

from app.application.embedding_model_listing_service import EmbeddingModelListingService
from app.application.embedding_provider_settings_service import EmbeddingProviderConfigService
from app.auth import require_scope
from app.constants import (
    DEFAULT_OLLAMA_BASE_URL,
    EMBEDDING_MODEL_LISTING_RATE_LIMIT,
    EMBEDDING_MODEL_PRESETS,
    EMBEDDING_PROVIDER_DISPLAY_NAMES,
    EMBEDDING_PROVIDERS_REQUIRING_API_KEY,
    EMBEDDING_PROVIDERS_REQUIRING_BASE_URL,
    EMBEDDING_PROVIDERS_SUPPORTING_BASE_URL,
)
from app.container import get_session
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.embedding_provider_settings_repository import (
    EmbeddingProviderSettingsRepository,
)
from app.infrastructure.repositories.library_repository import LibraryRepository
from app.presentation.schemas import EmbeddingModelListRequest
from app.rate_limit import limiter

options_bp = Blueprint("options", __name__)


def _embedding_provider_config_service() -> EmbeddingProviderConfigService:
    session = get_session()
    return EmbeddingProviderConfigService(
        EmbeddingProviderSettingsRepository(session), ChunkRepository(session), LibraryRepository(session)
    )


@options_bp.get("/embedding-options")
@require_scope()
def get_embedding_options():
    statuses = _embedding_provider_config_service().list_status()
    active = next((status for status in statuses if status.enabled), None)
    return jsonify(
        {
            # Every known provider is listed regardless of configuration/enabled state — there's
            # no more "selectable in a dropdown" toggle gating this; a UI is expected to render a
            # fixed page per provider. Any provider here accepts any model name + dimensions the
            # caller supplies — this describes each provider's *connection* requirements, not a
            # closed model list.
            "providers": [
                {
                    "name": status.provider,
                    # Single source of truth is app/constants.py, so a new provider needs an entry
                    # there once, not a duplicate mapping kept in sync in the SPA too.
                    "display_name": EMBEDDING_PROVIDER_DISPLAY_NAMES.get(status.provider, status.provider),
                    "enabled": status.enabled,
                    "configured": status.configured,
                    # True once this provider has chunks embedded with it — an enabled+locked
                    # provider can't be disabled (or reconfigured) until every chunk is deleted,
                    # since embeddings from different models aren't comparable. Surfaced here so a
                    # UI can grey out its own enable/disable toggle instead of only finding out
                    # after a rejected request.
                    "locked": status.locked,
                    "api_key_required": status.provider in EMBEDDING_PROVIDERS_REQUIRING_API_KEY,
                    "base_url_required": status.provider in EMBEDDING_PROVIDERS_REQUIRING_BASE_URL,
                    "base_url_supported": status.provider in EMBEDDING_PROVIDERS_SUPPORTING_BASE_URL,
                    "default_base_url": DEFAULT_OLLAMA_BASE_URL if status.provider == "ollama" else None,
                    # Tells a UI whether it's worth calling POST /embedding-options/models for
                    # this provider at all, before the user has typed any credentials — Voyage's
                    # SDK has no model-listing endpoint, so it's always false there.
                    "supports_model_listing": EmbeddingProviderRegistry.supports_model_listing(status.provider),
                }
                for status in statuses
            ],
            "default_provider": active.provider if active else None,
            "default_model": active.model if active else None,
            # Convenience suggestions only, never validated/enforced — see app/constants.py.
            "suggested_models": EMBEDDING_MODEL_PRESETS,
        }
    )


@options_bp.post("/embedding-options/models")
@require_scope("embedding_settings:write")
@limiter.limit(EMBEDDING_MODEL_LISTING_RATE_LIMIT)
def list_embedding_models():
    """Lists a provider's live model catalog using credentials the caller just typed (not yet
    saved) — lets a UI populate a model dropdown before the user commits to PUT
    /embedding-settings/<provider>. Gated behind the write scope (not the bare auth
    embedding-options uses) since, unlike that endpoint, this one makes a real outbound call on
    the caller's behalf using whatever base_url/api_key they supply."""
    dto = EmbeddingModelListRequest.model_validate(request.get_json(silent=True) or {})
    models = EmbeddingModelListingService().list_models(dto.provider, dto.api_key, dto.base_url)
    return jsonify({"models": models})
