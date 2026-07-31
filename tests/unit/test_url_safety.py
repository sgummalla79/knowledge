from unittest.mock import patch

import pytest

from app.domain import error_codes
from app.domain.errors import ValidationError
from app.infrastructure.web.url_safety import assert_public_url


def _addrinfo(ip: str):
    return [(None, None, None, None, (ip, 0))]


def test_rejects_non_http_scheme():
    with pytest.raises(ValidationError) as exc_info:
        assert_public_url("ftp://example.com/file")
    assert exc_info.value.code == error_codes.INVALID_CRAWL_URL


def test_rejects_url_with_no_hostname():
    with pytest.raises(ValidationError):
        assert_public_url("https:///path")


def test_allows_public_ip():
    with patch("app.infrastructure.web.url_safety.socket.getaddrinfo", return_value=_addrinfo("93.184.216.34")):
        assert_public_url("https://example.com")


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",  # loopback
        "10.0.0.5",  # private
        "192.168.1.1",  # private
        "169.254.169.254",  # link-local / cloud metadata
        "224.0.0.1",  # multicast
    ],
)
def test_rejects_non_public_ip(ip):
    with patch("app.infrastructure.web.url_safety.socket.getaddrinfo", return_value=_addrinfo(ip)):
        with pytest.raises(ValidationError) as exc_info:
            assert_public_url("https://internal.example.com")
        assert exc_info.value.code == error_codes.INVALID_CRAWL_URL


def test_rejects_unresolvable_host():
    import socket

    with patch("app.infrastructure.web.url_safety.socket.getaddrinfo", side_effect=socket.gaierror("nope")):
        with pytest.raises(ValidationError):
            assert_public_url("https://does-not-resolve.invalid")
