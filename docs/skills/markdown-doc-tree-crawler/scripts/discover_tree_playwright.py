#!/usr/bin/env python3
"""Builds a hierarchical page tree by reading the site's REAL sidebar DOM via a headless browser,
instead of inferring structure from in-body markdown links (see build_doc_tree.py for that
approach — kept as a separate script since it has no Playwright dependency and works fine on
sites without this shadow-DOM navigation quirk).

Why this exists: on sites like developer.salesforce.com, the left-nav is a Shadow DOM component
that only renders the children of whichever section the *currently loaded page* belongs to — other
sections stay collapsed. A page's in-body prose links (e.g. a "See Also" or "What to Do Next"
section) are NOT a reliable proxy for its true children: they mix real structural next-steps with
generic cross-references to unrelated topics, and there's no textual marker that reliably
distinguishes the two (confirmed empirically — a first attempt using body links produced a badly
tangled tree where one chapter absorbed most of the book via transitive "See Also" chains).

The sidebar itself doesn't have that ambiguity: visiting a page only ever auto-expands that page's
own section. So this script visits each page once, reads its rendered sidebar (piercing shadow
roots), and treats whatever links are newly visible (not already claimed by an earlier page) as
that page's children, in the order they appear. The full top-level chapter list is also read this
way, from the seed page's sidebar — no manual WebFetch step needed first.

Usage:
    python3 discover_tree_playwright.py <seed-url> --scope-prefix /docs/foo/guide/ \\
        --output tree.json

Dependencies (not stdlib): `pip install playwright && playwright install chromium`.
"""

import argparse
import json
import sys
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

_SIDEBAR_LINKS_JS = """
(scopePrefix) => {
    function walk(root, out, seen) {
        for (const el of root.children) {
            if (el.shadowRoot) {
                walk(el.shadowRoot, out, seen);
            } else if (el.children.length) {
                walk(el, out, seen);
            }
            if (el.tagName === 'A' && el.href) {
                let url;
                try { url = new URL(el.href); } catch (e) { continue; }
                if (!url.pathname.startsWith(scopePrefix)) continue;
                if (url.hash && url.pathname === window.location.pathname) continue;
                if (url.href.endsWith('#')) continue;
                const normalized = url.origin + url.pathname;
                const text = el.textContent.trim();
                if (!seen.has(normalized) || text.length > (seen.get(normalized).text || '').length) {
                    seen.set(normalized, {href: normalized, text});
                }
                if (!out.includes(normalized)) out.push(normalized);
            }
        }
    }
    const out = [];
    const seen = new Map();
    walk(document.body, out, seen);
    return out.map(href => seen.get(href));
}
"""


def _fetch_sidebar_links(page, url, scope_prefix, timeout):
    page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
    page.wait_for_timeout(800)
    return page.evaluate(_SIDEBAR_LINKS_JS, scope_prefix)


def discover(seed_url, scope_prefix, max_pages, timeout, headless=True):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        baseline = _fetch_sidebar_links(page, seed_url, scope_prefix, timeout)
        if not baseline:
            print(
                f"No in-scope sidebar links found on {seed_url} — check --scope-prefix matches "
                f"the site's actual path structure.",
                file=sys.stderr,
            )
            sys.exit(1)

        claimed = {}
        roots = []
        for entry in baseline:
            node = {"title": entry["text"], "url": entry["href"], "children": []}
            claimed[entry["href"]] = node
            roots.append(node)

        seed_normalized = urlsplit(seed_url)._replace(fragment="").geturl()
        frontier = deque(n for n in roots if n["url"] != seed_normalized)
        visited_seed_already = seed_normalized in claimed

        total = len(claimed)
        while frontier and total < max_pages:
            node = frontier.popleft()
            print(f"[{total}] visiting {node['url']}", file=sys.stderr)
            links = _fetch_sidebar_links(page, node["url"], scope_prefix, timeout)
            for entry in links:
                href = entry["href"]
                if href in claimed or total >= max_pages:
                    continue
                child = {"title": entry["text"], "url": href, "children": []}
                claimed[href] = child
                node["children"].append(child)
                frontier.append(child)
                total += 1

        if not visited_seed_already:
            pass  # seed's own children (if it's not a leaf) were already captured in `baseline`.

        browser.close()

    return roots


def count_nodes(roots):
    total = 0
    stack = list(roots)
    while stack:
        node = stack.pop()
        total += 1
        stack.extend(node["children"])
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("seed_url", help="Any page URL within the doc tree")
    parser.add_argument("--scope-prefix", required=True, help="Path prefix all pages must stay under")
    parser.add_argument("--output", required=True, help="Where to write the resulting tree.json")
    parser.add_argument("--max-pages", type=int, default=300)
    parser.add_argument("--timeout", type=float, default=30, help="Per-page navigation timeout, seconds")
    parser.add_argument("--headed", action="store_true", help="Show the browser window (debugging)")
    args = parser.parse_args()

    roots = discover(args.seed_url, args.scope_prefix, args.max_pages, args.timeout, headless=not args.headed)

    Path(args.output).write_text(json.dumps(roots, indent=2))

    print(f"chapters: {len(roots)}")
    print(f"total pages: {count_nodes(roots)}")
    print(f"tree written to {args.output}")


if __name__ == "__main__":
    main()
