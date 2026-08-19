import json
import os

from flask import current_app

from api.config import config
from api.presentation.web.csrf import csrf_token

# Mirrors webui/index.html's <head>/<body> shell (title, favicon, fonts, #root) — kept in sync by
# hand since dev mode can't read that file's own <script src="/src/main.tsx"> as-is (it needs the
# react-refresh preamble below first, and an absolute src pointing at the Vite dev server rather
# than a same-origin relative one).
_DEV_SHELL_TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="icon" href="/favicon.ico" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      rel="stylesheet"
      href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;500;600&display=swap"
    />
    <title>Knowledge</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module">
      import RefreshRuntime from "{dev_server}/@react-refresh"
      RefreshRuntime.injectIntoGlobalHook(window)
      window.$RefreshReg$ = () => {{}}
      window.$RefreshSig$ = () => (type) => type
      window.__vite_plugin_react_preamble_installed__ = true
    </script>
    <script type="module" src="{dev_server}/@vite/client"></script>
    <script type="module" src="{dev_server}/src/main.tsx"></script>
  </body>
</html>
"""


def serve_spa_shell(extra_globals: dict[str, object] | None = None):
    """Serves the SPA shell with a fresh CSRF token injected as a global — shared by every Flask
    route that hands off to the SPA (login, change-password, the workspace itself), since the
    SPA's client-side router decides what to render from the URL alone.

    Normally reads the built /workspace SPA's index.html (webui/, built by deploy/Dockerfile's
    Node stage into api/static/workspace/). If WEBUI_DEV_SERVER is set (config.webui_dev_server —
    local `npm run dev` (webui/) iteration only), serves a shell pointing at that Vite dev server
    instead, for HMR — no rebuild or Flask restart needed for a frontend-only change.

    extra_globals lets a specific route inject additional page-load data the same way (e.g. the
    logged-in username for the workspace's account menu) without every caller needing its own
    injection logic."""
    if config.webui_dev_server is not None:
        html = _DEV_SHELL_TEMPLATE.format(dev_server=config.webui_dev_server)
    else:
        index_path = os.path.join(current_app.static_folder, "workspace", "index.html")
        try:
            with open(index_path, encoding="utf-8") as handle:
                html = handle.read()
        except FileNotFoundError:
            # Only reachable during local development, before `npm run build` (webui/) has ever
            # been run once — deploy/Dockerfile's build stage always produces this file for a real
            # image.
            return (
                "webui build output not found at api/static/workspace/index.html — "
                "run `npm run build` in webui/ first.",
                503,
            )

    globals_ = {"CSRF_TOKEN": csrf_token(), **(extra_globals or {})}
    assignments = "".join(f"window.__{key}__={json.dumps(value)};" for key, value in globals_.items())
    return html.replace("</head>", f"<script>{assignments}</script></head>", 1)
