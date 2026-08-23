from uuid import uuid4

import pytest

from api import create_app
from api.constants import OBJECT_PERMISSIONS
from api.presentation.permission_catalog import PERMISSION_GROUPS

# HTTP-layer wiring for GET /profiles/permissions — the labeled vocabulary ProfileFormPage renders
# instead of hardcoding its own copy (see permission_catalog.py). ProfileService/repository aren't
# involved in this route at all, so nothing to mock — only test_tag_routes.py-style session setup.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    test_client = app.test_client()
    with test_client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["active_org_id"] = str(uuid4())
        sess["active_role"] = "admin"
    return test_client


def test_list_permission_catalog_returns_every_group(client):
    response = client.get("/profiles/permissions")

    assert response.status_code == 200
    body = response.get_json()
    assert [group["label"] for group in body["groups"]] == [group["label"] for group in PERMISSION_GROUPS]


def test_permission_catalog_covers_every_object_permission():
    # The real regression guard for the frontend/backend drift this endpoint replaced (webui's old
    # PERMISSION_GROUPS constant had silently fallen out of sync with OBJECT_PERMISSIONS, missing
    # session_settings:read/write) — a plain module-level assert in permission_catalog.py catches
    # this at import time too, but that one disappears under `python -O`, so this is the assertion
    # that's actually guaranteed to run in CI.
    catalogued = {
        permission["value"] for group in PERMISSION_GROUPS for permission in group["permissions"]
    }
    assert catalogued == set(OBJECT_PERMISSIONS)
