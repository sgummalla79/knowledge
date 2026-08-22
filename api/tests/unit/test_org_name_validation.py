import pytest

from api.application.org_name_validation import validate_org_slug
from api.domain.errors import ValidationError


@pytest.mark.parametrize("value", ["acme", "acme-labs", "a1-b2-c3", "a" * 63, "a" * 3])
def test_validate_org_slug_accepts_valid_values(value):
    validate_org_slug(value)  # does not raise


@pytest.mark.parametrize(
    "value",
    [
        "ab",  # too short
        "a" * 64,  # too long
        "Acme",  # uppercase
        "acme labs",  # space
        "acme_labs",  # underscore
        "-acme",  # leading hyphen
        "acme-",  # trailing hyphen
        "acme--labs",  # double hyphen
        "acme!",  # invalid char
    ],
)
def test_validate_org_slug_rejects_invalid_values(value):
    with pytest.raises(ValidationError) as exc_info:
        validate_org_slug(value)
    assert exc_info.value.field == "org_name"


def test_validate_org_slug_rejects_reserved_name():
    with pytest.raises(ValidationError) as exc_info:
        validate_org_slug("admin")
    assert "reserved" in exc_info.value.message
