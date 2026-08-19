---
name: markdown-doc-tree-crawler
description: Use when the user gives a documentation URL and wants every page under it discovered or listed — its "tree," "child articles," or "child pages." Trigger phrases include "list all the pages under this URL", "what pages would get crawled from this URL", "show me the child articles in this doc tree", "crawl this doc site and list the pages", "does this site have a full page list/sitemap". Works by finding each page's plain-markdown twin (many modern doc sites — Docusaurus, Nextra, Mintlify, Salesforce Developer Docs, etc. — publish one alongside the HTML) and following its real markdown links, which sidesteps JS-rendered nav or Shadow DOM content that a plain HTML fetch, or even a headless-browser render, can't see into.
version: 1.0.0
---

# Markdown Doc-Tree Crawler

> This is a committed reference copy. The live copy Claude Code actually loads for automatic
> skill invocation lives at `~/.claude/skills/markdown-doc-tree-crawler/` (user-level, outside
> this repo — `.claude/` here is git-ignored). To reinstall it as an active skill on another
> machine, copy this directory to `~/.claude/skills/markdown-doc-tree-crawler/`.

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
