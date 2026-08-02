from app.infrastructure.auth.redirect_uri import is_registered_redirect_uri, redirect_uri_matches


def test_exact_match():
    assert redirect_uri_matches("http://example.com/cb", "http://example.com/cb") is True


def test_different_path_rejected():
    assert redirect_uri_matches("http://example.com/other", "http://example.com/cb") is False


def test_loopback_ignores_port_difference():
    assert redirect_uri_matches("http://127.0.0.1:54231/callback", "http://127.0.0.1:9999/callback") is True
    assert redirect_uri_matches("http://localhost:1234/callback", "http://localhost:5678/callback") is True


def test_loopback_still_checks_path():
    assert redirect_uri_matches("http://127.0.0.1:54231/other", "http://127.0.0.1:9999/callback") is False


def test_non_loopback_requires_exact_port_match():
    # Port-agnostic matching is a native-app (RFC 8252) concession for loopback redirect URIs only
    # — a non-loopback host must still match exactly, port included.
    assert redirect_uri_matches("http://example.com:8080/cb", "http://example.com:9090/cb") is False


def test_is_registered_redirect_uri_checks_full_list():
    registered = ["http://127.0.0.1:9999/callback", "https://example.com/cb"]
    assert is_registered_redirect_uri("http://127.0.0.1:12345/callback", registered) is True
    assert is_registered_redirect_uri("https://evil.com/cb", registered) is False
