from app.infrastructure.auth.secrets import derive_default_dashboard_client_secret, derive_default_mcp_client_secret


def test_deterministic_for_the_same_secret_key():
    first = derive_default_dashboard_client_secret("some-secret-key")
    second = derive_default_dashboard_client_secret("some-secret-key")
    assert first == second


def test_varies_with_secret_key():
    first = derive_default_dashboard_client_secret("secret-key-one")
    second = derive_default_dashboard_client_secret("secret-key-two")
    assert first != second


def test_urlsafe_and_unpadded():
    secret = derive_default_dashboard_client_secret("some-secret-key")
    assert "=" not in secret
    assert "+" not in secret
    assert "/" not in secret


def test_differs_from_the_mcp_client_secret():
    # Distinct HMAC label (see app/infrastructure/auth/secrets.py) — same SECRET_KEY must not
    # produce the same secret for both built-in service-account Applications.
    assert derive_default_dashboard_client_secret("some-secret-key") != derive_default_mcp_client_secret(
        "some-secret-key"
    )
