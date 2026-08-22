import pytest

from api.application.username_validation import validate_email_format, validate_username_format
from api.domain.errors import ValidationError

_INVALID_EMAIL_SHAPED_VALUES = [
    "",
    "not-an-email",
    "ada@acme",  # no dot after @
    "@acme.com",  # empty local part
    "ada acme.com",  # no @
    "ada@ac me.com",  # space in domain
    "a" * 255 + "@acme.com",  # too long
]


@pytest.mark.parametrize("value", ["ada@acme.com", "a@b.co", "ada.lovelace+test@sub.acme.com"])
def test_validate_username_format_accepts_valid_values(value):
    validate_username_format(value)  # does not raise


@pytest.mark.parametrize("value", _INVALID_EMAIL_SHAPED_VALUES)
def test_validate_username_format_rejects_invalid_values(value):
    with pytest.raises(ValidationError) as exc_info:
        validate_username_format(value)
    assert exc_info.value.field == "username"


@pytest.mark.parametrize("value", ["ada@acme.com", "a@b.co", "ada.lovelace+test@sub.acme.com"])
def test_validate_email_format_accepts_valid_values(value):
    validate_email_format(value)  # does not raise


@pytest.mark.parametrize("value", _INVALID_EMAIL_SHAPED_VALUES)
def test_validate_email_format_rejects_invalid_values(value):
    with pytest.raises(ValidationError) as exc_info:
        validate_email_format(value)
    assert exc_info.value.field == "email"
