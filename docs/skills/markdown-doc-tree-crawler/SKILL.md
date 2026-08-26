---
name: markdown-doc-tree-crawler
description: Use when the user gives a documentation URL and wants every page under it discovered or listed — its "tree," "child articles," or "child pages" — or wants the whole doc tree exported as a single PDF book. Trigger phrases include "list all the pages under this URL", "what pages would get crawled from this URL", "show me the child articles in this doc tree", "crawl this doc site and list the pages", "does this site have a full page list/sitemap", "turn this doc site into a PDF", "generate a PDF of this doc tree with the same structure as the sidebar". Works by finding each page's plain-markdown twin (many modern doc sites — Docusaurus, Nextra, Mintlify, Salesforce Developer Docs, etc. — publish one alongside the HTML) and following its real markdown links, which sidesteps JS-rendered nav or Shadow DOM content that a plain HTML fetch, or even a headless-browser render, can't see into. For the PDF/hierarchy use case, a second, more reliable structure-discovery path reads the site's real rendered sidebar via Playwright — see "Building a PDF book" below.
version: 2.0.0
---

# Markdown Doc-Tree Crawler

> This is a committed reference copy. The live copy Claude Code actually loads for automatic
> skill invocation lives at `~/.claude/skills/markdown-doc-tree-crawler/` (user-level, outside
> this repo — `.claude/` here is git-ignored). To reinstall it as an active skill on another
> machine, copy this directory to `~/.claude/skills/markdown-doc-tree-crawler/`. It now includes
> three additional scripts (`build_doc_tree.py`, `discover_tree_playwright.py`, `render_pdf.py`)
> for exporting a doc tree as a single PDF book — see "Building a PDF book" below.

## What this does

