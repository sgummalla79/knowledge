from flask import Blueprint, jsonify

from app.auth import require_api_key
from app.constants import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_PROVIDER,
    SUPPORTED_EMBEDDING_MODELS_BY_PROVIDER,
)

options_bp = Blueprint("options", __name__)


@options_bp.get("/embedding-options")
@require_api_key
def get_embedding_options():
    return jsonify(
        {
            "providers": [
                {"name": provider, "models": models}
                for provider, models in SUPPORTED_EMBEDDING_MODELS_BY_PROVIDER.items()
            ],
            "default_provider": DEFAULT_EMBEDDING_PROVIDER,
            "default_model": DEFAULT_EMBEDDING_MODEL,
            "default_chunk_size": DEFAULT_CHUNK_SIZE,
            "default_chunk_overlap": DEFAULT_CHUNK_OVERLAP,
        }
    )
