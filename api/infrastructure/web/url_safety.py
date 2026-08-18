import ipaddress
import socket
from urllib.parse import urlsplit

from api.domain import error_codes
from api.domain.errors import ValidationError

_ALLOWED_SCHEMES = {"http", "https"}


def assert_public_url(url: str) -> None:
    """Raises ValidationError unless `url` is safe for the server to fetch on a caller's behalf:
    http(s) only, and every IP its hostname resolves to is a public, routable address. Must be
    called again on every redirect hop and every discovered crawl link, not just the URL a caller
    originally supplied — an SSRF guard checked once on the original URL is trivially bypassed by
    a redirect or a same-site link pointing at an internal address."""
    parts = urlsplit(url)
    if parts.scheme not in _ALLOWED_SCHEMES or not parts.hostname:
        raise ValidationError(
            error_codes.INVALID_CRAWL_URL, f"'{url}' is not a valid http(s) URL.", field="url"
        )

    try:
        resolved = socket.getaddrinfo(parts.hostname, None)
    except socket.gaierror as error:
        raise ValidationError(
            error_codes.INVALID_CRAWL_URL, f"Could not resolve host for '{url}'.", field="url"
        ) from error

    for family, _, _, _, sockaddr in resolved:
        address = ipaddress.ip_address(sockaddr[0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
        ):
            raise ValidationError(
                error_codes.INVALID_CRAWL_URL,
                f"'{url}' resolves to a non-public address and cannot be fetched.",
                field="url",
            )
