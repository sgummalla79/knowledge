from urllib.parse import urlsplit

# RFC 8252 §7.3 (OAuth for native apps): loopback redirect URIs commonly use a different ephemeral
# port on every run (the client binds an OS-assigned local port for its callback listener), so an
# authorization server must not require an exact port match for them.
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "[::1]"}


def is_loopback_host(hostname: str | None) -> bool:
    return hostname in _LOOPBACK_HOSTS


def redirect_uri_matches(candidate: str, registered: str) -> bool:
    if candidate == registered:
        return True

    candidate_parts = urlsplit(candidate)
    registered_parts = urlsplit(registered)
    if not is_loopback_host(candidate_parts.hostname):
        return False

    return (
        candidate_parts.scheme == registered_parts.scheme
        and candidate_parts.hostname == registered_parts.hostname
        and candidate_parts.path == registered_parts.path
    )


def is_registered_redirect_uri(candidate: str, registered_uris: list[str]) -> bool:
    return any(redirect_uri_matches(candidate, registered) for registered in registered_uris)
