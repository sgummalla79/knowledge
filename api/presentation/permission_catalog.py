from api.constants import OBJECT_PERMISSIONS

# Human labels for api.constants.OBJECT_PERMISSIONS, grouped for ProfileFormPage's checkbox list —
# used to live as a hand-duplicated constant in webui (PERMISSION_GROUPS in ProfileFormPage.tsx),
# which had already drifted out of sync with OBJECT_PERMISSIONS (missing the session_settings:*
# pair added alongside the session-inactivity-timeout feature) by the time this moved server-side.
# Exposed via GET /profile-permissions so the vocabulary — value *and* label — has exactly one
# home; adding a new OBJECT_PERMISSIONS entry without adding it here fails
# test_permission_catalog_covers_every_object_permission (api/tests/unit/test_profiles_routes.py)
# rather than silently leaving it ungrantable through the UI the way session_settings did.
PERMISSION_GROUPS: tuple[dict, ...] = (
    {"label": "Organization", "permissions": ({"value": "org:write", "label": "Rename / describe org"},)},
    {
        "label": "Documents",
        "permissions": ({"value": "documents:read", "label": "Read"}, {"value": "documents:write", "label": "Write"}),
    },
    {
        "label": "Categories",
        "permissions": ({"value": "categories:read", "label": "Read"}, {"value": "categories:write", "label": "Write"}),
    },
    {
        "label": "Shelves",
        "permissions": ({"value": "shelves:read", "label": "Read"}, {"value": "shelves:write", "label": "Write"}),
    },
    {
        "label": "Tags",
        "permissions": ({"value": "tags:read", "label": "Read"}, {"value": "tags:write", "label": "Write"}),
    },
    {
        "label": "Embedding models",
        "permissions": (
            {"value": "embedding_models:read", "label": "Read"},
            {"value": "embedding_models:write", "label": "Write"},
        ),
    },
    {
        "label": "Org members",
        "permissions": (
            {"value": "org_members:read", "label": "Read"},
            {"value": "org_members:write", "label": "Write"},
        ),
    },
    {
        "label": "Connected applications",
        "permissions": (
            {"value": "applications:read", "label": "Read"},
            {"value": "applications:write", "label": "Write"},
        ),
    },
    {
        "label": "Profiles",
        "permissions": ({"value": "profiles:read", "label": "Read"}, {"value": "profiles:write", "label": "Write"}),
    },
    {
        "label": "MCP settings",
        "permissions": (
            {"value": "mcp_settings:read", "label": "Read"},
            {"value": "mcp_settings:write", "label": "Write"},
        ),
    },
    {
        "label": "Session settings",
        "permissions": (
            {"value": "session_settings:read", "label": "Read"},
            {"value": "session_settings:write", "label": "Write"},
        ),
    },
    {"label": "Search", "permissions": ({"value": "queries:execute", "label": "Execute queries"},)},
)


def _flattened_values() -> set[str]:
    return {permission["value"] for group in PERMISSION_GROUPS for permission in group["permissions"]}


assert _flattened_values() == set(OBJECT_PERMISSIONS), (
    "PERMISSION_GROUPS has drifted from OBJECT_PERMISSIONS — every permission needs a group+label "
    "entry here, and vice versa (see test_permission_catalog_covers_every_object_permission)."
)
