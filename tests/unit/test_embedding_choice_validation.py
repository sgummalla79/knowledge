import pytest

from app.application.embedding_choice_validation import validate_embedding_choice
from app.domain import error_codes
from app.domain.errors import ValidationError


def test_ollama_default_choice_is_valid_without_api_key():
    validate_embedding_choice("ollama", "nomic-embed-text", None)


def test_unsupported_provider_rejected():
    with pytest.raises(ValidationError) as exc_info:
        validate_embedding_choice("openai", "text-embedding-3", "key")
    assert exc_info.value.code == error_codes.UNSUPPORTED_EMBEDDING_PROVIDER
    assert exc_info.value.field == "embedding_provider"


def test_dimension_incompatible_model_rejected():
    # voyage-3 is a real (provider, model) with a declared dimension, but is intentionally absent
    # from SUPPORTED_EMBEDDING_MODELS_BY_PROVIDER (1024-dim, incompatible with EMBEDDING_DIM=768) —
    # rejected as an unsupported provider before the dimension check is ever reached.
    with pytest.raises(ValidationError) as exc_info:
        validate_embedding_choice("voyage", "voyage-3", "key")
    assert exc_info.value.field == "embedding_provider"


def test_api_key_required_for_providers_that_declare_it(monkeypatch):
    # Exercises the api-key-required branch directly, since no currently-supported provider
    # requires a key (ollama doesn't; voyage isn't selectable at EMBEDDING_DIM=768) — monkeypatch
    # a hypothetical supported, key-requiring provider so the branch itself is verified.
    monkeypatch.setattr(
        "app.application.embedding_choice_validation.SUPPORTED_EMBEDDING_MODELS_BY_PROVIDER",
        {"hosted": ["hosted-model"]},
    )
    monkeypatch.setattr(
        "app.application.embedding_choice_validation.EMBEDDING_MODEL_DIMENSIONS",
        {("hosted", "hosted-model"): 768},
    )
    monkeypatch.setattr(
        "app.application.embedding_choice_validation.EMBEDDING_PROVIDERS_REQUIRING_API_KEY", {"hosted"}
    )

    with pytest.raises(ValidationError) as exc_info:
        validate_embedding_choice("hosted", "hosted-model", None)
    assert exc_info.value.field == "api_key"

    validate_embedding_choice("hosted", "hosted-model", "a-real-key")
