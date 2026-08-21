import re

from api import constants
from api.domain import error_codes
from api.domain.errors import ValidationError

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def validate_org_slug(value: str) -> None:
    """Validates a self-serve signup's org name, which doubles as its URL-safe slug (see
    SignupService.signup and GET /check-org-name) — raises ValidationError with `field="org_name"`
    on any violation so the signup form can show it next to the right input."""
    if not (constants.ORG_SLUG_MIN_LENGTH <= len(value) <= constants.ORG_SLUG_MAX_LENGTH):
        raise ValidationError(
            error_codes.ORGANIZATION_NAME_INVALID,
            f"Org name must be between {constants.ORG_SLUG_MIN_LENGTH} and "
            f"{constants.ORG_SLUG_MAX_LENGTH} characters.",
            field="org_name",
        )
    if not _SLUG_PATTERN.match(value):
        raise ValidationError(
            error_codes.ORGANIZATION_NAME_INVALID,
            "Org name can only contain lowercase letters, numbers, and single hyphens, and "
            "can't start or end with a hyphen.",
            field="org_name",
        )
    if value in constants.RESERVED_ORG_SLUGS:
        raise ValidationError(
            error_codes.ORGANIZATION_NAME_INVALID,
            f"'{value}' is reserved and can't be used as an org name.",
            field="org_name",
        )
