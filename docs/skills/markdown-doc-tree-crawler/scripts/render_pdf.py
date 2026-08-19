#!/usr/bin/env python3
"""Renders a doc tree (from discover_tree_playwright.py or build_doc_tree.py) into a single PDF
book, in tree order.

Fetches each page's markdown twin fresh (structure discovery and content rendering are kept as
separate steps/scripts on purpose), converts it to HTML, demotes heading levels by tree depth so
the whole thing nests correctly (a chapter's own H1 stays H1; its children's H1 becomes H2, their
children's H1 becomes H3, and so on), resolves relative links/images to absolute URLs, and adds a
title page plus a linked, paginated table of contents.

Usage:
    python3 render_pdf.py tree.json --output book.pdf --title "Some Doc Site"

Dependencies (not stdlib): `pip install markdown weasyprint`, plus a native `pango` install
(`brew install pango` on macOS — WeasyPrint needs it for text shaping/layout at PDF-render time,
not just at import time).
"""

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin


def _ensure_dyld_path():
    """On macOS, dlopen() (used by WeasyPrint's cffi bindings to load libpango/libgobject) doesn't
    search Homebrew's lib directory by default even when the libraries are installed there — this
    is a SIP-era macOS quirk, not a WeasyPrint bug. Point DYLD_FALLBACK_LIBRARY_PATH at whatever
    Homebrew prefix is active (Apple Silicon: /opt/homebrew, Intel: /usr/local) before weasyprint
    is imported, since it resolves the native libs at import time. No-op on Linux, where this
    dlopen search-path restriction doesn't apply."""
    if platform.system() != "Darwin" or os.environ.get("DYLD_FALLBACK_LIBRARY_PATH"):
        return
    try:
        prefix = subprocess.run(
            ["brew", "--prefix"], capture_output=True, text=True, timeout=5, check=True
        ).stdout.strip()
    except Exception:
        prefix = "/opt/homebrew" if platform.machine() == "arm64" else "/usr/local"
    lib_dir = f"{prefix}/lib"
    if os.path.isdir(lib_dir):
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = lib_dir


_ensure_dyld_path()

import markdown  # noqa: E402
import weasyprint  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crawl_markdown_tree import (  # noqa: E402
    DEFAULT_DELAY_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_USER_AGENT,
    fetch_markdown,
    markdown_variant_url,
)

_ATTR_URL_RE = re.compile(r'(href|src)="([^"]+)"')
_ADMONITION_RE = re.compile(r"^:::(\w+)[ \t]*\n(.*?)\n:::[ \t]*$", re.MULTILINE | re.DOTALL)


def _convert_admonitions(markdown_text: str) -> str:
    """Docusaurus/Mintlify-style `:::tip ... :::` blocks aren't standard markdown, so python-
    markdown passes them through as literal text untouched. Render each one to HTML up front and
    splice it back in as a raw HTML block — python-markdown preserves untouched block-level HTML
    that's on its own lines, so the outer conversion pass leaves it alone."""

    def replace(match):
        kind, body = match.group(1).lower(), match.group(2)
        inner_html = markdown.markdown(body, extensions=["fenced_code"])
        return f'\n<div class="admonition admonition-{kind}"><p class="admonition-title">{kind}</p>\n{inner_html}\n</div>\n'

    return _ADMONITION_RE.sub(replace, markdown_text)


_PAGE_CSS = """
@page {
    size: Letter;
    margin: 2.2cm 2cm 2.4cm 2cm;
    @bottom-center {
        content: counter(page);
        font-size: 9pt;
        color: #666;
    }
}
body {
    font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.5;
    color: #1a1a1a;
}
h1, h2, h3, h4, h5, h6 { line-height: 1.25; margin-top: 1.3em; margin-bottom: 0.5em; page-break-after: avoid; }
h1 { font-size: 20pt; }
h2 { font-size: 15pt; }
h3 { font-size: 12.5pt; }
h4, h5, h6 { font-size: 11pt; }
pre, code {
    font-family: "SF Mono", Menlo, Consolas, monospace;
    font-size: 8.5pt;
}
pre {
    background: #f4f4f4;
    padding: 0.7em;
    border-radius: 4px;
    white-space: pre-wrap;
    word-wrap: break-word;
    page-break-inside: avoid;
}
code { background: #f0f0f0; padding: 0.1em 0.3em; border-radius: 3px; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; }
th, td { border: 1px solid #ccc; padding: 0.4em 0.6em; text-align: left; font-size: 9.5pt; }
a { color: #0b5fff; text-decoration: none; }
img { max-width: 100%; }

.admonition {
    border-left: 3px solid #999;
    background: #f5f5f5;
    padding: 0.7em 1em;
    margin: 1em 0;
    border-radius: 0 4px 4px 0;
    page-break-inside: avoid;
}
.admonition p:last-child { margin-bottom: 0; }
.admonition-title {
    font-weight: bold;
    text-transform: capitalize;
    margin: 0 0 0.4em;
    font-size: 9.5pt;
}
.admonition-tip { border-color: #2f9e44; }
.admonition-tip .admonition-title { color: #2f9e44; }
.admonition-note { border-color: #1c7ed6; }
.admonition-note .admonition-title { color: #1c7ed6; }
.admonition-warning, .admonition-caution { border-color: #f08c00; }
.admonition-warning .admonition-title, .admonition-caution .admonition-title { color: #e8590c; }
.admonition-info { border-color: #1c7ed6; }
.admonition-info .admonition-title { color: #1c7ed6; }
.admonition-danger { border-color: #e03131; }
.admonition-danger .admonition-title { color: #e03131; }

.title-page {
    page-break-after: always;
    text-align: center;
    padding-top: 35%;
}
.title-page h1 { font-size: 28pt; border: none; }
.title-page .subtitle { color: #555; font-size: 11pt; margin-top: 1em; }

.toc { page-break-after: always; }
.toc h1 { font-size: 18pt; }
.toc ol { list-style: none; padding-left: 0; }
.toc li { margin: 0.35em 0; }
.toc .depth-2 { padding-left: 1.4em; font-size: 9.5pt; color: #333; }
.toc .depth-3 { padding-left: 2.8em; font-size: 9pt; color: #555; }
.toc a {
    display: flex;
    align-items: baseline;
    color: inherit;
    text-decoration: none;
}
.toc .title { flex: 0 1 auto; }
.toc .dots {
    flex: 1 1 auto;
    border-bottom: 1px dotted #aaa;
    margin: 0 0.3em -0.2em 0.3em;
}
.toc .pagenum { flex: 0 0 auto; }
.toc .pagenum::after { content: target-counter(attr(href url), page); }

section.doc-page { }
section.depth-1 { page-break-before: always; }
"""


