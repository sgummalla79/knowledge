from functools import wraps

from flask import current_app, jsonify, request


def require_api_key(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        provided = request.headers.get("X-API-Key")
        if provided != current_app.config["API_KEY"]:
            return jsonify({"error": "unauthorized"}), 401
        return view(*args, **kwargs)

    return wrapped
