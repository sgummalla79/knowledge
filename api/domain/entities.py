from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# Document is intentionally thin/anemic (no behavior) — it mirrors the persisted fields 1:1 and
# exists only so the application layer depends on plain data, not ORM rows. Inventing methods here
# just to avoid "anemic domain model" would be premature abstraction.


@dataclass(frozen=True)
class Document:
    id: UUID
    org_id: UUID
    source_id: UUID | None
    category_id: UUID | None
    owner_id: UUID
    title: str
    type: str
    # Technical upload format (pdf/md/txt/html) driving parser selection — distinct from `type`
    # above (article/document classification). See the ORM class docstring.
    file_type: str
    content_uri: str | None
    description: str | None
    status: str
    error_message: str | None
    size_bytes: int | None
    chunk_count: int | None
    split_group_id: UUID | None
    split_part: int | None
    split_total: int | None
    created_by: UUID | None
    last_modified_by: UUID | None
    created_at: datetime
    last_modified_at: datetime
    indexed_at: datetime | None


@dataclass(frozen=True)
class Chunk:
    """A document's persisted chunk, as browsed (Item page's chunk table) rather than as scored
    retrieval output — see ScoredChunk below for the query-time variant. No `status` field: a
    chunk row only ever exists after successful embedding, so every persisted chunk is implicitly
    "indexed" by construction — there's nothing to store."""

    id: UUID
    document_id: UUID
    ordinal: int
    content: str
    token_count: int
    created_at: datetime


@dataclass(frozen=True)
class ScoredChunk:
    id: UUID
    document_id: UUID
    ordinal: int
    content: str
    # Higher is always better — whether this is a per-list similarity score or an RRF-fused score
    # depends on which stage of the pipeline produced it. Never a lower-is-better distance, so
    # callers never have to remember which convention applies.
    score: float


@dataclass(frozen=True)
class EmbeddingSettings:
    id: UUID
    provider: str
    model: str
    api_key: str | None
    base_url: str | None
    dimensions: int
    chunk_size: int
    chunk_overlap: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class EmbeddingProviderConfig:
    id: UUID
    provider: str
    enabled: bool
    model: str | None
    api_key: str | None
    base_url: str | None
    dimensions: int | None
    chunk_size: int | None
    chunk_overlap: int | None
    created_at: datetime | None
    updated_at: datetime


@dataclass(frozen=True)
class RoutedScoredChunk:
    category_id: UUID
    category_name: str
    chunk: ScoredChunk


@dataclass(frozen=True)
class Organization:
    id: UUID
    name: str
    slug: str
    description: str | None
    plan: str
    created_by: UUID | None
    last_modified_by: UUID | None
    created_at: datetime
    last_modified_at: datetime


@dataclass(frozen=True)
class Category:
    id: UUID
    org_id: UUID
    parent_id: UUID | None
    name: str
    slug: str
    description: str | None
    created_by: UUID | None
    last_modified_by: UUID | None
    created_at: datetime
    last_modified_at: datetime


@dataclass(frozen=True)
class Tag:
    id: UUID
    org_id: UUID
    name: str
    created_by: UUID | None
    created_at: datetime


@dataclass(frozen=True)
class Query:
    id: UUID
    org_id: UUID
    user_id: UUID | None
    query_text: str
    latency_ms: int | None
    result_count: int | None
    created_at: datetime


@dataclass(frozen=True)
class QueryResult:
    id: int
    query_id: UUID
    chunk_id: UUID
    rank: int
    similarity_score: float


@dataclass(frozen=True)
class Shelf:
    id: UUID
    org_id: UUID
    name: str
    slug: str
    description: str | None
    is_default: bool
    created_by: UUID | None
    last_modified_by: UUID | None
    created_at: datetime
    last_modified_at: datetime


@dataclass(frozen=True)
class UserShelfAccess:
    user_id: UUID
    shelf_id: UUID
    granted_by: UUID | None
    granted_at: datetime


@dataclass(frozen=True)
class Source:
    id: UUID
    org_id: UUID
    type: str
    name: str
    config: dict
    api_key_hash: str | None
    status: str
    created_by: UUID | None
    last_modified_by: UUID | None
    created_at: datetime
    last_modified_at: datetime
    last_synced_at: datetime | None


