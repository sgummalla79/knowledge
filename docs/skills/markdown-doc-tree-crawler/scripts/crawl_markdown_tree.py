#!/usr/bin/env python3
"""Discovers every page in a documentation site's "tree" by following the plain-markdown link
graph, starting from one seed URL — no headless browser, no JS execution.

Why this works: many modern doc platforms (Docusaurus, Nextra, Mintlify, and bespoke setups like
Salesforce's Developer Docs) publish a markdown twin of every HTML page at the same path, with
".html"/".htm" replaced by ".md" (or ".md" appended, if the page has no extension). That twin
contains real "[text](url)" links to sibling pages via a plain static GET. This sidesteps sites
whose real navigation/content lives in Shadow DOM web components, which defeats both a plain
<a href> scrape and a headless-browser page.content() dump (neither pierces shadow roots).

Usage:
    python3 crawl_markdown_tree.py <seed-url> [--scope-prefix /docs/foo/] [--max-pages 300]
                                    [--delay 0.3] [--user-agent "..."] [--timeout 20]
"""

import argparse
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from urllib.parse import urljoin, urlsplit

# Confirmed empirically against a real Akamai-fronted target (developer.salesforce.com): a UA that
# visibly identifies this as automated (e.g. "...DocCrawler/1.0") gets 403'd — but so, counter-
# intuitively, does a UA that claims to be a real desktop browser without the TLS/JS fingerprint to
# back it up (looks like a "fake browser", which some bot-detection treats as more suspicious than
# an honest simple client). The boring default `requests` library sends is what actually gets
# through consistently; override with --user-agent if a specific site still blocks it.
DEFAULT_USER_AGENT = "python-requests/2.32.3"
DEFAULT_MAX_PAGES = 300
DEFAULT_DELAY_SECONDS = 0.3
DEFAULT_TIMEOUT_SECONDS = 20

_MARKDOWN_LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
_MARKDOWN_CONTENT_TYPE_HINT = "markdown"


def _ssl_context() -> ssl.SSLContext:
    """Some Python installs (notably python.org's macOS installer) ship a bare `ssl` module that
    doesn't trust any CA by default, even though the `certifi` package — which supplies one — is
    separately installed; urllib doesn't wire the two together on its own. Use certifi's bundle
    when available so this script works out of the box on that install; fall back to whatever the
    platform default already trusts otherwise."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def markdown_variant_url(url: str) -> str:
    """Same convention observed empirically across several doc sites: swap a trailing .html/.htm
    for .md, or append .md if the path has no extension. URLs already ending in .md are returned
    unchanged (nothing to guess)."""
    if url.endswith(".md"):
        return url
    parts = urlsplit(url)
    path = parts.path
    for ext in (".html", ".htm"):
        if path.endswith(ext):
            path = path[: -len(ext)]
            break
    return parts._replace(path=path + ".md").geturl()


def seed_scope_prefix(seed_url: str) -> str:
    """Default crawl scope: the seed URL's directory (path with the last segment stripped) — the
    same default a real crawler would use. Override with --scope-prefix for sites organized
    differently (e.g. sibling guide/ and references/ directories that should both be in scope)."""
    path = urlsplit(seed_url).path
    return path.rsplit("/", 1)[0] + "/"


def _get(url: str, user_agent: str, timeout: float, retries: int = 1):
    """Returns (status_code, content_type, body_bytes) or None on failure. Retries once on a 5xx —
    doc sites behind Akamai/CDN bot-detection layers have been observed to 503 transiently, then
    succeed moments later, even on an unmodified retry."""
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    attempts = retries + 1
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=_ssl_context()) as response:
                return response.status, response.headers.get("Content-Type", ""), response.read()
        except urllib.error.HTTPError as error:
            if error.code >= 500 and attempt < attempts - 1:
                time.sleep(1.0)
                continue
            return error.code, error.headers.get("Content-Type", "") if error.headers else "", b""
        except urllib.error.URLError:
            if attempt < attempts - 1:
                time.sleep(1.0)
                continue
            return None
    return None


def fetch_markdown(url: str, user_agent: str, timeout: float):
    """Tries the URL as-is if it already ends in .md, otherwise probes the guessed .md twin.
    Returns markdown text on success, or None (page not found / no markdown twin available —
    these are NOT distinguished, since either way there's nothing further to crawl from here)."""
    candidate = markdown_variant_url(url)
    result = _get(candidate, user_agent, timeout)
    if result is None:
        return None
    status, content_type, body = result
    if status != 200 or _MARKDOWN_CONTENT_TYPE_HINT not in content_type.lower():
        return None
    return body.decode("utf-8", errors="replace")


def in_scope_links(markdown_text: str, base_url: str, scope_prefix: str):
    base_parts = urlsplit(base_url)
    links = []
    seen = set()
    for match in _MARKDOWN_LINK_RE.finditer(markdown_text):
        resolved = urljoin(base_url, match.group(1))
        parts = urlsplit(resolved)
        if parts.scheme != base_parts.scheme or parts.netloc != base_parts.netloc:
            continue
        if not parts.path.startswith(scope_prefix):
            continue
        normalized = parts._replace(fragment="").geturl()
        if normalized in seen:
            continue
        seen.add(normalized)
        links.append(normalized)
    return links


def crawl(seed_url: str, scope_prefix: str, max_pages: int, delay: float, user_agent: str, timeout: float):
    visited = set()
    failed = {}
    frontier = deque([seed_url])

    while frontier and len(visited) < max_pages:
        url = frontier.popleft()
        if url in visited:
            continue
        visited.add(url)

        markdown_text = fetch_markdown(url, user_agent, timeout)
        if markdown_text is None:
            failed[url] = "no markdown twin found (not a 200 + markdown Content-Type response)"
            continue

        if len(visited) < max_pages:
            for link in in_scope_links(markdown_text, url, scope_prefix):
                if link not in visited and link not in frontier:
                    frontier.append(link)

        if frontier and len(visited) < max_pages:
            time.sleep(delay)

    succeeded = sorted(u for u in visited if u not in failed)
    return succeeded, failed


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("seed_url", help="Any page URL within the doc tree to crawl")
    parser.add_argument(
        "--scope-prefix",
        default=None,
        help="Path prefix pages must stay under (default: the seed URL's own directory)",
    )
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS, help="Seconds between fetches")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()

    scope_prefix = args.scope_prefix or seed_scope_prefix(args.seed_url)
    succeeded, failed = crawl(
        args.seed_url, scope_prefix, args.max_pages, args.delay, args.user_agent, args.timeout
    )

    if not succeeded and args.seed_url in failed:
        print(f"No markdown twin found for {args.seed_url} — try a different seed URL one level "
              f"into the doc tree (this is common for a site's top-level landing page even when "
              f"every article page has a .md twin).", file=sys.stderr)
        sys.exit(1)

    print(f"scope_prefix: {scope_prefix}")
    print(f"pages found: {len(succeeded)}")
    if failed:
        print(f"pages skipped (fetch failed): {len(failed)}", file=sys.stderr)
        for url, reason in sorted(failed.items()):
            print(f"  {url}: {reason}", file=sys.stderr)
    print()
    for url in succeeded:
        print(url)


if __name__ == "__main__":
    main()
