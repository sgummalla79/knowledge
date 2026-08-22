import pytest

from api.application.embedding_choice_validation import validate_provider_connection
from api.domain import error_codes
from api.domain.errors import ValidationError


def test_ollama_default_choice_is_valid_without_api_key():
    validate_provider_connection("ollama", None, "http://ollama:11434")


def test_any_model_name_and_dimensions_accepted_for_a_known_provider():
    # This is the whole point of "bring your own model" — no whitelist on model/dimensions
    # (dimensions/model aren't even parameters here; validate_provider_connection only checks
    # connection requirements).
    validate_provider_connection("ollama", None, "http://ollama:11434")


def test_unsupported_provider_rejected():
    with pytest.raises(ValidationError) as exc_info:
        validate_provider_connection("made-up-provider", "key", None)
    assert exc_info.value.code == error_codes.UNSUPPORTED_EMBEDDING_PROVIDER
    assert exc_info.value.field == "embedding_provider"


def test_voyage_reachable_with_any_api_key():
    # Previously blocked as "unsupported" purely because voyage-3 is 1024-dim and the deployment
    # was pinned to EMBEDDING_DIM=768 — dimensions are now caller-supplied, so this is valid.
    validate_provider_connection("voyage", "key", None)


def test_api_key_required_for_providers_that_declare_it():
    with pytest.raises(ValidationError) as exc_info:
        validate_provider_connection("voyage", None, None)
    assert exc_info.value.field == "api_key"


def test_base_url_required_for_providers_that_declare_it():
    with pytest.raises(ValidationError) as exc_info:
        validate_provider_connection("openai_compatible", "key", None)
    assert exc_info.value.field == "base_url"


def test_openai_compatible_valid_with_base_url_and_key():
    validate_provider_connection("openai_compatible", "key", "https://api.openai.com/v1")
