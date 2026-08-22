from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.constants import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_TOP_K,
    WEB_CRAWL_MAX_PAGES_LIMIT,
)
from api.application.embedding_provider_settings_service import EmbeddingProviderConfigStatus
from api.domain.entities import (
    Application,
    Category,
    Chunk,
    DashboardStats,
    Document,
    IngestionJob,
    MCPSettings,
    MostRetrievedDocument,
    Organization,
    PersonalAccessToken,
    Profile,
    Query,
    RoutedScoredChunk,
    ScoredChunk,
    Shelf,
    Tag,
)

DocumentType = Literal["article", "document"]
# The DB's application_auth_method enum still has "api_key" and "certificate" values (the former
# vestigial after api_key moved to personal access tokens — see migration 0010 — the latter never
# built), so a later migration doesn't need to touch this column, but this Literal only widens once
# a method actually has issuance/verification support.
ApplicationAuthMethod = Literal["oauth_client_credentials", "oauth_authorization_code"]


class OrgResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    # The resolved permission set for the *current* identity in this org (PermissionService),
    # replacing the old bare role string — the frontend checks e.g.
    # permissions.includes("applications:write") instead of role === "admin".
    permissions: list[str]

    @classmethod
    def from_entity(cls, organization: Organization, permissions: list[str]) -> "OrgResponse":
        return cls(
            id=organization.id,
            name=organization.name,
            slug=organization.slug,
            description=organization.description,
            permissions=permissions,
        )


class OrgInviteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1)
    # No default — unlike the old fixed 3-value role, profiles are custom per org, so there's no
    # guaranteed non-admin profile to fall back to. The inviter must pick one of this org's
    # existing profiles explicitly.
    profile_id: UUID


class OrgMemberProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID


class MeUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    email: str = Field(min_length=1)


class MeUsernameUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1)
    current_password: str = Field(min_length=1)


class OrgMemberResponse(BaseModel):
    identity_id: UUID
    username: str
    email: str | None
    name: str
    profile_id: UUID
    profile_name: str
    profile_is_admin: bool


class CategoryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None
    parent_id: UUID | None = None


class CategoryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None


class PaginationQuery(BaseModel):
    """Shared shape for every paginated list endpoint (documents, ...)."""

    limit: int = Field(default=100, gt=0, le=500)
    offset: int = Field(default=0, ge=0)
    sort: str = "-created_at"
    category_id: UUID | None = None
    shelf_id: UUID | None = None
    type: str | None = None


class LimitOffsetQuery(BaseModel):
    """Shared shape for list endpoints that only need limit/offset, no sort/filter (chunks,
    ingestion jobs, query history)."""

    limit: int = Field(default=100, gt=0, le=500)
    offset: int = Field(default=0, ge=0)


class CategoryResponse(BaseModel):
    id: UUID
    org_id: UUID
    parent_id: UUID | None
    name: str
    slug: str
    description: str | None
    created_at: datetime
    last_modified_at: datetime

    @classmethod
    def from_entity(cls, category: Category) -> "CategoryResponse":
        return cls(
            id=category.id,
            org_id=category.org_id,
            parent_id=category.parent_id,
            name=category.name,
            slug=category.slug,
            description=category.description,
            created_at=category.created_at,
            last_modified_at=category.last_modified_at,
        )


class DocumentResponse(BaseModel):
    id: UUID
    org_id: UUID
    category_id: UUID | None
    owner_id: UUID
    source_id: UUID | None
    title: str
    type: str
    description: str | None
    file_type: str
    status: str
    error_message: str | None
    size_bytes: int | None
    chunk_count: int | None
    split_group_id: UUID | None = None
    split_part: int | None = None
    split_total: int | None = None
    indexed_at: datetime | None
    created_at: datetime
    # Only populated by GET /documents/<id> (the Item page's single-document fetch) — omitted from
    # the list endpoint to avoid an aggregate join per row on every Browse/Category page load.
    retrieval_count: int | None = None
    avg_similarity: float | None = None

    @classmethod
    def from_entity(
        cls, document: Document, retrieval_count: int | None = None, avg_similarity: float | None = None
    ) -> "DocumentResponse":
        return cls(
            id=document.id,
            org_id=document.org_id,
            category_id=document.category_id,
            owner_id=document.owner_id,
            source_id=document.source_id,
            title=document.title,
            type=document.type,
            description=document.description,
            file_type=document.file_type,
            status=document.status,
            error_message=document.error_message,
            size_bytes=document.size_bytes,
            chunk_count=document.chunk_count,
            split_group_id=document.split_group_id,
            split_part=document.split_part,
            split_total=document.split_total,
            indexed_at=document.indexed_at,
            created_at=document.created_at,
            retrieval_count=retrieval_count,
            avg_similarity=avg_similarity,
        )


