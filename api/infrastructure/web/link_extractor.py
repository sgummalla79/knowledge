from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


def seed_scope_prefix(seed_url: str) -> str:
    """Default crawl scope: the seed URL's directory (its path with the last segment stripped) —
    e.g. '/docs/atlas.en-us.api_asynch.meta/api_asynch/asynch_api_intro.htm' scopes to
    '/docs/atlas.en-us.api_asynch.meta/api_asynch/', which is exactly the directory a doc "book"
    like that lives under. Callers can override this via CrawlRequest.scope_prefix for sites
    organized differently."""
    path = urlsplit(seed_url).path
    return path.rsplit("/", 1)[0] + "/"


def extract_in_scope_links(html: bytes, base_url: str, scope_prefix: str) -> list[str]:
    """Every <a href> resolved against base_url, kept only if it's the same scheme+host as
    base_url (never overridable — a crawl never wanders to a different domain) and its path
    starts with scope_prefix. Fragment-only links to the same page are dropped."""
    base_parts = urlsplit(base_url)
    links: list[str] = []
    seen = set()

    for anchor in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        resolved = urljoin(base_url, anchor["href"])
        parts = urlsplit(resolved)
        normalized = parts._replace(fragment="").geturl()

        if parts.scheme != base_parts.scheme or parts.netloc != base_parts.netloc:
            continue
        if not parts.path.startswith(scope_prefix):
            continue
        if normalized in seen:
            continue

        seen.add(normalized)
        links.append(normalized)

    return links
