import json
import os

from flask import current_app

from app.presentation.web.csrf import csrf_token


def serve_spa_shell(extra_globals: dict[str, object] | None = None):
    """Serves the built /workspace SPA's index.html (webui/, built by deploy/Dockerfile's Node
    stage into app/static/workspace/) with a fresh CSRF token injected as a global — shared by
    every Flask route that hands off to the SPA (login, change-password, the workspace itself),
    since the SPA's client-side router decides what to render from the URL alone.

    extra_globals lets a specific route inject additional page-load data the same way (e.g. the
    logged-in username for the workspace's account menu) without every caller needing its own
    injection logic."""
    index_path = os.path.join(current_app.static_folder, "workspace", "index.html")
    try:
        with open(index_path, encoding="utf-8") as handle:
            html = handle.read()
    except FileNotFoundError:
        # Only reachable during local development, before `npm run build` (webui/) has ever been
        # run once — deploy/Dockerfile's build stage always produces this file for a real image.
        return (
            "webui build output not found at app/static/workspace/index.html — "
            "run `npm run build` in webui/ first.",
            503,
        )

    globals_ = {"CSRF_TOKEN": csrf_token(), **(extra_globals or {})}
    assignments = "".join(f"window.__{key}__={json.dumps(value)};" for key, value in globals_.items())
    return html.replace("</head>", f"<script>{assignments}</script></head>", 1)