Given a single documentation page URL, discovers every other page in that doc "book"/tree by
following the site's plain-markdown link graph — no headless browser, no JS execution required.
It works even on sites whose real navigation/content lives inside Shadow DOM web components, which
defeats both a plain HTML `<a href>` scrape *and* a Playwright/Puppeteer `page.content()` dump
(neither pierces shadow roots — that's a browser-API limitation, not a rendering-wait issue).

## Why this works

Many modern documentation platforms publish a plain-markdown sibling of every HTML page at the
same path, with `.html`/`.htm` replaced by `.md` (or `.md` appended, if the page has no extension).
That markdown page has the same content as clean text, plus real `[text](url)` links to sibling
pages — reachable via a plain static GET.

Verified empirically in a real session against `developer.salesforce.com/docs/...`: the site's
actual left-nav and article content render inside native Shadow DOM (confirmed via
`document.querySelectorAll('*')` finding elements with `.shadowRoot` set), invisible to
`page.content()` even after a full headless-Chromium render with `wait_until="networkidle"`. But
the `.md` twin of each page (e.g. `.../guide/get-started.html` → `.../guide/get-started.md`)
returns clean markdown with real links to every sibling page, letting a plain static BFS crawl
enumerate the entire tree — no browser needed at all.

## How to use it

1. Run the bundled script against the seed URL the user gave you:
   ```bash
   python3 ~/.claude/skills/markdown-doc-tree-crawler/scripts/crawl_markdown_tree.py "<seed-url>"
   ```
   It prints the scope prefix used, the total page count, then every discovered URL sorted, one
   per line. No dependencies beyond the Python 3 standard library.

2. If the seed URL itself has no markdown twin, the script exits with a clear message rather than
   silently reporting zero pages. This is common for a site's top-level landing/overview page even
   when every article page underneath has one — retry with a URL one level in (e.g. the first
   "Get Started" or "Introduction" link on that page).

3. Useful flags (`--help` for the full list):
   - `--scope-prefix /docs/some/subpath/` — override the default scope (the seed URL's own
     directory) if related content spans multiple sibling directories (e.g. a `guide/` and a
     `references/` directory that should both be included), or to narrow/widen it.
   - `--max-pages N` — default 300; raise for a very large doc site, lower for a quick sample.
   - `--user-agent "..."` — the default identifies this tool honestly; switch to a normal browser
     UA if every request comes back blocked.

4. Report the result back to the user as a clear list (or a count + list) — this skill's job is
   discovery, not judgment about which pages matter. If they want the *content* of the pages too,
   that's a separate step: fetch each URL from the resulting list.

## Known limitations

- Only finds pages reachable through the markdown link graph starting from the seed — a page with
  no incoming link from anything you visited won't be discovered (same limitation any crawler has).
- Occasional transient 5xx responses from CDN/bot-detection layers (observed on
  developer.salesforce.com, which is Akamai-fronted) are retried once automatically; a page that
  still fails is reported as skipped on stderr, not silently dropped from the count.
- This only *discovers and lists* pages — it doesn't download/ingest their content.
- **Do not use this script's link graph to infer page *hierarchy* (parent/child structure).**
  Confirmed empirically: pages often carry "See Also" / "Related Topics" / "What to Do Next"
  sections whose links point to unrelated topics elsewhere in the site, not real children — and
  there's no reliable textual marker separating those from genuine "next step" links, since both
  appear as plain `[text](url)` links in the body, sometimes inside ordinary prose. A first attempt
  at building a nested tree this way produced a badly tangled result (one chapter's crawl
  transitively absorbed most of the book via cross-reference chains). For a flat page *list*, this
  is a non-issue. For a hierarchical *tree* (e.g. to build a PDF book), use
  `discover_tree_playwright.py` instead — see below.

## Building a PDF book (exact sidebar structure)

For "export this doc tree as one PDF, in the same order/structure as the site's own nav," use the
three scripts below together rather than trying to infer structure from `crawl_markdown_tree.py`'s
flat list (see the limitation above for why).

**1. Discover the true hierarchical tree** — reads the site's actual rendered sidebar via a
headless browser (piercing Shadow DOM, since that's where this nav typically lives), rather than
guessing from in-body links:
```bash
python3 ~/.claude/skills/markdown-doc-tree-crawler/scripts/discover_tree_playwright.py \
  "<any-page-url-in-the-tree>" --scope-prefix /docs/foo/guide/ --output tree.json
```
Why this is reliable where body-link inference isn't: visiting a page only ever auto-expands
*that page's own* sidebar section — sibling sections stay collapsed. So a page's true children are
exactly whatever new links appear in its rendered sidebar that weren't visible from any
already-visited page. No ambiguity between "next step" and "related topic," because the sidebar
only ever shows structural nav, never prose cross-references. Also auto-discovers the top-level
chapter list from the seed page itself — no manual step needed first.
Requires `pip install playwright && playwright install chromium` (one-time, ~150–300MB).
If a site's nav isn't in Shadow DOM / doesn't have this collapse-by-section behavior, a plain
`page.evaluate()` DOM walk still works the same way — the shadow-piercing part is a no-op there.

**2. (Fallback, no Playwright) Heuristic tree from body links** — `build_doc_tree.py` reuses
`crawl_markdown_tree.py`'s link-following logic but assigns first-discovers-wins parentage. Faster
and zero extra dependencies, but only trustworthy on sites confirmed *not* to mix cross-reference
links into body content (verify by spot-checking a few pages' raw `.md` first). Needs a manually
supplied top-level chapter list (JSON array of `{"title", "url"}`, in sidebar order — get this via
WebFetch on the seed page asking for the left-nav links in order) since that part can't be inferred
from markdown alone:
```bash
python3 ~/.claude/skills/markdown-doc-tree-crawler/scripts/build_doc_tree.py \
  --top-level-file toplevel.json --scope-prefix /docs/foo/guide/ --output tree.json
```

**3. Render the tree to PDF** — fetches each page's markdown twin, converts to HTML (heading
levels demoted per tree depth so nesting stays correct), resolves relative links/images to
absolute URLs, converts `:::tip`/`:::note`/etc. admonition blocks to styled callouts, and adds a
title page plus a linked, paginated table of contents:
```bash
python3 ~/.claude/skills/markdown-doc-tree-crawler/scripts/render_pdf.py tree.json \
  --output book.pdf --title "Some Doc Site"
```
`--output` always lands in `~/Downloads` — a bare filename or any relative path is resolved against
`~/Downloads` (created if it doesn't exist yet), not the current working directory; pass an
absolute path only if the user explicitly wants the PDF saved somewhere else. The script prints the
real, final path it wrote to — report that path back to the user rather than assuming it matches
whatever was passed to `--output`.

Requires `pip install markdown weasyprint`, plus a native `pango` install
(`brew install pango` on macOS). On macOS, WeasyPrint's native libs (libpango/libgobject, via
Homebrew) aren't found by `dlopen()` unless `DYLD_FALLBACK_LIBRARY_PATH` points at the Homebrew
lib dir — `render_pdf.py` sets this automatically at import time, detecting the active Homebrew
prefix; no manual `export` needed.

Verified end-to-end against `developer.salesforce.com`'s Agentforce Vibes guide: 45 pages, 16
top-level chapters, several correctly nested up to 3 levels deep, rendered into a 105-page PDF with
a working paginated ToC.
