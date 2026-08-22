#!/usr/bin/env python3
"""Builds a hierarchical page tree for a doc site, for feeding into render_pdf.py.

The site's real sidebar (chapter list, in order) lives in Shadow DOM and can't be scraped
statically — that part still requires a one-time manual/LLM step (e.g. WebFetch on the seed page,
asking for the left-nav links in order) whose output becomes this script's --top-level-file input.

What this script automates is the *rest* of the tree: for each top-level chapter, it BFS-crawls
that chapter's own markdown-twin link graph (same mechanism as crawl_markdown_tree.py) and assigns
every newly-discovered page as a child of whichever page first links to it. A page already claimed
by an earlier chapter (or an earlier page within the same chapter) is never re-parented — this
keeps every page in the tree exactly once, with structure that mirrors how the docs actually link
to each other (an overview page's "next steps" links become that section's children).

Usage:
    python3 build_doc_tree.py --top-level-file toplevel.json --scope-prefix /docs/foo/guide/ \\
        --output tree.json

toplevel.json is a JSON array of {"title": "...", "url": "..."} objects, in the order they should
appear in the final document — typically produced by asking Claude to WebFetch the seed page and
list its left-nav links in order.
"""

import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crawl_markdown_tree import (  # noqa: E402
    DEFAULT_DELAY_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_USER_AGENT,
    fetch_markdown,
    in_scope_links,
)
import time  # noqa: E402

_H1_RE = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


def _title_from_markdown(markdown_text: str, fallback_url: str) -> str:
    match = _H1_RE.search(markdown_text)
    if match:
        return match.group(1).strip()
    return fallback_url.rstrip("/").rsplit("/", 1)[-1]


def build_tree(top_level, scope_prefix, max_pages, delay, user_agent, timeout):
    claimed = {}  # url -> node dict
    failed = {}

    for entry in top_level:
        url = entry["url"]
        if url in claimed:
            print(f"warning: top-level url appears twice, skipping duplicate: {url}", file=sys.stderr)
            continue
        node = {"title": entry.get("title"), "url": url, "children": []}
        claimed[url] = node

    total_pages = len(claimed)
    for entry in top_level:
        root = claimed.get(entry["url"])
        if root is None:
            continue
        frontier = deque([root])
        while frontier:
            node = frontier.popleft()
            markdown_text = fetch_markdown(node["url"], user_agent, timeout)
            if markdown_text is None:
                failed[node["url"]] = "no markdown twin found"
                continue
            if not node["title"]:
                node["title"] = _title_from_markdown(markdown_text, node["url"])

            for link in in_scope_links(markdown_text, node["url"], scope_prefix):
                if link in claimed or total_pages >= max_pages:
                    continue
                child = {"title": None, "url": link, "children": []}
                claimed[link] = child
                node["children"].append(child)
                frontier.append(child)
                total_pages += 1

            if frontier:
                time.sleep(delay)

    roots = [claimed[e["url"]] for e in top_level if e["url"] in claimed]
    return roots, failed


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
    parser.add_argument("--top-level-file", required=True, help="JSON file: [{\"title\":..,\"url\":..}, ...]")
    parser.add_argument("--scope-prefix", required=True, help="Path prefix all pages must stay under")
    parser.add_argument("--output", required=True, help="Where to write the resulting tree.json")
    parser.add_argument("--max-pages", type=int, default=300)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()

    top_level = json.loads(Path(args.top_level_file).read_text())
    roots, failed = build_tree(
        top_level, args.scope_prefix, args.max_pages, args.delay, args.user_agent, args.timeout
    )

    Path(args.output).write_text(json.dumps(roots, indent=2))

    print(f"chapters: {len(roots)}")
    print(f"total pages: {count_nodes(roots)}")
    if failed:
        print(f"pages skipped (fetch failed): {len(failed)}", file=sys.stderr)
        for url, reason in sorted(failed.items()):
            print(f"  {url}: {reason}", file=sys.stderr)
    print(f"tree written to {args.output}")


if __name__ == "__main__":
    main()
