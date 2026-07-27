from flask import Blueprint, jsonify

from app.auth import require_scope
from app.constants import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_PROVIDER,
    DEFAULT_RERANK_MODEL,
    DEFAULT_RERANK_PROVIDER,
    EMBEDDING_DIM,
    SUPPORTED_EMBEDDING_MODELS_BY_PROVIDER,
    SUPPORTED_RERANK_MODELS_BY_PROVIDER,
)

options_bp = Blueprint("options", __name__)


@options_bp.get("/embedding-options")
@require_scope()
def get_embedding_options():
    return jsonify(
        {
            "providers": [
                {"name": provider, "models": models}
                for provider, models in SUPPORTED_EMBEDDING_MODELS_BY_PROVIDER.items()
            ],
            "default_provider": DEFAULT_EMBEDDING_PROVIDER,
            "default_model": DEFAULT_EMBEDDING_MODEL,
            # Fixed by pgvector's table-creation-time column dimension (see app/constants.py) —
            # exposed so clients can show a real "Dimensions" value instead of hardcoding one.
            "dimensions": EMBEDDING_DIM,
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