@dataclass(frozen=True)
class IngestionJob:
    id: UUID
    org_id: UUID
    source_id: UUID | None
    document_id: UUID | None
    type: str
    status: str
    error_message: str | None
    items_processed: int
    triggered_by: UUID | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True)
class Identity:
    """A person — see migration 0001's module docstring for the original identities/org_members
    split (that rationale, "one identity can belong to many orgs and switch between them," no
    longer holds: migration 0013 made org_members.identity_id unique, so an identity now belongs to
    exactly one org for its whole life). `username` is globally unique across the whole app and
    must be email-shaped (see api/application/username_validation.py) but isn't necessarily a real,
    deliverable address — that's `email`, which is optional and, unlike username, not unique."""

    id: UUID
    username: str
    email: str | None
    name: str
    password_hash: str
    must_change_password: bool
    created_at: datetime
    last_modified_at: datetime
    last_active_at: datetime | None


@dataclass(frozen=True)
class MostRetrievedDocument:
    document_id: UUID
    title: str
    retrieval_count: int
    avg_similarity: float


@dataclass(frozen=True)
class DashboardStats:
    document_count: int
    chunk_count: int
    queries_last_30d: int
    avg_query_latency_ms: float | None
    most_retrieved_documents: list[MostRetrievedDocument]


@dataclass(frozen=True)
class OrgMember:
    """Which orgs an Identity belongs to, and with what profile (object-level read/write grants)
    in each — a person can hold a different membership (and profile) in several orgs and switch
    between them."""

    id: UUID
    org_id: UUID
    identity_id: UUID
    profile_id: UUID
    invited_by: UUID | None
    last_modified_by: UUID | None
    created_at: datetime
    last_modified_at: datetime


@dataclass(frozen=True)
class Profile:
    """An org-scoped, reusable bundle of per-object-type read/write grants — assigned to org
    members (and, later, to a connected application's execute-as user) rather than access being
    granted to a person or app directly. `is_admin` marks the one profile per org whose permissions
    are always every OBJECT_PERMISSIONS entry — enforced by ProfileService, not something a
    permission grid ever edits. `is_system` marks all three seeded-per-org default profiles (Admin,
    Contributor, Viewer) as fully locked — no name/description/permission edits, no deletion — a
    strict superset of is_admin (every is_admin profile is also is_system, but Contributor/Viewer
    are is_system without being is_admin, since they don't get every permission)."""

    id: UUID
    org_id: UUID
    name: str
    description: str | None
    is_admin: bool
    is_system: bool
    created_by: UUID | None
    last_modified_by: UUID | None
    created_at: datetime
    last_modified_at: datetime


@dataclass(frozen=True)
class Application:
    """An org-scoped connected application (MCP client / external integration) — its actual
    request-time authority is its granted scopes (see application_scopes / ApplicationRepositoryPort.
    list_scopes), not org role; service_identity_id exists only to satisfy this schema's
    created_by/owner_id-style FKs, which all point at identities.id."""

    id: UUID
    org_id: UUID
    name: str
    description: str | None
    auth_method: str
    status: str
    service_identity_id: UUID
    # Only set for oauth_client_credentials — the real, already-existing member a token from this
    # application resolves to (PermissionService.resolve_permissions is keyed off this, not
    # service_identity_id, which client_credentials never meaningfully reads).
    execute_as_identity_id: UUID | None
    # Whether this application may reach the MCP server at all, uniform across all three auth
    # methods (see api/mcp_server/ and MCPSettings below) — independent of application_scopes/profile,
    # a channel flag rather than a resource permission.
    mcp_access: bool
    # Symmetric channel flag for the other direction: whether this application may call the plain
    # REST API at all, independent of what application_scopes/profile would otherwise grant.
    # Defaults true (see migration 0009) since REST API access is this app's original purpose.
    api_access: bool
    created_by: UUID | None
    last_modified_by: UUID | None
    revoked_at: datetime | None
    revoked_by: UUID | None
    created_at: datetime
    last_modified_at: datetime


