from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from api import create_app
from api.domain.entities import SessionSettings
from api.domain.errors import AuthenticationError
from api.presentation.web.session_guard import resolve_cookie_session

# resolve_cookie_session() reads/writes flask.session, so every test runs inside a real request
# context (an app, not a bare function call) even though it's exercised directly rather than
# through a route — same reasoning test_login_routes.py/test_oauth_routes.py already apply.


@pytest.fixture()
def app():
    return create_app(testing=True)


def _settings(**overrides):
    fields = dict(org_id=uuid4(), inactivity_timeout_minutes=120, last_modified_by=None, last_modified_at=datetime.now(timezone.utc))
    fields.update(overrides)
    return SessionSettings(**fields)


def test_no_session_returns_none(app):
    with app.test_request_context("/"):
        assert resolve_cookie_session() is None


def test_never_checked_session_is_allowed_and_gets_touched(app):
    identity_id, org_id = uuid4(), uuid4()
    with app.test_request_context("/"):
        from flask import session

        session["identity_id"] = str(identity_id)
        session["active_org_id"] = str(org_id)

        with (
            patch(
                "api.presentation.web.session_guard.IdentityRepository.get_last_active_at", return_value=None
            ),
            patch("api.presentation.web.session_guard.IdentityRepository.touch_last_active") as mock_touch,
        ):
            resolved = resolve_cookie_session()

        assert resolved == (identity_id, org_id)
        mock_touch.assert_called_once_with(identity_id)


def test_fresh_session_is_allowed(app):
    identity_id, org_id = uuid4(), uuid4()
    with app.test_request_context("/"):
        from flask import session

        session["identity_id"] = str(identity_id)
        session["active_org_id"] = str(org_id)

        with (
            patch(
                "api.presentation.web.session_guard.IdentityRepository.get_last_active_at",
                return_value=datetime.now(timezone.utc) - timedelta(minutes=5),
            ),
            patch(
                "api.presentation.web.session_guard.SessionSettingsService.get",
                return_value=_settings(inactivity_timeout_minutes=120),
            ),
            patch("api.presentation.web.session_guard.IdentityRepository.touch_last_active"),
        ):
            resolved = resolve_cookie_session()

        assert resolved == (identity_id, org_id)


def test_stale_session_is_rejected_and_cleared(app):
    identity_id, org_id = uuid4(), uuid4()
    with app.test_request_context("/"):
        from flask import session

        session["identity_id"] = str(identity_id)
        session["active_org_id"] = str(org_id)
        session["some_other_key"] = "still-here-until-cleared"

        with (
            patch(
                "api.presentation.web.session_guard.IdentityRepository.get_last_active_at",
                return_value=datetime.now(timezone.utc) - timedelta(minutes=130),
            ),
            patch(
                "api.presentation.web.session_guard.SessionSettingsService.get",
                return_value=_settings(inactivity_timeout_minutes=120),
            ),
        ):
            with pytest.raises(AuthenticationError):
                resolve_cookie_session()

        assert "identity_id" not in session
        assert "some_other_key" not in session


def test_respects_a_non_default_org_timeout(app):
    # An org configured for a short 15-minute timeout rejects a 20-minute-old session that would
    # have passed under the 120-minute default.
    identity_id, org_id = uuid4(), uuid4()
    with app.test_request_context("/"):
        from flask import session

        session["identity_id"] = str(identity_id)
        session["active_org_id"] = str(org_id)

        with (
            patch(
                "api.presentation.web.session_guard.IdentityRepository.get_last_active_at",
                return_value=datetime.now(timezone.utc) - timedelta(minutes=20),
            ),
            patch(
                "api.presentation.web.session_guard.SessionSettingsService.get",
                return_value=_settings(inactivity_timeout_minutes=15),
            ),
        ):
            with pytest.raises(AuthenticationError):
                resolve_cookie_session()
