from app.constants import SUPPORTED_SCOPES
from app.domain import error_codes
from app.domain.errors import ValidationError


def validate_scopes_supported(scopes: list[str]) -> None:
    """Shared by ApplicationService (registering an application's allowed scopes) and TokenService
    (validating a client_credentials request's requested scope) so the supported-scope check has
    one home, mirroring validate_provider_connection."""
    for scope in scopes:
        if scope not in SUPPORTED_SCOPES:
            raise ValidationError(error_codes.INVALID_SCOPE, f"Unsupported scope '{scope}'.", field="scope")


def validate_scope_subset(requested: list[str], allowed: list[str]) -> None:
    unsupported = [scope for scope in requested if scope not in allowed]
    if unsupported:
        raise ValidationError(
            error_codes.INVALID_SCOPE,
            f"Scope(s) not allowed for this application: {', '.join(unsupported)}.",
            field="scope",
        )