def _flatten(roots):
    """Pre-order traversal: each chapter immediately followed by all its descendants, matching how
    a printed book lays out chapters and their subsections."""
    ordered = []

    def visit(node, depth):
        ordered.append((node, depth))
        for child in node["children"]:
            visit(child, depth + 1)

    for root in roots:
        visit(root, 1)
    return ordered


def _rewrite_relative_urls(html_fragment: str, base_url: str) -> str:
    def replace(match):
        attr, value = match.group(1), match.group(2)
        if value.startswith(("http://", "https://", "#", "mailto:", "data:")):
            return match.group(0)
        return f'{attr}="{urljoin(base_url, value)}"'

    return _ATTR_URL_RE.sub(replace, html_fragment)


def _render_page_html(node, depth, anchor_id, user_agent, timeout):
    markdown_text = fetch_markdown(node["url"], user_agent, timeout)
    if markdown_text is None:
        body = f"<p><em>Could not fetch this page ({markdown_variant_url(node['url'])}).</em></p>"
    else:
        baselevel = min(depth, 6)
        markdown_text = _convert_admonitions(markdown_text)
        body = markdown.markdown(
            markdown_text,
            extensions=["fenced_code", "tables", "toc"],
            extension_configs={"toc": {"baselevel": baselevel}},
        )
        body = _rewrite_relative_urls(body, node["url"])
    return f'<section id="{anchor_id}" class="doc-page depth-{depth}">{body}</section>'


def _build_toc_html(flat_nodes, anchors):
    items = []
    for node, depth in flat_nodes:
        anchor = anchors[id(node)]
        css_depth = min(depth, 3)
        title = node["title"] or node["url"]
        items.append(
            f'<li class="depth-{css_depth}"><a href="#{anchor}"><span class="title">{title}</span>'
            f'<span class="dots"></span><span class="pagenum" href="#{anchor}"></span></a></li>'
        )
    return '<section class="toc"><h1>Contents</h1><ol>' + "".join(items) + "</ol></section>"


def build_pdf(tree_path, output_path, title, user_agent, timeout, delay):
    roots = json.loads(Path(tree_path).read_text())
    flat_nodes = _flatten(roots)

    anchors = {id(node): f"sec-{i}" for i, (node, _depth) in enumerate(flat_nodes, start=1)}

    title_page = (
        f'<section class="title-page"><h1>{title}</h1>'
        f'<div class="subtitle">Generated {date.today().isoformat()}</div></section>'
    )
    toc_html = _build_toc_html(flat_nodes, anchors)

    page_sections = []
    total = len(flat_nodes)
    for i, (node, depth) in enumerate(flat_nodes, start=1):
        anchor = anchors[id(node)]
        print(f"[{i}/{total}] fetching {node['url']}", file=sys.stderr)
        page_sections.append(_render_page_html(node, depth, anchor, user_agent, timeout))
        if i < total:
            time.sleep(delay)

    full_html = (
        f"<html><head><meta charset='utf-8'><style>{_PAGE_CSS}</style></head>"
        f"<body>{title_page}{toc_html}{''.join(page_sections)}</body></html>"
    )

    weasyprint.HTML(string=full_html).write_pdf(output_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "tree_json", help="Path to tree.json produced by discover_tree_playwright.py or build_doc_tree.py"
    )
    parser.add_argument("--output", required=True, help="Output PDF path")
    parser.add_argument("--title", default="Documentation", help="Title-page heading")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS, help="Seconds between fetches")
    args = parser.parse_args()

    build_pdf(args.tree_json, args.output, args.title, args.user_agent, args.timeout, args.delay)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