@dataclass(frozen=True)
class MCPSettings:
    """One row per org: independent on/off switches for each of the three MCP tool tiers
    (api/mcp_server/). Absent row means all three off — see MCPSettingsService's "no row yet" default,
    same convention embedding_settings historically used before it went per-provider."""

    org_id: UUID
    rag_read_enabled: bool
    object_read_enabled: bool
    object_write_enabled: bool
    last_modified_by: UUID | None
    last_modified_at: datetime


@dataclass(frozen=True)
class SessionSettings:
    """One row per org: how long a browser (cookie) session may sit idle before it's rejected,
    even though the signed cookie itself hasn't cryptographically expired — enforced in
    api/presentation/web/session_guard.py, not by Flask's own session machinery. Absent row means
    the default (SESSION_TIMEOUT_DEFAULT_MINUTES) — see SessionSettingsService's "no row yet"
    default, same convention MCPSettings above uses."""

    org_id: UUID
    inactivity_timeout_minutes: int
    last_modified_by: UUID | None
    last_modified_at: datetime


@dataclass(frozen=True)
class ApplicationOAuthClient:
    """Shared credential row for both oauth_client_credentials and oauth_authorization_code —
    application_id itself is the wire-format client_id, so there's no separate client_id column.
    client_secret_hash is required for client_credentials and always None for authorization_code
    (a public, PKCE-only client — see api/infrastructure/auth/pkce.py). redirect_uris is only
    populated for authorization_code."""

    id: UUID
    application_id: UUID
    client_secret_hash: str | None
    redirect_uris: list[str]
    created_at: datetime
    last_rotated_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True)
class AuthorizationCode:
    """A single-use, short-lived authorization_code grant — identity_id is whoever completed the
    consent screen, resolved fresh at exchange time via PermissionService just like every other
    request path."""

    id: UUID
    code_hash: str
    application_id: UUID
    org_id: UUID
    identity_id: UUID
    redirect_uri: str
    code_challenge: str
    code_challenge_method: str
    scope: str
    expires_at: datetime
    consumed_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class RefreshToken:
    id: UUID
    token_hash: str
    application_id: UUID
    org_id: UUID
    identity_id: UUID
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True)
class PersonalAccessToken:
    """A self-service, per-user API key — created by an identity for themselves, in whichever org
    is active at creation time (org_id is then fixed; same per-request-org model every other
    credential here already uses). No revoked_at/rotation: deleting the row is the only
    lifecycle-ending action. Authority is never baked into the token itself — AppAuthService
    resolves (identity_id, org_id) from token_hash, then calls the identical
    PermissionService.resolve_permissions() a session or oauth_client_credentials caller uses, so a
    token's effective permissions always track that identity's *current* profile in that org."""

    id: UUID
    identity_id: UUID
    org_id: UUID
    name: str
    token_hash: str
    token_prefix: str
    # Same channel-flag concept as Application.mcp_access — opt-in, since a personal key's default
    # purpose is REST access (unconditional for this entity, unlike Application.api_access, which
    # doesn't exist here at all).
    mcp_access: bool
    created_at: datetime
    last_used_at: datetime | None


@dataclass(frozen=True)
class ResolvedCaller:
    """What a verified machine-caller bearer token resolves to. Returned by
    AppAuthService.authenticate_bearer_token, which is deliberately framework-free so this same
    entity (and the service that produces it) is reusable by both the Flask require_scope
    decorator and api/mcp_server/."""

    org_id: UUID
    identity_id: UUID
    # Only set for an Application-backed caller (oauth_client_credentials/oauth_authorization_code)
    # — a personal_access_token caller has no application at all, identified purely by identity_id.
    application_id: UUID | None
    scopes: frozenset[str]
    auth_method: str
    # Mirrors Application.mcp_access / PersonalAccessToken.mcp_access — unused by the REST API's
    # own require_permission, only consulted by api/mcp_server/permissions.py's
    # require_tier_permission.
    mcp_access: bool
    # Mirrors Application.api_access for an Application-backed caller; always True for a
    # personal_access_token caller (that entity has no api_access column at all — a personal key's
    # whole purpose is REST access, so it's unconditional, not a toggle). Checked by
    # require_permission before the scope check. Not consulted by api/mcp_server/, which has its
    # own independent mcp_access gate; a caller can be REST-only, MCP-only, both, or neither.
    api_access: bool
