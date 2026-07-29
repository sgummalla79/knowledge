import pytest

from app.application.embedding_choice_validation import validate_embedding_choice
from app.domain import error_codes
from app.domain.errors import ValidationError

_ALL_ENABLED = {"voyage", "ollama", "openai_compatible"}


def test_ollama_default_choice_is_valid_without_api_key():
    validate_embedding_choice("ollama", "nomic-embed-text", None, "http://ollama:11434", 768, _ALL_ENABLED)


def test_any_model_name_and_dimensions_accepted_for_a_known_provider():
    # This is the whole point of "bring your own model" — no whitelist on model/dimensions.
    validate_embedding_choice(
        "ollama", "some-other-ollama-model", None, "http://ollama:11434", 1234, _ALL_ENABLED
    )


def test_unsupported_provider_rejected():
    with pytest.raises(ValidationError) as exc_info:
        validate_embedding_choice("made-up-provider", "text-embedding-3", "key", None, 1536, _ALL_ENABLED)
    assert exc_info.value.code == error_codes.UNSUPPORTED_EMBEDDING_PROVIDER
    assert exc_info.value.field == "embedding_provider"


def test_voyage_now_reachable_with_any_model_and_dimensions():
    # Previously blocked as "unsupported" purely because voyage-3 is 1024-dim and the deployment
    # was pinned to EMBEDDING_DIM=768 — dimensions are now caller-supplied, so this is valid.
    validate_embedding_choice("voyage", "voyage-3", "key", None, 1024, _ALL_ENABLED)


def test_api_key_required_for_providers_that_declare_it():
    with pytest.raises(ValidationError) as exc_info:
        validate_embedding_choice("voyage", "voyage-3", None, None, 1024, _ALL_ENABLED)
    assert exc_info.value.field == "api_key"


def test_base_url_required_for_providers_that_declare_it():
    with pytest.raises(ValidationError) as exc_info:
        validate_embedding_choice(
            "openai_compatible", "text-embedding-3-small", "key", None, 1536, _ALL_ENABLED
        )
    assert exc_info.value.field == "base_url"


def test_openai_compatible_valid_with_base_url_and_key():
    validate_embedding_choice(
        "openai_compatible", "text-embedding-3-small", "key", "https://api.openai.com/v1", 1536, _ALL_ENABLED
    )


def test_disabled_provider_rejected_even_though_it_is_a_known_provider():
    # A known, structurally-valid provider — but an admin has switched it off independently of
    # the others (see EmbeddingProviderSettingsService), so it's still rejected here.
    with pytest.raises(ValidationError) as exc_info:
        validate_embedding_choice("ollama", "nomic-embed-text", None, "http://ollama:11434", 768, {"voyage"})
    assert exc_info.value.code == error_codes.EMBEDDING_PROVIDER_DISABLED
    assert exc_info.value.field == "embedding_provider"


def test_unsupported_provider_checked_before_disabled_status():
    # An unknown provider should be reported as unsupported, not disabled, even if it's also
    # absent from enabled_providers.
    with pytest.raises(ValidationError) as exc_info:
        validate_embedding_choice("made-up-provider", "model", "key", None, 768, set())
    assert exc_info.value.code == error_codes.UNSUPPORTED_EMBEDDING_PROVIDER
