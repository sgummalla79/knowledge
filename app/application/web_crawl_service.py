import logging
import time
from collections import deque
from typing import Callable
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests

from app.application.ingestion_service import IngestionService
from app.constants import WEB_CRAWL_PAGE_DELAY_SECONDS, WEB_CRAWL_REQUEST_TIMEOUT_SECONDS
from app.domain.entities import Document, Library
from app.infrastructure.web.fetcher import WebPageFetcher
from app.infrastructure.web.link_extractor import extract_in_scope_links, seed_scope_prefix
from app.infrastructure.web.url_safety import assert_public_url

logger = logging.getLogger(__name__)

_ROBOTS_USER_AGENT = "knowledge-api-web-ingestion"

OnPageResult = Callable[[str, Document | None, Exception | None], None]


class _RobotsCache:
    """Fetches robots.txt at most once per origin per crawl — a crawl typically stays on one
    host, and re-fetching it before every single page would be wasteful and impolite in its own
    right. A missing or unfetchable robots.txt defaults to "allow" (standard convention)."""

    def __init__(self):
        self._parsers: dict[str, RobotFileParser] = {}

    def allows(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        parser = self._parsers.get(origin)
        if parser is None:
            parser = RobotFileParser()
            robots_url = urljoin(origin, "/robots.txt")
            try:
                assert_public_url(robots_url)
                response = requests.get(robots_url, timeout=WEB_CRAWL_REQUEST_TIMEOUT_SECONDS)
                parser.parse(response.text.splitlines() if response.status_code < 400 else [])
            except Exception:
                parser.parse([])
            self._parsers[origin] = parser
        return parser.can_fetch(_ROBOTS_USER_AGENT, url)


class WebCrawlService:
    """Breadth-first crawl from a seed URL, ingesting each in-scope page through
    IngestionService.ingest_html exactly like a normal upload. max_pages=1 (the default)
    degenerates to "just ingest this one page" — the same code path as a real crawl, not a
    special case: link extraction is simply never reached once the page cap is hit."""

    def __init__(self, ingestion_service: IngestionService, fetcher: WebPageFetcher | None = None):
        self._ingestion_service = ingestion_service
        self._fetcher = fetcher or WebPageFetcher()

    def crawl(
        self,
        library: Library,
        seed_url: str,
        max_pages: int,
        scope_prefix: str | None = None,
        on_page_result: OnPageResult | None = None,
    ) -> None:
        assert_public_url(seed_url)
        scope_prefix = scope_prefix or seed_scope_prefix(seed_url)
        robots = _RobotsCache()

        visited: set[str] = set()
        frontier: deque[str] = deque([seed_url])

        while frontier and len(visited) < max_pages:
            url = frontier.popleft()
            if url in visited:
                continue
            visited.add(url)

            if not robots.allows(url):
                logger.info("Skipping URL disallowed by robots.txt", extra={"url": url})
                continue

            try:
                fetched = self._fetcher.fetch(url)
                document = self._ingestion_service.ingest_html(library, fetched.final_url, fetched.html)
                if on_page_result:
                    on_page_result(url, document, None)

                if len(visited) < max_pages:
                    for link in extract_in_scope_links(fetched.html, fetched.final_url, scope_prefix):
                        if link not in visited and link not in frontier:
                            frontier.append(link)
            except Exception as error:
                logger.warning("Failed to ingest crawled page", extra={"url": url, "error": str(error)})
                if on_page_result:
                    on_page_result(url, None, error)

            if frontier and len(visited) < max_pages:
                time.sleep(WEB_CRAWL_PAGE_DELAY_SECONDS)
