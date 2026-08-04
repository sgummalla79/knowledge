import base64
import hashlib
import hmac
import secrets

# Not a secret itself — an HMAC domain-separation label, so this derivation can never collide with
# some other deterministic-secret use elsewhere that also happens to key off SECRET_KEY.
_DEFAULT_MCP_CLIENT_SECRET_LABEL = b"knowledge:default-mcp-client"

# Distinct label for the built-in dashboard/workspace Application (see
# DEFAULT_DASHBOARD_APPLICATION_ID) — a different label guarantees this never derives to the same
# value as the MCP client's secret even though both key off the same SECRET_KEY.
_DEFAULT_DASHBOARD_CLIENT_SECRET_LABEL = b"knowledge:default-dashboard-client"


def generate_secret() -> str:
    return secrets.token_urlsafe(32)


def hash_secret(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def derive_default_mcp_client_secret(secret_key: str) -> str:
    """The built-in MCP service-account Application's secret. Deterministic, not random or
    hardcoded: bootstrap.py (storing its hash) and mcp_server/client.py (a separate process,
    needing the raw value to authenticate) each derive this independently from SECRET_KEY — already
    required and unique per deployment — instead of a new value that would need handing off via an
    env var, file, or (worse) a literal constant shared identically across every installation."""
    digest = hmac.new(secret_key.encode(), _DEFAULT_MCP_CLIENT_SECRET_LABEL, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def derive_default_dashboard_client_secret(secret_key: str) -> str:
    """The built-in dashboard/workspace Application's secret — same rationale as
    derive_default_mcp_client_secret, but derived within the same Flask process that also verifies
    it (app/presentation/routes/workspace.py), not handed off to a separate process."""
    digest = hmac.new(secret_key.encode(), _DEFAULT_DASHBOARD_CLIENT_SECRET_LABEL, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
