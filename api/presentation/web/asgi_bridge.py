from contextlib import AsyncExitStack, asynccontextmanager

from a2wsgi import WSGIMiddleware
from flask import Flask
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.types import ASGIApp

from api.presentation.web.mcp_org_scoping import MCPOrgScopingMiddleware


def build_asgi_app(flask_app: Flask, mcp_servers: list[FastMCP] | None = None) -> ASGIApp:
    """Wraps a Flask (WSGI) app for ASGI serving, optionally alongside one or more FastMCP
    instances, via a2wsgi.WSGIMiddleware (Starlette's own WSGIMiddleware is deprecated in favor of
    this). Kept import-side-effect-free (unlike api/asgi.py, which also imports the real
    api.wsgi.app singleton — that triggers a real DB bootstrap at import time) so tests can build a
    combined app around a create_app(testing=True) instance instead, with or without any MCP
    servers mounted.

    Each FastMCP server's own Starlette app (streamable_http_app()) carries its streamable-http
    endpoint at a real, full top-level path (see mcp_server/server.py's streamable_http_path) —
    that route is merged directly into this app's own top-level route list rather than nested
    under an extra Mount(), since nesting would double the path prefix. (An earlier version of
    mcp_server/server.py also configured FastMCP's own AuthSettings, which would have added an RFC
    9728 well-known discovery route here too — computed relative to that sub-app's own root, same
    nesting-breaks-it hazard. That's gone now: see server.py's own docstring on why FastMCP no
    longer does its own auth/discovery at all.) Flask's catch-all is listed last for readability —
    a route with a real path always wins over it regardless of order.

    Each FastMCP server's own internal lifespan (which enters its session_manager.run() — see the
    installed SDK's FastMCP.streamable_http_app) is never triggered just by merging its routes in:
    Starlette's Router only dispatches the ASGI "lifespan" scope type to itself, not to routes that
    originated from another app, so a merged-in MCP server would silently never start its session
    manager without this. The combined app's own lifespan enters every server's
    session_manager.run() itself instead.

    When any MCP servers are mounted, the whole app is wrapped in MCPOrgScopingMiddleware — every
    org's tools live at /<org-slug>/mcp/<tier>, not the bare /mcp/<tier> path FastMCP itself still
    literally serves (see that module's docstring for why the org-slug awareness lives in front of
    FastMCP rather than inside its own mounting). "Wrapped" here means the middleware instance
    becomes the actual ASGI app returned — not a Starlette middleware= entry — since it's a pure
    ASGI passthrough that only inspects/rewrites scope before delegating, not a Starlette-specific
    construct, and it must sit in front of route matching, not be one of the matched routes.
    """
    mcp_servers = mcp_servers or []

    routes = []
    for mcp in mcp_servers:
        routes.extend(mcp.streamable_http_app().routes)
    routes.append(Mount("/", app=WSGIMiddleware(flask_app)))

    lifespan = None
    if mcp_servers:

        @asynccontextmanager
        async def lifespan(_app):
            async with AsyncExitStack() as stack:
                for mcp in mcp_servers:
                    await stack.enter_async_context(mcp.session_manager.run())
                yield

    app = Starlette(routes=routes, lifespan=lifespan)
    return MCPOrgScopingMiddleware(app) if mcp_servers else app
