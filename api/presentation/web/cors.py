from flask import Flask, Response, request


def register_cors(app: Flask, allowed_origins: frozenset[str]) -> None:
    """Cross-origin cookie support for a webui/ served from a different origin than this API
    (see config.webui_origins) — every resource route here is cookie+CSRF authenticated
    (auth_ui.py/client.ts), not bearer-token, so a browser fetch() with credentials: 'include'
    needs an explicit Access-Control-Allow-Origin/-Credentials pair; the wildcard '*' origin is
    rejected by browsers whenever credentials are involved, so this always echoes back one
    specific, allowlisted origin rather than reflecting any Origin sent."""

    @app.before_request
    def _handle_preflight():
        if request.method == "OPTIONS" and request.headers.get("Origin"):
            return _cors_headers(Response())

    @app.after_request
    def _apply_cors_headers(response: Response) -> Response:
        return _cors_headers(response)

    def _cors_headers(response: Response) -> Response:
        origin = request.headers.get("Origin")
        if origin not in allowed_origins:
            return response
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        existing_vary = response.headers.get("Vary")
        response.headers["Vary"] = f"{existing_vary}, Origin" if existing_vary else "Origin"
        if request.method == "OPTIONS":
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRF-Token"
        return response
