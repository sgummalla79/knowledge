import re
from urllib.parse import SplitResult, urljoin, urlsplit

from bs4 import BeautifulSoup

# Matches a markdown link's target, e.g. "flow](" in "[Flow of Control](/docs/.../flow.md)" —
# deliberately not markdown-aware beyond that (no image-vs-link distinction, no title-attribute
# handling): the pages this is used against (WebPageFetcher's markdown-twin fetches) are generated
# docs output, not hand-written markdown with unusual link forms.
_MARKDOWN_LINK_RE = re.compile(r"\]\(([^)\s]+)\)")


def _in_scope_url(resolved: str, base_parts: SplitResult, scope_prefix: str) -> str | None:
    """Shared by extract_in_scope_links and extract_in_scope_markdown_links: same scheme+host as
    base_parts (never overridable — a crawl never wanders to a different domain), path starting
    with scope_prefix, fragment stripped. Returns None if resolved is out of scope."""
    parts = urlsplit(resolved)
    if parts.scheme != base_parts.scheme or parts.netloc != base_parts.netloc:
        return None
    if not parts.path.startswith(scope_prefix):
        return None
    return parts._replace(fragment="").geturl()


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
        normalized = _in_scope_url(resolved, base_parts, scope_prefix)
        if normalized is None or normalized in seen:
            continue

        seen.add(normalized)
        links.append(normalized)

    return links


def extract_in_scope_markdown_links(markdown: bytes, base_url: str, scope_prefix: str) -> list[str]:
    """Same scoping rules as extract_in_scope_links, for the markdown-twin pages WebPageFetcher
    fetches when a site publishes one (see fetcher.py's _MARKDOWN_CONTENT_TYPE_HINT) — those pages
    link to siblings as plain markdown "[text](url)", not <a href> tags, so they need their own
    (much simpler) regex-based extraction rather than an HTML parser."""
    base_parts = urlsplit(base_url)
    text = markdown.decode("utf-8", errors="replace")
    links: list[str] = []
    seen = set()

    for match in _MARKDOWN_LINK_RE.finditer(text):
        resolved = urljoin(base_url, match.group(1))
        normalized = _in_scope_url(resolved, base_parts, scope_prefix)
        if normalized is None or normalized in seen:
            continue

        seen.add(normalized)
        links.append(normalized)

    return links
