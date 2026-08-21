from urllib.parse import urlsplit

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def redirect_uri_matches(registered: str, candidate: str) -> bool:
    """Exact match, except loopback hosts get their port ignored (RFC 8252 §7.3) — a locally-run
    CLI/MCP client's callback listener binds a different ephemeral port every run, so pinning an
    exact port at registration time would break it on every restart."""
    if registered == candidate:
        return True

    registered_parts = urlsplit(registered)
    candidate_parts = urlsplit(candidate)
    if registered_parts.hostname not in _LOOPBACK_HOSTS or candidate_parts.hostname not in _LOOPBACK_HOSTS:
        return False

    return (
        registered_parts.scheme == candidate_parts.scheme
        and registered_parts.hostname == candidate_parts.hostname
        and registered_parts.path == candidate_parts.path
        and registered_parts.query == candidate_parts.query
    )
