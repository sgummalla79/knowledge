"""initial schema: the multi-tenant data model, as a clean baseline

This app has no production deployment yet — see this repo's CLAUDE.md — so rather than carry an
incremental migration history transforming the old single-tenant "libraries" schema into the new
multi-tenant one (organizations/identities+org_members-with-roles/embedding_models/sources/categories/shelves/
documents/chunks/tags/ingestion_jobs/queries), this is a single clean baseline that creates the
target schema directly. There is no `libraries` table, no `library_id`/`chunk_index` anywhere, and
`documents.status`/`embedding_models.status` are real enums from day one — nothing here is shaped
around preserving old data or keeping old application code running, because there is no old data
and the application layer (routes/services/MCP server) is being rewritten separately to match this
schema, not the other way around.

Source of truth is the "Knowledge data library pages" DataModel-Spec.dc.html / schema.sql this app
was designed against, with these deliberate, documented deviations:

- `embed_provider` uses this app's actual three registry values (voyage/ollama/openai_compatible —
  see app/infrastructure/embeddings/registry.py), not the spec's literal openai/cohere/voyage/
  self_hosted/custom list, which doesn't match what this app can construct a client for.
- `chunks.embedding` is dimensionless (`vector()`), not the spec's fixed `vector(1536)` — per-org
  "bring your own embedding model" means different orgs (and a mid-reindex org) can have different
  `dimensions`; a single fixed-width column can't represent that. A genuinely correct multi-
  dimension ANN index strategy is still open follow-up work; for now this mirrors how the old
  schema handled a changing-but-singular embedding width (runtime `ALTER COLUMN TYPE`, see
  ChunkRepository.resize_embedding_column).
- `chunks.content_tsv` (generated `tsvector` + GIN index) is added even though the spec omits it —
  it's the sparse half of this app's hybrid (dense+sparse RRF) search.
- `documents` keeps `file_type` (technical upload format — pdf/md/txt/html, drives parser
  selection; distinct from the spec's `type` classification enum), `content_hash`, `size_bytes`,
  `chunk_count`, `raw_file_bytes`, `split_group_id`/`split_part`/`split_total`, `error_message`
  alongside the spec's `content_uri` — real features (parser dispatch, dedup, retry-on-failure,
  oversized-PDF splitting) the spec's author wasn't accounting for. `content_uri` is nullable and,
  for now, unpopulated — no blob storage exists yet, uploads still live in `raw_file_bytes`.
- `embedding_models.chunk_size`/`chunk_overlap` stay on that table (the spec has no column for
  them at all) rather than moving to `sources` — chunking config is resolved alongside
  provider/model/dimensions in one repository call today; splitting it across two tables would be
  a real ingestion-service behavior change, not a schema decision.
- The `shelf_gated_read` policy is RESTRICTIVE, not the spec's three separate PERMISSIVE policies
  (`tenant_isolation`/`admin_bypass_shelf_gate`/`shelf_gated_read` on `documents`). Postgres ORs
  permissive policies together, so as literally written in the spec, satisfying `tenant_isolation`
  alone (same org) would be sufficient to see a document — shelf checks would never actually
  restrict anything, contradicting the spec's own prose. Merging the admin-bypass and shelf-access
  checks into one RESTRICTIVE policy makes it actually AND against `tenant_isolation` (same org AND
  (admin OR has shelf access)).
- This app previously carried its own OAuth2 client registry (`applications`/`refresh_tokens`/
  `authorization_codes`) and three global settings tables (`search_settings`/`web_crawl_settings`/
  `router_settings`), none of which are part of the spec. Both have been removed entirely: the
  three settings tables' values are now fixed `DEFAULT_*` constants in app/constants.py instead of
  admin-configurable per-org rows.
- `users` is split into `identities` (a person: email — globally unique, not per-org — name,
  password hash; wholly org-independent) and `org_members` (which orgs an identity belongs to and
  with what role). This app owns its own org/membership model rather than delegating it to a
  third-party IdP (Auth0 can't hand back an `org_id`; a self-hosted multi-tenant IdP like Zitadel
  models orgs as a IdP-level concept, which is more than this needs) — mirrors how
  platform.claude/platform.openai split "prove who this person is" from "which orgs do they
  belong to": one identity can belong to many orgs and switch between them, each with its own role.
  Every column that used to point at `users.id` (`created_by`/`owner_id`/`triggered_by`/etc.) now
  points at `identities.id` — those always meant "which person," not "which membership."
- RLS is enabled and policies are created (matching the spec's list of RLS tables) but is still
  practically inert: this app's single Postgres role (POSTGRES_USER) both runs migrations (owns
  every table) and serves every app query, and Postgres exempts table owners from their own RLS
  policies unless FORCE ROW LEVEL SECURITY is set (it isn't). Real enforcement needs a later phase
  that introduces a restricted, non-owner role and wires `SET LOCAL app.org_id`/`app.user_id` per
  request.

Every table id is a plain `uuid` column with no server-side default — ids are always supplied by
the application (`default=uuid.uuid4` in the ORM), matching this app's established convention.

Revision ID: 0001
Revises:
Create Date: 2026-08-17

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ENUM, JSONB, TSVECTOR, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

org_plan = ENUM("free", "team", "enterprise", name="org_plan", create_type=False)
user_role = ENUM("admin", "contributor", "viewer", name="user_role", create_type=False)
embed_provider = ENUM("voyage", "ollama", "openai_compatible", name="embed_provider", create_type=False)
embed_model_status = ENUM("active", "retired", "disabled", name="embed_model_status", create_type=False)
source_type = ENUM("upload", "url", "connector", name="source_type", create_type=False)
source_status = ENUM("active", "paused", "error", name="source_status", create_type=False)
ingestion_type = ENUM("upload", "crawl", "resync", "reindex", name="ingestion_type", create_type=False)
ingestion_status = ENUM("queued", "processing", "indexed", "failed", name="ingestion_status", create_type=False)
document_type = ENUM(
    "article", "document", name="document_type", create_type=False
)
document_status = ENUM(
    "processing", "indexed", "failed", "archived", name="document_status", create_type=False
)

_ALL_ENUMS = (
    org_plan,
    user_role,
    embed_provider,
    embed_model_status,
    source_type,
    source_status,
    ingestion_type,
    ingestion_status,
    document_type,
    document_status,
)

_RLS_TABLES = (
    "org_members",
    "embedding_models",
    "sources",
    "categories",
    "documents",
    "ingestion_jobs",
    "tags",
    "chunks",
    "queries",
    "shelves",
)


def upgrade():
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    for enum in _ALL_ENUMS:
        enum.create(bind, checkfirst=True)

    # ── Tenancy & access ────────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("slug", sa.String, nullable=False, unique=True),
        sa.Column("plan", org_plan, nullable=False, server_default="free"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),  # fk -> identities, added below
        sa.Column("last_modified_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_modified_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "identities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("password_hash", sa.String, nullable=False),
        sa.Column("must_change_password", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_modified_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="uq_identities_email"),
    )
    op.create_foreign_key("organizations_created_by_fkey", "organizations", "identities", ["created_by"], ["id"])
    op.create_foreign_key("organizations_last_modified_by_fkey", "organizations", "identities", ["last_modified_by"], ["id"])

    # ── Org membership: which orgs an identity belongs to, and with what role ──────────────────
    # Deliberately separate from `identities` (see module docstring) — one identity can hold a
    # membership (and role) in several orgs and switch between them, the same split
    # platform.claude/platform.openai make between "who is this person" and "which workspace are
    # they acting in right now."
    op.create_table(
        "org_members",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("identity_id", UUID(as_uuid=True), sa.ForeignKey("identities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="viewer"),
        sa.Column("invited_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("last_modified_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_modified_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "identity_id", name="uq_org_members_org_id_identity_id"),
    )
    op.create_index("ix_org_members_identity_id", "org_members", ["identity_id"])

    # ── Embedding models (bring your own, per org) ─────────────────────
    op.create_table(
        "embedding_models",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", embed_provider, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("model_identifier", sa.String, nullable=False),
        sa.Column("dimensions", sa.Integer, nullable=False),
        sa.Column("endpoint_url", sa.String, nullable=True),
        sa.Column("api_key", sa.String, nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("status", embed_model_status, nullable=False, server_default="disabled"),
        sa.Column("chunk_size", sa.Integer, nullable=False),
        sa.Column("chunk_overlap", sa.Integer, nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("last_modified_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_modified_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("not is_default or status = 'active'", name="embedding_models_default_is_active"),
    )
    op.create_index(
        "embedding_models_one_active_per_org", "embedding_models", ["org_id"],
        unique=True, postgresql_where=sa.text("status = 'active'"),
    )
    op.execute(
        """
        create or replace function guard_embedding_model_change() returns trigger as $$
        begin
          if TG_OP = 'DELETE' then
            if exists (select 1 from chunks where embedding_model_id = old.id) then
              raise exception 'Cannot delete embedding model %: chunks reference it', old.id;
            end if;
            return old;
          end if;
          if TG_OP = 'UPDATE' and new.status = 'disabled' and old.status <> 'disabled' then
            if exists (select 1 from chunks where embedding_model_id = old.id) then
              raise exception 'Cannot disable embedding model %: chunks reference it — it will move to retired instead', old.id;
            end if;
          end if;
          return new;
        end;
        $$ language plpgsql
        """
    )

    # ── Sources & categories & shelves ──────────────────────────────────
    op.create_table(
        "sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", source_type, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("config", JSONB, nullable=False, server_default="{}"),
        sa.Column("api_key_hash", sa.String, nullable=True),
        sa.Column("status", source_status, nullable=False, server_default="active"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("last_modified_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_modified_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sources_org_id", "sources", ["org_id"])

    op.create_table(
        "categories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("slug", sa.String, nullable=False),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("description_embedding", Vector(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("last_modified_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_modified_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "slug", name="uq_categories_org_id_slug"),
    )
    op.create_index("ix_categories_org_id", "categories", ["org_id"])
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])

    op.create_table(
        "shelves",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("slug", sa.String, nullable=False),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("last_modified_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_modified_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "slug", name="uq_shelves_org_id_slug"),
    )
    op.create_index("ix_shelves_org_id", "shelves", ["org_id"])

    # ── Content ──────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category_id", UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("type", document_type, nullable=False),
        sa.Column("content_uri", sa.String, nullable=True),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("status", document_status, nullable=False, server_default="processing"),
        # Extensions beyond the spec (see module docstring): parser selection, dedup, retry,
        # oversized-PDF splitting, chunk-count reporting.
        sa.Column("file_type", sa.String, nullable=False),
        sa.Column("content_hash", sa.String, nullable=False),
        sa.Column("raw_file_bytes", sa.LargeBinary, nullable=True),
        sa.Column("error_message", sa.String, nullable=True),
        sa.Column("size_bytes", sa.Integer, nullable=True),
        sa.Column("chunk_count", sa.Integer, nullable=True),
        sa.Column("split_group_id", UUID(as_uuid=True), nullable=True),
        sa.Column("split_part", sa.Integer, nullable=True),
        sa.Column("split_total", sa.Integer, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("last_modified_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_modified_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_documents_org_id", "documents", ["org_id"])
    op.create_index("ix_documents_source_id", "documents", ["source_id"])
    op.create_index("ix_documents_category_id", "documents", ["category_id"])
    op.create_index("ix_documents_split_group_id", "documents", ["split_group_id"], postgresql_where=sa.text("split_group_id IS NOT NULL"))

    op.create_table(
        "document_shelves",
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shelf_id", UUID(as_uuid=True), sa.ForeignKey("shelves.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("document_id", "shelf_id"),
    )
    op.create_index("ix_document_shelves_shelf_id", "document_shelves", ["shelf_id"])

    op.create_table(
        "user_shelf_access",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("identities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shelf_id", UUID(as_uuid=True), sa.ForeignKey("shelves.id", ondelete="CASCADE"), nullable=False),
        sa.Column("granted_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "shelf_id"),
    )
    op.create_index("ix_user_shelf_access_user_id", "user_shelf_access", ["user_id"])

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type", ingestion_type, nullable=False),
        sa.Column("status", ingestion_status, nullable=False, server_default="queued"),
        sa.Column("error_message", sa.String, nullable=True),
        sa.Column("items_processed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("triggered_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ingestion_jobs_org_id", "ingestion_jobs", ["org_id", "status"])

    op.create_table(
        "tags",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "name", name="uq_tags_org_id_name"),
    )

    op.create_table(
        "document_tags",
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag_id", UUID(as_uuid=True), sa.ForeignKey("tags.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("document_id", "tag_id"),
    )

    # ── Retrieval ────────────────────────────────────────────────────────
    op.create_table(
        "chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("content", sa.String, nullable=False),
        sa.Column(
            "content_tsv", TSVECTOR, sa.Computed("to_tsvector('english', content)", persisted=True), nullable=False
        ),
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.Column(
            "embedding_model_id", UUID(as_uuid=True), sa.ForeignKey("embedding_models.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_org_id", "chunks", ["org_id"])
    op.create_index("ix_chunks_content_tsv_gin", "chunks", ["content_tsv"], postgresql_using="gin")
    # No HNSW index here — pgvector requires a fixed-width vector column to build one, and
    # `embedding` is deliberately dimensionless from the start (see module docstring: no baked-in
    # default provider/dimension anymore, per-org "bring your own model"). ChunkRepository.
    # resize_embedding_column() creates it (DROP INDEX IF EXISTS + CREATE INDEX, already
    # idempotent to a missing index) the first time an org actually configures a model.
    op.execute(
        """
        create trigger embedding_models_guard
          before update or delete on embedding_models
          for each row execute function guard_embedding_model_change()
        """
    )

    op.create_table(
        "queries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("identities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("query_text", sa.String, nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("result_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_queries_org_id_created_at", "queries", ["org_id", "created_at"])

    op.create_table(
        "query_results",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("query_id", UUID(as_uuid=True), sa.ForeignKey("queries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", UUID(as_uuid=True), sa.ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("similarity_score", sa.Float, nullable=False),
    )
    op.create_index("ix_query_results_query_id", "query_results", ["query_id"])

    # ── Row-level security (see module docstring: inert until a restricted role exists) ────────
    for table in _RLS_TABLES:
        op.execute(f"alter table {table} enable row level security")
        op.execute(f"create policy tenant_isolation on {table} using (org_id = current_setting('app.org_id')::uuid)")

    op.execute("alter table document_shelves enable row level security")
    op.execute(
        """
        create policy tenant_isolation on document_shelves using (
          exists (select 1 from documents d where d.id = document_id and d.org_id = current_setting('app.org_id')::uuid)
        )
        """
    )
    op.execute("alter table user_shelf_access enable row level security")
    op.execute(
        """
        create policy tenant_isolation on user_shelf_access using (
          exists (select 1 from shelves s where s.id = shelf_id and s.org_id = current_setting('app.org_id')::uuid)
        )
        """
    )
    op.execute(
        """
        create policy shelf_gated_read on documents
          as restrictive
          for select using (
            exists (
              select 1 from org_members m
              where m.identity_id = current_setting('app.user_id')::uuid
                and m.org_id = current_setting('app.org_id')::uuid
                and m.role = 'admin'
            )
            or exists (
              select 1 from document_shelves ds
              join user_shelf_access usa on usa.shelf_id = ds.shelf_id
              where ds.document_id = documents.id
                and usa.user_id = current_setting('app.user_id')::uuid
            )
          )
        """
    )


def downgrade():
    # RLS policies first — shelf_gated_read on `documents` references user_shelf_access/
    # document_shelves, which blocks dropping those tables while it still exists.
    op.execute("drop policy shelf_gated_read on documents")
    op.execute("drop policy tenant_isolation on user_shelf_access")
    op.execute("drop policy tenant_isolation on document_shelves")
    for table in reversed(_RLS_TABLES):
        op.execute(f"drop policy tenant_isolation on {table}")

    op.drop_table("query_results")
    op.drop_table("queries")
    op.drop_table("chunks")
    op.drop_table("document_tags")
    op.drop_table("tags")
    op.drop_table("ingestion_jobs")
    op.drop_table("user_shelf_access")
    op.drop_table("document_shelves")
    op.drop_table("documents")
    op.drop_table("shelves")
    op.drop_table("categories")
    op.drop_table("sources")
    op.drop_table("embedding_models")
    op.execute("drop function if exists guard_embedding_model_change()")
    op.drop_constraint("organizations_last_modified_by_fkey", "organizations", type_="foreignkey")
    op.drop_constraint("organizations_created_by_fkey", "organizations", type_="foreignkey")
    op.drop_table("org_members")
    op.drop_table("identities")
    op.drop_table("organizations")

    bind = op.get_bind()
    for enum in reversed(_ALL_ENUMS):
        enum.drop(bind, checkfirst=True)
