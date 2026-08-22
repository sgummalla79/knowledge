"""Combined ASGI entrypoint — the Flask REST API (wrapped WSGI-in-ASGI) and the three MCP tool
tiers, served by one process (see deploy/entrypoint.sh: gunicorn -k uvicorn.workers.UvicornWorker
api.asgi:app).

api/wsgi.py stays a plain Flask WSGI app, unchanged and still used directly for fast local
iteration (`flask --app api.wsgi run`, per this repo's dev-preview workflow) — this module is
additive, the only thing that changes is what actually ships in the container.

Importing this module triggers api.wsgi's real DB bootstrap (create_app()'s default
bootstrap_admin=True) — deliberately kept out of api.presentation.web.asgi_bridge, whose
build_asgi_app() factory is import-side-effect-free, so tests can build a combined app around a
create_app(testing=True) instance without needing a real database.
"""

from api.mcp_server.server import build_mcp_servers
from api.presentation.web.asgi_bridge import build_asgi_app
from api.wsgi import app as flask_app

app = build_asgi_app(flask_app, build_mcp_servers())
