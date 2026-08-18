from unittest.mock import MagicMock
from uuid import uuid4

from app.application.web_crawl_service import WebCrawlService
from app.infrastructure.web.fetcher import FetchedPage


def _ids():
    return uuid4(), uuid4()  # org_id, owner_id


def _fake_fetcher(pages_by_url: dict[str, tuple[bytes, list[str]]]):
    """pages_by_url maps url -> (html_bytes, [in-scope links found in that html]).
    The fake link_extractor patch below reads the second element directly instead of really
    parsing HTML, keeping this test focused on BFS/crawl behavior, not link parsing (already
    covered by test_link_extractor.py)."""
    fetcher = MagicMock()

    def fetch(url):
        html, _ = pages_by_url[url]
        return FetchedPage(html=html, final_url=url)

    fetcher.fetch.side_effect = fetch
    return fetcher


def test_max_pages_one_never_calls_link_extractor(monkeypatch):
    ingestion_service = MagicMock()
    ingestion_service.ingest_html.return_value = MagicMock(id=uuid4())
    fetcher = _fake_fetcher({"https://example.com/a": (b"<html></html>", [])})

    extractor = MagicMock()
    monkeypatch.setattr("app.application.web_crawl_service.extract_in_scope_links", extractor)

    service = WebCrawlService(ingestion_service, fetcher)
    org_id, owner_id = _ids()
    service.crawl(org_id, owner_id, "https://example.com/a", max_pages=1)

    extractor.assert_not_called()
    ingestion_service.ingest_html.assert_called_once()


def test_crawl_follows_in_scope_links_up_to_max_pages(monkeypatch):
    ingestion_service = MagicMock()
    ingestion_service.ingest_html.side_effect = (
        lambda org_id, owner_id, url, html, category_id=None: MagicMock(id=uuid4())
    )

    pages = {
        "https://example.com/a": b"<html>a</html>",
        "https://example.com/b": b"<html>b</html>",
        "https://example.com/c": b"<html>c</html>",
    }
    links_by_url = {
        "https://example.com/a": ["https://example.com/b", "https://example.com/c"],
        "https://example.com/b": [],
        "https://example.com/c": [],
    }
    fetcher = MagicMock()
    fetcher.fetch.side_effect = lambda url: FetchedPage(html=pages[url], final_url=url)

    monkeypatch.setattr(
        "app.application.web_crawl_service.extract_in_scope_links",
        lambda html, base_url, scope_prefix: links_by_url[base_url],
    )

    service = WebCrawlService(ingestion_service, fetcher)
    org_id, owner_id = _ids()
    results = []
    service.crawl(
        org_id,
        owner_id,
        "https://example.com/a",
        max_pages=2,
        on_page_result=lambda url, doc, err: results.append((url, doc, err)),
    )

    # BFS visits the seed, then only ONE of its two discovered links before hitting max_pages=2.
    assert len(results) == 2
    assert results[0][0] == "https://example.com/a"
    assert results[1][0] == "https://example.com/b"
    assert ingestion_service.ingest_html.call_count == 2


def test_one_failed_page_does_not_abort_the_crawl(monkeypatch):
    ingestion_service = MagicMock()

    def ingest_html(org_id, owner_id, url, html, category_id=None):
        if url == "https://example.com/b":
            raise RuntimeError("embedding failed")
        return MagicMock(id=uuid4())

    ingestion_service.ingest_html.side_effect = ingest_html

    pages = {
        "https://example.com/a": b"<html>a</html>",
        "https://example.com/b": b"<html>b</html>",
    }
    fetcher = MagicMock()
    fetcher.fetch.side_effect = lambda url: FetchedPage(html=pages[url], final_url=url)

    monkeypatch.setattr(
        "app.application.web_crawl_service.extract_in_scope_links",
        lambda html, base_url, scope_prefix: (
            ["https://example.com/b"] if base_url == "https://example.com/a" else []
        ),
    )

    service = WebCrawlService(ingestion_service, fetcher)
    org_id, owner_id = _ids()
    results = []
    service.crawl(
        org_id,
        owner_id,
        "https://example.com/a",
        max_pages=2,
        on_page_result=lambda url, doc, err: results.append((url, doc, err)),
    )

    assert len(results) == 2
    _, doc_a, err_a = results[0]
    _, doc_b, err_b = results[1]
    assert doc_a is not None and err_a is None
    assert doc_b is None and isinstance(err_b, RuntimeError)


def test_seed_url_is_ssrf_checked_before_crawling():
    import pytest

    from app.domain.errors import ValidationError

    ingestion_service = MagicMock()
    service = WebCrawlService(ingestion_service, MagicMock())

    org_id, owner_id = _ids()
    with pytest.raises(ValidationError):
        service.crawl(org_id, owner_id, "https://127.0.0.1/admin", max_pages=1)
    ingestion_service.ingest_html.assert_not_called()
