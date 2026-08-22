from unittest.mock import patch
from uuid import uuid4

import pytest

from api import create_app

# HTTP-layer only — IdentityRepository is mocked, no real DB involved.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def _logged_in(client):
    org_id = uuid4()
    with client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["active_org_id"] = str(org_id)
    return org_id


def _built_shell(client, tmp_path):
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    (workspace_dir / "index.html").write_text("<html><head><title>Knowledge</title></head><body></body></html>")
    with client.application.app_context():
        client.application.static_folder = str(tmp_path)


def test_root_requires_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/sign-in" in response.headers["Location"]


@patch("api.presentation.routes.app_shell.IdentityRepository.get_by_id", return_value=None)
def test_root_serves_built_shell_with_injected_globals(_get_user, client, tmp_path):
    _built_shell(client, tmp_path)
    _logged_in(client)

    response = client.get("/")
    assert response.status_code == 200
    assert b"__CSRF_TOKEN__" in response.data
    assert b"__ORG_ID__" in response.data


@patch("api.presentation.routes.app_shell.IdentityRepository.get_by_id", return_value=None)
def test_arbitrary_subpath_serves_the_same_shell(_get_user, client, tmp_path):
    _built_shell(client, tmp_path)
    _logged_in(client)

    response = client.get("/browse")
    assert response.status_code == 200
    assert b"__CSRF_TOKEN__" in response.data


@patch("api.presentation.routes.app_shell.IdentityRepository.get_by_id", return_value=None)
def test_missing_build_output_returns_503(_get_user, client, tmp_path):
    with client.application.app_context():
        client.application.static_folder = str(tmp_path)
    _logged_in(client)

    response = client.get("/")
    assert response.status_code == 503
