import logging
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from api.constants import (
    DEFAULT_WEB_CRAWL_USER_AGENT,
    WEB_CRAWL_JS_SHELL_TEXT_THRESHOLD_CHARS,
    WEB_CRAWL_RENDER_TIMEOUT_SECONDS,
    WEB_CRAWL_REQUEST_TIMEOUT_SECONDS,
)
from api.domain import error_codes
from api.domain.errors import ValidationError
from api.infrastructure.web.url_safety import assert_public_url

logger = logging.getLogger(__name__)

_MAX_REDIRECTS = 5

# Many modern doc sites (Docusaurus/Nextra/Mintlify-style, and Salesforce's developer docs) publish
# a plain-markdown twin of every HTML page at the same path with ".md" in place of ".html"/".htm"
# (or appended, if the page has no extension) — a static fetch of that twin gives clean content and
# a real link graph to sibling pages, without ever needing the headless-render fallback below.
# Checked first, best-effort: confirmed only via a real 200 with a markdown Content-Type, so a site
# with no such twin (or one that soft-404s to an HTML error page) just falls through to the normal
# path below at the cost of one harmless extra request.
_MARKDOWN_CONTENT_TYPE_HINT = "markdown"


@dataclass(frozen=True)
class FetchedPage:
    content: bytes
    final_url: str
    is_markdown: bool = False


class WebPageFetcher:
    """Fetches a page's content, preferring a markdown twin (see _MARKDOWN_CONTENT_TYPE_HINT above)
    over the real HTML, and among the two possible HTML paths, static first, falling back to a
    headless browser only when the static result looks like an unrendered JS shell (e.g.
    help.salesforce.com-style SPAs) — see _looks_like_js_shell. Every URL, including every redirect
    hop, is SSRF-checked before any request is made.

    user_agent defaults to DEFAULT_WEB_CRAWL_USER_AGENT but is expected to be supplied by the
    caller from WebCrawlSettingsService — some sites (e.g. developer.salesforce.com) block a UA
    that honestly identifies this as an automated tool, and an admin needs to be able to adjust
    it per-deployment without a code change."""

    def __init__(self, user_agent: str = DEFAULT_WEB_CRAWL_USER_AGENT):
        self._user_agent = user_agent

    def fetch(self, url: str) -> FetchedPage:
        if url.endswith(".md"):
            content, final_url = self._fetch_static(url)
            return FetchedPage(content=content, final_url=final_url, is_markdown=True)

        markdown_page = self._fetch_markdown_variant(url)
        if markdown_page is not None:
            return markdown_page

        html, final_url = self._fetch_static(url)
        if self._looks_like_js_shell(html):
            logger.info("Static fetch looks like a JS shell, rendering instead", extra={"url": final_url})
            html = self._fetch_rendered(final_url)
        return FetchedPage(content=html, final_url=final_url, is_markdown=False)

    def _markdown_variant_url(self, url: str) -> str:
        parts = urlsplit(url)
        path = parts.path
        for ext in (".html", ".htm"):
            if path.endswith(ext):
                path = path[: -len(ext)]
                break
        return parts._replace(path=path + ".md").geturl()

    def _fetch_markdown_variant(self, url: str) -> FetchedPage | None:
        candidate = self._markdown_variant_url(url)
        assert_public_url(candidate)
        try:
            response = requests.get(
                candidate,
                headers={"User-Agent": self._user_agent},
                timeout=WEB_CRAWL_REQUEST_TIMEOUT_SECONDS,
                allow_redirects=False,
            )
        except requests.RequestException:
            return None

        content_type = response.headers.get("Content-Type", "")
        if response.status_code != 200 or _MARKDOWN_CONTENT_TYPE_HINT not in content_type.lower():
            return None
        return FetchedPage(content=response.content, final_url=url, is_markdown=True)

    def _fetch_static(self, url: str) -> tuple[bytes, str]:
        current_url = url
        for _ in range(_MAX_REDIRECTS + 1):
            assert_public_url(current_url)
            try:
                response = requests.get(
                    current_url,
                    headers={"User-Agent": self._user_agent},
                    timeout=WEB_CRAWL_REQUEST_TIMEOUT_SECONDS,
                    allow_redirects=False,
                )
                if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    if not location:
                        break
                    current_url = urljoin(current_url, location)
                    continue
                # Inside the same try as the request itself (not after it) — an HTTP error
                # response (e.g. a 403 from a site blocking automated fetches) is a
                # requests.RequestException subclass too, and should surface as the same clean
                # ValidationError as a network-level failure, not an unwrapped requests exception.
                response.raise_for_status()
                return response.content, current_url
            except requests.RequestException as error:
                raise ValidationError(
                    error_codes.INVALID_CRAWL_URL, f"Failed to fetch '{current_url}': {error}", field="url"
                ) from error

        raise ValidationError(
            error_codes.INVALID_CRAWL_URL, f"Too many redirects fetching '{url}'.", field="url"
        )

    def _looks_like_js_shell(self, html: bytes) -> bool:
        text = BeautifulSoup(html, "html.parser").get_text(strip=True)
        return len(text) < WEB_CRAWL_JS_SHELL_TEXT_THRESHOLD_CHARS

    def _fetch_rendered(self, url: str) -> bytes:
        assert_public_url(url)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    page = browser.new_page()
                    page.goto(url, timeout=WEB_CRAWL_RENDER_TIMEOUT_SECONDS * 1000, wait_until="networkidle")
                    return page.content().encode("utf-8")
                finally:
                    browser.close()
        except Exception as error:
            raise ValidationError(
                error_codes.INVALID_CRAWL_URL, f"Failed to render '{url}': {error}", field="url"
            ) from error
