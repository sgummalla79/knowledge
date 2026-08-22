import re

from api import constants
from api.domain import error_codes
from api.domain.errors import ValidationError

# Deliberately simple syntactic check (local-part@domain, at least one dot after the @) — both
# username and email must look like an email address; neither is verified as a real, deliverable
# one (see domain/entities.py's Identity docstring).
_EMAIL_SHAPE_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email_shape(value: str, *, field: str, error_code: str) -> None:
    if len(value) == 0:
        raise ValidationError(error_code, f"{field.capitalize()} is required.", field=field)
    if len(value) > constants.USERNAME_MAX_LENGTH:
        raise ValidationError(
            error_code,
            f"{field.capitalize()} must be at most {constants.USERNAME_MAX_LENGTH} characters.",
            field=field,
        )
    if not _EMAIL_SHAPE_PATTERN.match(value):
        raise ValidationError(
            error_code,
            f"{field.capitalize()} must be in email address format (e.g. ada@acme.com).",
            field=field,
        )


def validate_username_format(value: str) -> None:
    """Validates a signup/invite's username — raises ValidationError with `field="username"` on
    any violation so the calling form can show it next to the right input."""
    _validate_email_shape(value, field="username", error_code=error_codes.USERNAME_INVALID_FORMAT)


def validate_email_format(value: str) -> None:
    """Validates a signup's email — required, but (unlike username) not unique. Raises
    ValidationError with `field="email"` on any violation."""
    _validate_email_shape(value, field="email", error_code=error_codes.EMAIL_INVALID_FORMAT)
