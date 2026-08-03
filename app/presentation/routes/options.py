from flask import Blueprint, jsonify, request

from app.application.embedding_model_listing_service import EmbeddingModelListingService
from app.application.embedding_provider_settings_service import EmbeddingProviderSettingsService
from app.auth import require_scope
from app.constants import (
    DEFAULT_OLLAMA_BASE_URL,
    EMBEDDING_MODEL_LISTING_RATE_LIMIT,
    EMBEDDING_MODEL_PRESETS,
    EMBEDDING_PROVIDERS_REQUIRING_API_KEY,
    EMBEDDING_PROVIDERS_REQUIRING_BASE_URL,
    EMBEDDING_PROVIDERS_SUPPORTING_BASE_URL,
)
from app.container import get_session
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry
from app.infrastructure.repositories.embedding_provider_settings_repository import (
    EmbeddingProviderSettingsRepository,
)
from app.presentation.schemas import EmbeddingModelListRequest
from app.rate_limit import limiter

options_bp = Blueprint("options", __name__)


@options_bp.get("/embedding-options")
@require_scope()
def get_embedding_options():
    toggles = EmbeddingProviderSettingsService(EmbeddingProviderSettingsRepository(get_session())).list_providers()
    enabled_providers = sorted(toggle.provider for toggle in toggles if toggle.enabled)
    return jsonify(
        {
            # Only enabled providers are listed — a disabled provider is invisible here even
            # though its adapter code still exists (see embedding_provider_settings routes).
            # Any provider here accepts any model name + dimensions the caller supplies — this
            # describes each provider's *connection* requirements, not a closed model list.
            "providers": [
                {
                    "name": provider,
                    "api_key_required": provider in EMBEDDING_PROVIDERS_REQUIRING_API_KEY,
                    "base_url_required": provider in EMBEDDING_PROVIDERS_REQUIRING_BASE_URL,
                    "base_url_supported": provider in EMBEDDING_PROVIDERS_SUPPORTING_BASE_URL,
                    "default_base_url": DEFAULT_OLLAMA_BASE_URL if provider == "ollama" else None,
                    # Tells a UI whether it's worth calling POST /embedding-options/models for
                    # this provider at all, before the user has typed any credentials — Voyage's
                    # SDK has no model-listing endpoint, so it's always false there.
                    "supports_model_listing": EmbeddingProviderRegistry.supports_model_listing(provider),
                }
                for provider in enabled_providers
            ],
            # No provider is bundled/enabled by default anymore (the Ollama sidecar was removed
            # from docker-compose) — there's no single sensible "default" until an admin enables
            # one via the Configuration page, so these are null rather than pointing at a
            # provider that may not even appear in `providers` above.
            "default_provider": None,
            "default_model": None,
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
    /embedding-settings. Gated behind the write scope (not the bare auth embedding-options uses)
    since, unlike that endpoint, this one makes a real outbound call on the caller's behalf using
    whatever base_url/api_key they supply."""
    dto = EmbeddingModelListRequest.model_validate(request.get_json(silent=True) or {})
    service = EmbeddingModelListingService(EmbeddingProviderSettingsRepository(get_session()))
    models = service.list_models(dto.provider, dto.api_key, dto.base_url)
    return jsonify({"models": models})
