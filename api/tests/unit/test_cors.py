from flask import Flask, jsonify

from api.presentation.web.cors import register_cors

_ORIGIN = "https://knowledge.example.com"


def _app():
    app = Flask(__name__)

    @app.get("/documents")
    def documents():
        response = jsonify([])
        response.headers["X-Total-Count"] = "42"
        return response

    register_cors(app, frozenset({_ORIGIN}))
    return app


def test_expose_headers_lets_the_frontend_read_x_total_count():
    """Regression test: a custom response header like X-Total-Count is invisible to a cross-origin
    fetch()'s JS (response.headers.get(...)) unless the server explicitly allowlists it via
    Access-Control-Expose-Headers -- without it, webui/src/api/client.ts's getPaginated() silently
    read null, fell back to items.length, and the Browse/category pages' pagination control always
    looked like exactly one page regardless of how many documents actually existed."""
    client = _app().test_client()

    response = client.get("/documents", headers={"Origin": _ORIGIN})

    assert response.headers.get("Access-Control-Expose-Headers") == "X-Total-Count"


def test_no_cors_headers_for_a_request_with_no_origin_header():
    client = _app().test_client()

    response = client.get("/documents")

    assert "Access-Control-Expose-Headers" not in response.headers


def test_no_cors_headers_for_a_disallowed_origin():
    client = _app().test_client()

    response = client.get("/documents", headers={"Origin": "https://not-allowed.example.com"})

    assert "Access-Control-Expose-Headers" not in response.headers
