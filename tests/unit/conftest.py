import os
from unittest.mock import patch

import pytest
from flask import Flask

from app.infrastructure.auth.jwt_tokens import issue_access_token


@pytest.fixture(autouse=True)
def _mock_sidebar_embedding_provider_status():
    """The dashboard sidebar queries embedding_provider_settings on every authenticated page
    render (see auth_ui._inject_embedding_provider_nav_status), so any test that renders a full
    dashboard page — not just embedding-settings tests — would otherwise need a real DB. Defaults
    to "nothing configured" globally; tests that care about the sidebar's provider strip override
    this locally with their own `with patch(...)`."""
    with patch("app.presentation.routes.auth_ui.EmbeddingProviderSettingsRepository.list", return_value=[]):
        yield


@pytest.fixture()
def auth_headers():
    """Mints a Bearer token with the given scopes for HTTP-layer tests. Uses a bare Flask app
    (not the app factory) purely as a context to sign the token — going through create_app()
    would re-run limiter.init_app() against the module-level Limiter singleton and reset
    test_rate_limit.py's overridden limit back to the default."""

    def _make(*scopes: str) -> dict:
        minimal_app = Flask(__name__)
        minimal_app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
        with minimal_app.app_context():
            token = issue_access_token("test-app", list(scopes), ttl_seconds=60)
        return {"Authorization": f"Bearer {token}"}

    return _make
