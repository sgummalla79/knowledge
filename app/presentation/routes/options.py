from flask import Blueprint, jsonify

from app.application.embedding_provider_settings_service import EmbeddingProviderSettingsService
from app.auth import require_scope
from app.constants import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_PROVIDER,
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_RERANK_MODEL,
    DEFAULT_RERANK_PROVIDER,
    EMBEDDING_MODEL_PRESETS,
    EMBEDDING_PROVIDERS_REQUIRING_API_KEY,
    EMBEDDING_PROVIDERS_REQUIRING_BASE_URL,
    EMBEDDING_PROVIDERS_SUPPORTING_BASE_URL,
    SUPPORTED_RERANK_MODELS_BY_PROVIDER,
)
from app.container import get_session
from app.infrastructure.repositories.embedding_provider_settings_repository import (
    EmbeddingProviderSettingsRepository,
)

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
                }
                for provider in enabled_providers
            ],
            "default_provider": DEFAULT_EMBEDDING_PROVIDER,
            "default_model": DEFAULT_EMBEDDING_MODEL,
            # Convenience suggestions only, never validated/enforced — see app/constants.py.
            "suggested_models": EMBEDDING_MODEL_PRESETS,
        }
    )


@options_bp.get("/rerank-options")
@require_scope()
def get_rerank_options():
    return jsonify(
        {
            "providers": [
                {"name": provider, "models": models}
                for provider, models in SUPPORTED_RERANK_MODELS_BY_PROVIDER.items()
            ],
            "default_provider": DEFAULT_RERANK_PROVIDER,
            "default_model": DEFAULT_RERANK_MODEL,
        }
    )