class ChunkResponse(BaseModel):
    id: UUID
    document_id: UUID
    ordinal: int
    content: str
    token_count: int
    created_at: datetime

    @classmethod
    def from_entity(cls, chunk: Chunk) -> "ChunkResponse":
        return cls(
            id=chunk.id,
            document_id=chunk.document_id,
            ordinal=chunk.ordinal,
            content=chunk.content,
            token_count=chunk.token_count,
            created_at=chunk.created_at,
        )


class JobStatusResponse(BaseModel):
    status: str
    error: str | None
    document_id: str | None
    cancel_requested: bool = False
    # Populated only for an ingestion that split an oversized PDF into multiple parts
    # (PdfSplitIngestionService) — parts_total == 1 (the default single-document case) means
    # document_id above is the whole story; parts_total > 1 means document_ids lists every
    # successfully-ingested part and parts_failed may be > 0 even though the job itself completed.
    document_ids: list[str] = []
    parts_total: int | None = None
    parts_completed: int = 0
    parts_failed: int = 0


class DocumentRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)


class DocumentMetadataUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: UUID | None = None
    type: DocumentType


class CrawlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1)
    max_pages: int = Field(default=1, gt=0, le=WEB_CRAWL_MAX_PAGES_LIMIT)
    scope_prefix: str | None = Field(default=None, min_length=1)
    category_id: UUID | None = None


class CrawlPageStatus(BaseModel):
    status: str
    document_id: str | None
    error: str | None


class CrawlJobStatusResponse(BaseModel):
    status: str
    seed_url: str
    error: str | None
    pages: dict[str, CrawlPageStatus]


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    top_k: int = Field(default=DEFAULT_TOP_K, gt=0, le=100)


class ScoredChunkResponse(BaseModel):
    id: UUID
    document_id: UUID
    ordinal: int
    content: str
    score: float

    @classmethod
    def from_entity(cls, chunk: ScoredChunk) -> "ScoredChunkResponse":
        return cls(
            id=chunk.id,
            document_id=chunk.document_id,
            ordinal=chunk.ordinal,
            content=chunk.content,
            score=chunk.score,
        )


class RoutedScoredChunkResponse(BaseModel):
    category_id: UUID
    category_name: str
    id: UUID
    document_id: UUID
    ordinal: int
    content: str
    score: float
    # Search results need more than category/score to render — the caller batch-fetches the
    # referenced documents once and passes these in, rather than this response doing N+1 lookups.
    document_title: str
    document_type: str

    @classmethod
    def from_entity(cls, routed: RoutedScoredChunk, document_title: str, document_type: str) -> "RoutedScoredChunkResponse":
        return cls(
            category_id=routed.category_id,
            category_name=routed.category_name,
            id=routed.chunk.id,
            document_id=routed.chunk.document_id,
            ordinal=routed.chunk.ordinal,
            content=routed.chunk.content,
            score=routed.chunk.score,
            document_title=document_title,
            document_type=document_type,
        )


class EmbeddingModelListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    api_key: str | None = Field(default=None, min_length=1)
    base_url: str | None = Field(default=None, min_length=1)


class EmbeddingProviderConfigUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = Field(min_length=1)
    api_key: str | None = Field(default=None, min_length=1)
    base_url: str | None = Field(default=None, min_length=1)
    dimensions: int = Field(gt=0)
    chunk_size: int = Field(default=DEFAULT_CHUNK_SIZE, gt=0)
    chunk_overlap: int = Field(default=DEFAULT_CHUNK_OVERLAP, ge=0)


class EmbeddingProviderConfigResponse(BaseModel):
    provider: str
    enabled: bool
    configured: bool
    locked: bool
    locked_by_other: bool
    chunk_count: int
    model: str | None
    base_url: str | None
    dimensions: int | None
    chunk_size: int
    chunk_overlap: int
    updated_at: datetime | None
    active_provider: str | None

    @classmethod
    def from_status(cls, status: EmbeddingProviderConfigStatus) -> "EmbeddingProviderConfigResponse":
        return cls(
            provider=status.provider,
            enabled=status.enabled,
            configured=status.configured,
            locked=status.locked,
            locked_by_other=status.locked_by_other,
            chunk_count=status.chunk_count,
            model=status.model,
            base_url=status.base_url,
            dimensions=status.dimensions,
            chunk_size=status.chunk_size,
            chunk_overlap=status.chunk_overlap,
            updated_at=status.updated_at,
            active_provider=status.active_provider,
        )


class ShelfCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None


class ShelfUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None


class ShelfDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID


class ShelfAccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID


class ShelfResponse(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    slug: str
    description: str | None
    is_default: bool
    document_count: int
    member_count: int
    created_at: datetime
    last_modified_at: datetime

    @classmethod
    def from_entity(cls, shelf: Shelf, document_count: int, member_count: int) -> "ShelfResponse":
        return cls(
            id=shelf.id,
            org_id=shelf.org_id,
            name=shelf.name,
            slug=shelf.slug,
            description=shelf.description,
            is_default=shelf.is_default,
            document_count=document_count,
            member_count=member_count,
            created_at=shelf.created_at,
            last_modified_at=shelf.last_modified_at,
        )


class ShelfSummaryResponse(BaseModel):
    """A member's shelf-access badge only needs id/name/slug, not the full ShelfResponse (which
    also computes document/member counts) — kept separate to avoid an admin-only members-page
    load computing counts for shelves it never displays."""

    id: UUID
    name: str
    slug: str

    @classmethod
    def from_entity(cls, shelf: Shelf) -> "ShelfSummaryResponse":
        return cls(id=shelf.id, name=shelf.name, slug=shelf.slug)


class TagCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)


class DocumentTagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag_id: UUID


class TagResponse(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    created_at: datetime

    @classmethod
    def from_entity(cls, tag: Tag) -> "TagResponse":
        return cls(id=tag.id, org_id=tag.org_id, name=tag.name, created_at=tag.created_at)


class IngestionJobResponse(BaseModel):
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

    @classmethod
    def from_entity(cls, job: IngestionJob) -> "IngestionJobResponse":
        return cls(
            id=job.id,
            org_id=job.org_id,
            source_id=job.source_id,
            document_id=job.document_id,
            type=job.type,
            status=job.status,
            error_message=job.error_message,
            items_processed=job.items_processed,
            triggered_by=job.triggered_by,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )


class QueryHistoryResponse(BaseModel):
    id: UUID
    org_id: UUID
    user_id: UUID | None
    query_text: str
    latency_ms: int | None
    result_count: int | None
    created_at: datetime

    @classmethod
    def from_entity(cls, query: Query) -> "QueryHistoryResponse":
        return cls(
            id=query.id,
            org_id=query.org_id,
            user_id=query.user_id,
            query_text=query.query_text,
            latency_ms=query.latency_ms,
            result_count=query.result_count,
            created_at=query.created_at,
        )


class MostRetrievedDocumentResponse(BaseModel):
    document_id: UUID
    title: str
    retrieval_count: int
    avg_similarity: float

    @classmethod
    def from_entity(cls, entity: MostRetrievedDocument) -> "MostRetrievedDocumentResponse":
        return cls(
            document_id=entity.document_id,
            title=entity.title,
            retrieval_count=entity.retrieval_count,
            avg_similarity=entity.avg_similarity,
        )


class DashboardStatsResponse(BaseModel):
    document_count: int
    chunk_count: int
    queries_last_30d: int
    avg_query_latency_ms: float | None
    most_retrieved_documents: list[MostRetrievedDocumentResponse]

    @classmethod
    def from_entity(cls, stats: DashboardStats) -> "DashboardStatsResponse":
        return cls(
            document_count=stats.document_count,
            chunk_count=stats.chunk_count,
            queries_last_30d=stats.queries_last_30d,
            avg_query_latency_ms=stats.avg_query_latency_ms,
            most_retrieved_documents=[
                MostRetrievedDocumentResponse.from_entity(document) for document in stats.most_retrieved_documents
            ],
        )


class ApplicationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None
    auth_method: ApplicationAuthMethod = "oauth_client_credentials"
    # Only meaningful/required for oauth_client_credentials — an existing org member whose profile
    # this application's tokens inherit permissions from.
    execute_as_identity_id: UUID | None = None
    # Only meaningful/required for oauth_authorization_code — the callback URL(s) this app is
    # allowed to redirect to after a member consents.
    redirect_uris: list[str] = []
    # Whether this application may reach the MCP server at all — uniform across both auth methods,
    # independent of the auth-method radio selection above (see api/mcp_server/).
    mcp_access: bool = False
    # Symmetric channel flag for the REST API side — defaults true since that's this app's
    # original, primary purpose (see migration 0009).
    api_access: bool = True


class ApplicationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None


class ApplicationResponse(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    description: str | None
    auth_method: str
    status: str
    execute_as_identity_id: UUID | None
    mcp_access: bool
    api_access: bool
    created_at: datetime
    last_modified_at: datetime
    revoked_at: datetime | None

    @classmethod
    def from_entity(cls, application: Application) -> "ApplicationResponse":
        return cls(
            id=application.id,
            org_id=application.org_id,
            name=application.name,
            description=application.description,
            auth_method=application.auth_method,
            status=application.status,
            execute_as_identity_id=application.execute_as_identity_id,
            mcp_access=application.mcp_access,
            api_access=application.api_access,
            created_at=application.created_at,
            last_modified_at=application.last_modified_at,
            revoked_at=application.revoked_at,
        )


class ProfileCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None
    permissions: list[str] = Field(min_length=1)


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None
    # A request against a system profile (Admin/Contributor/Viewer — see Profile.is_system) is
    # rejected outright by ProfileService.update before this field is even consulted; the plain
    # default just keeps this field required for every other profile without a separate shape.
    permissions: list[str] = []


class ProfileResponse(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    description: str | None
    is_admin: bool
    is_system: bool
    permissions: list[str]
    created_at: datetime
    last_modified_at: datetime

    @classmethod
    def from_entity(cls, profile: Profile, permissions: list[str]) -> "ProfileResponse":
        return cls(
            id=profile.id,
            org_id=profile.org_id,
            name=profile.name,
            description=profile.description,
            is_admin=profile.is_admin,
            is_system=profile.is_system,
            permissions=permissions,
            created_at=profile.created_at,
            last_modified_at=profile.last_modified_at,
        )


class ApplicationOAuthClientSecretResponse(ApplicationResponse):
    """client_credentials' one-time-reveal counterpart — client_id is just application.id (already
    in the base response), client_secret is the one-time-reveal secret (returned only from
    create/rotate, never persisted in raw form)."""

    client_id: UUID
    client_secret: str

    @classmethod
    def from_application_entity(cls, application: Application, client_secret: str) -> "ApplicationOAuthClientSecretResponse":
        return cls(
            **ApplicationResponse.from_entity(application).model_dump(),
            client_id=application.id,
            client_secret=client_secret,
        )


class PersonalAccessTokenCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    # Same channel-flag concept as Application.mcp_access — opt-in, since REST access is this
    # entity's unconditional purpose (no api_access toggle exists for it at all).
    mcp_access: bool = False


class PersonalAccessTokenResponse(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    token_prefix: str
    mcp_access: bool
    created_at: datetime
    last_used_at: datetime | None

    @classmethod
    def from_entity(cls, token: PersonalAccessToken) -> "PersonalAccessTokenResponse":
        return cls(
            id=token.id,
            org_id=token.org_id,
            name=token.name,
            token_prefix=token.token_prefix,
            mcp_access=token.mcp_access,
            created_at=token.created_at,
            last_used_at=token.last_used_at,
        )


class PersonalAccessTokenSecretResponse(PersonalAccessTokenResponse):
    """Same shape as PersonalAccessTokenResponse plus the one-time-reveal raw token — returned only
    from create, never from a plain GET, since the raw value isn't persisted anywhere (only its
    HMAC hash is)."""

    token: str

    @classmethod
    def from_token_entity(cls, token: PersonalAccessToken, raw_token: str) -> "PersonalAccessTokenSecretResponse":
        return cls(**PersonalAccessTokenResponse.from_entity(token).model_dump(), token=raw_token)


class MCPSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rag_read_enabled: bool
    object_read_enabled: bool
    object_write_enabled: bool


class MCPSettingsResponse(BaseModel):
    org_id: UUID
    rag_read_enabled: bool
    object_read_enabled: bool
    object_write_enabled: bool
    last_modified_at: datetime

    @classmethod
    def from_entity(cls, settings: MCPSettings) -> "MCPSettingsResponse":
        return cls(
            org_id=settings.org_id,
            rag_read_enabled=settings.rag_read_enabled,
            object_read_enabled=settings.object_read_enabled,
            object_write_enabled=settings.object_write_enabled,
            last_modified_at=settings.last_modified_at,
        )


