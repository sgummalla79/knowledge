from unittest.mock import MagicMock, patch

import pytest
import requests

from api.constants import DEFAULT_WEB_CRAWL_USER_AGENT
from api.domain import error_codes
from api.domain.errors import ValidationError
from api.infrastructure.web.fetcher import WebPageFetcher


_REAL_CONTENT = b"<html><body>" + b"real content " * 20 + b"</body></html>"


def _response(status_code, content=_REAL_CONTENT, location=None):
    response = MagicMock()
    response.status_code = status_code
    response.is_redirect = status_code in (301, 302, 303, 307, 308)
    response.content = content
    response.headers = {"Location": location} if location else {}
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(
            f"{status_code} Client Error", response=response
        )
    else:
        response.raise_for_status.return_value = None
    return response


def test_default_user_agent_is_the_configured_default():
    fetcher = WebPageFetcher()
    assert fetcher._user_agent == DEFAULT_WEB_CRAWL_USER_AGENT


def test_sends_the_configured_user_agent():
    fetcher = WebPageFetcher(user_agent="custom-agent/1.0")
    with patch("api.infrastructure.web.fetcher.requests.get", return_value=_response(200)) as mock_get:
        fetcher.fetch("https://example.com")

    assert mock_get.call_args.kwargs["headers"]["User-Agent"] == "custom-agent/1.0"


def test_http_error_response_raises_clean_validation_error_not_raw_http_error():
    """Regression test: raise_for_status() used to sit outside the try/except, so an HTTP error
    response (e.g. a 403 from a site blocking automated fetches) propagated as a raw
    requests.HTTPError instead of the same clean ValidationError every other fetch failure gets."""
    fetcher = WebPageFetcher()
    with patch("api.infrastructure.web.fetcher.requests.get", return_value=_response(403)):
        with pytest.raises(ValidationError) as exc_info:
            fetcher.fetch("https://example.com")

    assert exc_info.value.code == error_codes.INVALID_CRAWL_URL


def test_network_error_raises_validation_error():
    fetcher = WebPageFetcher()
    with patch("api.infrastructure.web.fetcher.requests.get", side_effect=requests.ConnectionError("boom")):
        with pytest.raises(ValidationError) as exc_info:
            fetcher.fetch("https://example.com")

    assert exc_info.value.code == error_codes.INVALID_CRAWL_URL


def test_follows_redirect_to_final_url():
    fetcher = WebPageFetcher()
    responses = [
        _response(302, location="https://example.com/final"),
        _response(200, content=b"<html><body>" + b"real content " * 20 + b"</body></html>"),
    ]
    with patch("api.infrastructure.web.fetcher.requests.get", side_effect=responses):
        fetched = fetcher.fetch("https://example.com/start")

    assert fetched.final_url == "https://example.com/final"


def test_js_shell_triggers_playwright_fallback():
    fetcher = WebPageFetcher()
    shell_response = _response(200, content=b"<html><body><div id='root'></div></body></html>")

    mock_page = MagicMock()
    mock_page.content.return_value = "<html><body>rendered content</body></html>"
    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page
    mock_playwright_ctx = MagicMock()
    mock_playwright_ctx.chromium.launch.return_value = mock_browser

    with patch("api.infrastructure.web.fetcher.requests.get", return_value=shell_response):
        with patch("api.infrastructure.web.fetcher.sync_playwright") as mock_sync_playwright:
            mock_sync_playwright.return_value.__enter__.return_value = mock_playwright_ctx
            fetched = fetcher.fetch("https://example.com")

    mock_page.goto.assert_called_once()
    assert fetched.html == b"<html><body>rendered content</body></html>"
