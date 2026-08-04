import { ErDiagram } from '../components/ErDiagram'

const DIAGRAM_SOURCE = `erDiagram
    LIBRARIES ||--o{ DOCUMENTS : contains
    LIBRARIES ||--o{ CHUNKS : contains
    DOCUMENTS ||--o{ CHUNKS : "split into"
    APPLICATIONS ||--o{ REFRESH_TOKENS : issues
    APPLICATIONS ||--o{ AUTHORIZATION_CODES : issues

    LIBRARIES {
        uuid id PK
        string name UK
        string description
        int document_count
        int chunk_count
        timestamp last_ingested_at
        timestamp created_at
        timestamp updated_at
    }
    DOCUMENTS {
        uuid id PK
        uuid library_id FK
        string source_filename
        string file_type
        string content_hash
        string status
        bytea raw_file_bytes
        string error_message
        int size_bytes
        int chunk_count
        uuid split_group_id
        int split_part
        int split_total
        timestamp ingested_at
        timestamp created_at
    }
    CHUNKS {
        uuid id PK
        uuid document_id FK
        uuid library_id FK
        int chunk_index
        string content
        tsvector content_tsv
        vector embedding
        timestamp created_at
    }
    EMBEDDING_SETTINGS {
        uuid id PK
        string provider
        string model
        string api_key
        string base_url
        int dimensions
        int chunk_size
        int chunk_overlap
        timestamp created_at
        timestamp updated_at
    }
    EMBEDDING_PROVIDER_SETTINGS {
        uuid id PK
        string provider UK
        bool enabled
        timestamp updated_at
    }
    SEARCH_SETTINGS {
        uuid id PK
        int dense_k
        int sparse_k
        int rrf_k
        timestamp created_at
        timestamp updated_at
    }
    WEB_CRAWL_SETTINGS {
        uuid id PK
        string user_agent
        timestamp created_at
        timestamp updated_at
    }
    USERS {
        uuid id PK
        string username UK
        string password_hash
        bool must_change_password
        timestamp created_at
        timestamp updated_at
    }
    APPLICATIONS {
        uuid id PK
        string name UK
        string client_secret_hash
        string allowed_scopes
        string redirect_uris
        timestamp created_at
    }
    REFRESH_TOKENS {
        uuid id PK
        uuid application_id FK
        string token_hash UK
        string scope
        timestamp created_at
        timestamp expires_at
        timestamp last_used_at
        timestamp revoked_at
    }
    AUTHORIZATION_CODES {
        uuid id PK
        uuid application_id FK
        string code_hash UK
        string redirect_uri
        string code_challenge
        string code_challenge_method
        string scope
        timestamp created_at
        timestamp expires_at
        timestamp used_at
    }
`

export function DataModelPage() {
  return (
    <div className="settings-wide">
      <h1>Data Model</h1>
      <p className="subtitle">knowledge-api — PostgreSQL 16 + pgvector schema reference. Reflects migrations through <code>0015</code>.</p>

      <div className="docs-layout">
        <nav className="docs-nav">
          <a href="#diagram">Overview</a>
          <div className="docs-nav-group">Tables</div>
          <a href="#libraries">libraries</a>
          <a href="#documents">documents</a>
          <a href="#chunks">chunks</a>
          <a href="#embedding_provider_settings">embedding_provider_settings</a>
          <a href="#search_settings">search_settings</a>
          <a href="#web_crawl_settings">web_crawl_settings</a>
          <a href="#users">users</a>
          <a href="#applications">applications</a>
          <a href="#refresh_tokens">refresh_tokens</a>
          <a href="#authorization_codes">authorization_codes</a>
          <div className="docs-nav-group">Reference</div>
          <a href="#indexes">Indexes</a>
        </nav>

        <div className="docs-main">
          <h2 id="diagram">Entity relationships</h2>
          <p className="lede">
            <code>embedding_provider_settings</code>, <code>search_settings</code>, and{' '}
            <code>web_crawl_settings</code> carry no foreign keys — they're global,
            application-wide configuration (singleton or small lookup tables), not scoped to a
            library.
          </p>

          <ErDiagram source={DIAGRAM_SOURCE} />

          <div className="legend" style={{ marginTop: 14 }}>
            <span className="legend-item"><span className="col-badge pk">PK</span> primary key</span>
            <span className="legend-item"><span className="col-badge fk">FK</span> foreign key</span>
            <span className="legend-item"><span className="col-badge uk">UK</span> unique</span>
            <span className="legend-item"><span className="col-badge gen">GEN</span> generated column</span>
          </div>

          <h2 id="libraries" style={{ marginTop: 40 }}>Tables</h2>

          <div className="endpoint" id="libraries">
            <div className="endpoint-head"><span className="endpoint-path">libraries</span><span className="table-count">8 columns</span></div>
            <p className="endpoint-desc">
              A named collection of documents. Chunking/embedding config is not per-library — it's
              global (<code>embedding_provider_settings</code>) — so this table only tracks
              identity and running counts.
            </p>
            <div className="table-scroll">
              <table className="params-table">
                <thead><tr><th>Column</th><th>Type</th><th>Null</th><th>Default</th><th>Notes</th></tr></thead>
                <tbody>
                  <tr><td>id<span className="col-badge pk">PK</span></td><td>uuid</td><td>no</td><td>—</td><td></td></tr>
                  <tr><td>name<span className="col-badge uk">UK</span></td><td>string</td><td>no</td><td>—</td><td></td></tr>
                  <tr><td>description</td><td>string</td><td>yes</td><td>—</td><td></td></tr>
                  <tr><td>document_count</td><td>integer</td><td>no</td><td>0</td><td>maintained by <code>LibraryRepository.increment_counts</code></td></tr>
                  <tr><td>chunk_count</td><td>integer</td><td>no</td><td>0</td><td>maintained by <code>LibraryRepository.increment_counts</code></td></tr>
                  <tr><td>last_ingested_at</td><td>timestamptz</td><td>yes</td><td>—</td><td></td></tr>
                  <tr><td>created_at</td><td>timestamptz</td><td>no</td><td>now()</td><td></td></tr>
                  <tr><td>updated_at</td><td>timestamptz</td><td>no</td><td>now(), on update now()</td><td></td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="endpoint" id="documents">
            <div className="endpoint-head"><span className="endpoint-path">documents</span><span className="table-count">15 columns</span></div>
            <p className="endpoint-desc">One row per uploaded file within a library.</p>
            <div className="table-scroll">
              <table className="params-table">
                <thead><tr><th>Column</th><th>Type</th><th>Null</th><th>Default</th><th>Notes</th></tr></thead>
                <tbody>
                  <tr><td>id<span className="col-badge pk">PK</span></td><td>uuid</td><td>no</td><td>—</td><td></td></tr>
                  <tr><td>library_id<span className="col-badge fk">FK</span></td><td>uuid</td><td>no</td><td>—</td><td>→ libraries.id, ON DELETE CASCADE, indexed</td></tr>
                  <tr><td>source_filename</td><td>string</td><td>no</td><td>—</td><td></td></tr>
                  <tr><td>file_type</td><td>string</td><td>no</td><td>—</td><td>extension, e.g. pdf, md, txt</td></tr>
                  <tr><td>content_hash</td><td>string</td><td>no</td><td>—</td><td>SHA-256 of the uploaded bytes</td></tr>
                  <tr><td>status</td><td>string</td><td>no</td><td>"pending"</td><td>pending · processing · completed · failed</td></tr>
                  <tr><td>raw_file_bytes</td><td>bytea</td><td>yes</td><td>—</td><td>added 0008; deferred-loaded; kept only until ingestion completes so a failed document can be retried without re-upload</td></tr>
                  <tr><td>error_message</td><td>string</td><td>yes</td><td>—</td><td>added 0008; failure reason surfaced to retry callers</td></tr>
                  <tr><td>size_bytes</td><td>integer</td><td>yes</td><td>—</td><td>added 0011; set at upload time</td></tr>
                  <tr><td>chunk_count</td><td>integer</td><td>yes</td><td>—</td><td>added 0011; NULL until ingestion completes, so callers can tell "not available yet" apart from "genuinely zero chunks"</td></tr>
                  <tr><td>split_group_id</td><td>uuid</td><td>yes</td><td>—</td><td>added 0016, indexed (partial); shared by every part of an oversized PDF auto-split on ingest; NULL for an ordinary, unsplit document</td></tr>
                  <tr><td>split_part</td><td>integer</td><td>yes</td><td>—</td><td>added 0016; 1-indexed position among split_total parts</td></tr>
                  <tr><td>split_total</td><td>integer</td><td>yes</td><td>—</td><td>added 0016; total parts in this document's split_group_id</td></tr>
                  <tr><td>ingested_at</td><td>timestamptz</td><td>yes</td><td>—</td><td>set on successful completion</td></tr>
                  <tr><td>created_at</td><td>timestamptz</td><td>no</td><td>now()</td><td></td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="endpoint" id="chunks">
            <div className="endpoint-head"><span className="endpoint-path">chunks</span><span className="table-count">8 columns</span></div>
            <p className="endpoint-desc">
              The retrieval unit: one row per chunk produced from a document, holding both its
              dense vector and (via a generated column) its sparse/keyword representation.
            </p>
            <div className="table-scroll">
              <table className="params-table">
                <thead><tr><th>Column</th><th>Type</th><th>Null</th><th>Default</th><th>Notes</th></tr></thead>
                <tbody>
                  <tr><td>id<span className="col-badge pk">PK</span></td><td>uuid</td><td>no</td><td>—</td><td></td></tr>
                  <tr><td>document_id<span className="col-badge fk">FK</span></td><td>uuid</td><td>no</td><td>—</td><td>→ documents.id, ON DELETE CASCADE, indexed</td></tr>
                  <tr><td>library_id<span className="col-badge fk">FK</span></td><td>uuid</td><td>no</td><td>—</td><td>→ libraries.id, ON DELETE CASCADE, indexed; denormalized from document_id so search never needs a join</td></tr>
                  <tr><td>chunk_index</td><td>integer</td><td>no</td><td>—</td><td>position within the source document</td></tr>
                  <tr><td>content</td><td>string</td><td>no</td><td>—</td><td>chunk text</td></tr>
                  <tr><td>content_tsv<span className="col-badge gen">GEN</span></td><td>tsvector</td><td>no</td><td>to_tsvector('english', content)</td><td>added 0003, GIN-indexed for sparse search; Postgres keeps it in sync automatically</td></tr>
                  <tr><td>embedding</td><td>vector(N)</td><td>no</td><td>—</td><td>N = the active embedding_provider_settings row's dimensions; HNSW-indexed (cosine ops); resized at runtime when the active provider changes with zero existing chunks</td></tr>
                  <tr><td>created_at</td><td>timestamptz</td><td>no</td><td>now()</td><td></td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="endpoint" id="embedding_provider_settings">
            <div className="endpoint-head"><span className="endpoint-path">embedding_provider_settings</span><span className="table-count">11 columns · one row per provider</span></div>
            <p className="endpoint-desc">
              One row per provider registered in EmbeddingProviderRegistry (voyage, ollama,
              openai_compatible) — each seeded disabled/unconfigured at first app start
              (bootstrap_embedding_provider_settings). Holds that provider's connection/chunking
              config <em>and</em> whether it's the one actually used for embedding. Since the app
              embeds with a single global model, not a per-library choice, at most one row may
              have <code>enabled = true</code> at a time (enforced by{' '}
              <code>ix_embedding_provider_settings_single_enabled</code>, a partial unique index,
              in addition to EmbeddingProviderConfigService.enable()/disable()). Before migration
              0015 this was two tables — a single global "active settings" row plus a separate
              per-provider enable/disable toggle that only gated dropdown selection — merged here
              since "enabled" now means "active", making the split pointless.
            </p>
            <div className="table-scroll">
              <table className="params-table">
                <thead><tr><th>Column</th><th>Type</th><th>Null</th><th>Default</th><th>Notes</th></tr></thead>
                <tbody>
                  <tr><td>id<span className="col-badge pk">PK</span></td><td>uuid</td><td>no</td><td>—</td><td></td></tr>
                  <tr><td>provider<span className="col-badge uk">UK</span></td><td>string</td><td>no</td><td>—</td><td>the registry key itself; every lookup/route addresses a row by this, not id</td></tr>
                  <tr><td>enabled</td><td>boolean</td><td>no</td><td>false</td><td>at most one row true at a time; "false" default changed from "true" in 0015 — every provider now starts disabled until explicitly configured and enabled</td></tr>
                  <tr><td>model</td><td>string</td><td>yes</td><td>—</td><td>added 0015; free text — no whitelist</td></tr>
                  <tr><td>api_key</td><td>string</td><td>yes</td><td>—</td><td>added 0015; self-hosted providers need none</td></tr>
                  <tr><td>base_url</td><td>string</td><td>yes</td><td>—</td><td>added 0015; required for openai_compatible, optional override for ollama</td></tr>
                  <tr><td>dimensions</td><td>integer</td><td>yes</td><td>—</td><td>added 0015; caller-declared, verified live against the provider's output at save time</td></tr>
                  <tr><td>chunk_size</td><td>integer</td><td>yes</td><td>—</td><td>added 0015</td></tr>
                  <tr><td>chunk_overlap</td><td>integer</td><td>yes</td><td>—</td><td>added 0015</td></tr>
                  <tr><td>created_at</td><td>timestamptz</td><td>yes</td><td>now()</td><td>added 0015; nullable since a seeded-but-never-configured row has no meaningful creation time</td></tr>
                  <tr><td>updated_at</td><td>timestamptz</td><td>no</td><td>now(), on update now()</td><td></td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="endpoint" id="search_settings">
            <div className="endpoint-head"><span className="endpoint-path">search_settings</span><span className="table-count">6 columns · singleton</span></div>
            <p className="endpoint-desc">
              Single global row — the same singleton pattern the embedding config used before
              migration 0015 merged it into per-provider rows. Tunes hybrid (dense + sparse)
              retrieval. An absent row is not an error — retrieval falls back to defaults in{' '}
              <code>app/constants.py</code>. Reranking was removed (migration 0014) — it was
              already unreachable via the API before that.
            </p>
            <div className="table-scroll">
              <table className="params-table">
                <thead><tr><th>Column</th><th>Type</th><th>Null</th><th>Default</th><th>Notes</th></tr></thead>
                <tbody>
                  <tr><td>id<span className="col-badge pk">PK</span></td><td>uuid</td><td>no</td><td>—</td><td></td></tr>
                  <tr><td>dense_k</td><td>integer</td><td>no</td><td>—</td><td>candidates from pgvector similarity search</td></tr>
                  <tr><td>sparse_k</td><td>integer</td><td>no</td><td>—</td><td>candidates from keyword/tsvector search</td></tr>
                  <tr><td>rrf_k</td><td>integer</td><td>no</td><td>—</td><td>reciprocal rank fusion constant</td></tr>
                  <tr><td>created_at / updated_at</td><td>timestamptz</td><td>no</td><td>now()</td><td></td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="endpoint" id="web_crawl_settings">
            <div className="endpoint-head"><span className="endpoint-path">web_crawl_settings</span><span className="table-count">4 columns · singleton</span></div>
            <p className="endpoint-desc">
              Added 0012. Admin-configurable outbound User-Agent for web-page ingestion — some
              sites return 403 for the honest default identifying UA.
            </p>
            <div className="table-scroll">
              <table className="params-table">
                <thead><tr><th>Column</th><th>Type</th><th>Null</th><th>Default</th><th>Notes</th></tr></thead>
                <tbody>
                  <tr><td>id<span className="col-badge pk">PK</span></td><td>uuid</td><td>no</td><td>—</td><td></td></tr>
                  <tr><td>user_agent</td><td>string</td><td>no</td><td>—</td><td></td></tr>
                  <tr><td>created_at / updated_at</td><td>timestamptz</td><td>no</td><td>now()</td><td></td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="endpoint" id="users">
            <div className="endpoint-head"><span className="endpoint-path">users</span><span className="table-count">6 columns</span></div>
            <p className="endpoint-desc">Single default admin (dashboard login), bootstrapped on first <code>create_app()</code> call.</p>
            <div className="table-scroll">
              <table className="params-table">
                <thead><tr><th>Column</th><th>Type</th><th>Null</th><th>Default</th><th>Notes</th></tr></thead>
                <tbody>
                  <tr><td>id<span className="col-badge pk">PK</span></td><td>uuid</td><td>no</td><td>—</td><td></td></tr>
                  <tr><td>username<span className="col-badge uk">UK</span></td><td>string</td><td>no</td><td>—</td><td>bootstrapped as "admin"</td></tr>
                  <tr><td>password_hash</td><td>string</td><td>no</td><td>—</td><td></td></tr>
                  <tr><td>must_change_password</td><td>boolean</td><td>no</td><td>true</td><td>forces a real password change on first login</td></tr>
                  <tr><td>created_at / updated_at</td><td>timestamptz</td><td>no</td><td>now()</td><td></td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="endpoint" id="applications">
            <div className="endpoint-head"><span className="endpoint-path">applications</span><span className="table-count">6 columns</span></div>
            <p className="endpoint-desc">
              Registered OAuth2 clients. Admin-created ones are never reachable via the
              bearer-token JSON API (see Settings &rsaquo; Applications); MCP clients can also
              self-register via <code>POST /oauth/register</code> (RFC 7591 DCR). One fixed-id row
              (<code>DEFAULT_MCP_APPLICATION_ID</code>) is bootstrapped automatically for this
              app's own bundled MCP server and hidden from the Applications page.
            </p>
            <div className="table-scroll">
              <table className="params-table">
                <thead><tr><th>Column</th><th>Type</th><th>Null</th><th>Default</th><th>Notes</th></tr></thead>
                <tbody>
                  <tr><td>id<span className="col-badge pk">PK</span></td><td>uuid</td><td>no</td><td>—</td><td>doubles as the OAuth2 client_id</td></tr>
                  <tr><td>name<span className="col-badge uk">UK</span></td><td>string</td><td>no</td><td>—</td><td></td></tr>
                  <tr><td>client_secret_hash</td><td>string</td><td>no</td><td>—</td><td>shown once at registration/regeneration, hashed at rest</td></tr>
                  <tr><td>allowed_scopes</td><td>string</td><td>no</td><td>—</td><td>space-separated scope string, OAuth2 convention</td></tr>
                  <tr><td>redirect_uris</td><td>string</td><td>yes</td><td>—</td><td>added 0013; space-separated, needed for the authorization_code grant only</td></tr>
                  <tr><td>created_at</td><td>timestamptz</td><td>no</td><td>now()</td><td></td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="endpoint" id="refresh_tokens">
            <div className="endpoint-head"><span className="endpoint-path">refresh_tokens</span><span className="table-count">8 columns</span></div>
            <p className="endpoint-desc">
              Opaque, DB-backed, <strong>reusable</strong> (not rotated on use) refresh tokens for
              the <code>refresh_token</code> grant.
            </p>
            <div className="table-scroll">
              <table className="params-table">
                <thead><tr><th>Column</th><th>Type</th><th>Null</th><th>Default</th><th>Notes</th></tr></thead>
                <tbody>
                  <tr><td>id<span className="col-badge pk">PK</span></td><td>uuid</td><td>no</td><td>—</td><td></td></tr>
                  <tr><td>application_id<span className="col-badge fk">FK</span></td><td>uuid</td><td>no</td><td>—</td><td>→ applications.id, ON DELETE CASCADE, indexed</td></tr>
                  <tr><td>token_hash<span className="col-badge uk">UK</span></td><td>string</td><td>no</td><td>—</td><td>SHA-256 hash of the opaque token</td></tr>
                  <tr><td>scope</td><td>string</td><td>no</td><td>—</td><td>granted at issuance, reissued as-is on refresh — never re-negotiated</td></tr>
                  <tr><td>created_at</td><td>timestamptz</td><td>no</td><td>now()</td><td></td></tr>
                  <tr><td>expires_at</td><td>timestamptz</td><td>yes</td><td>—</td><td>NULL = non-expiring</td></tr>
                  <tr><td>last_used_at</td><td>timestamptz</td><td>yes</td><td>—</td><td></td></tr>
                  <tr><td>revoked_at</td><td>timestamptz</td><td>yes</td><td>—</td><td>presence = revoked</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="endpoint" id="authorization_codes">
            <div className="endpoint-head"><span className="endpoint-path">authorization_codes</span><span className="table-count">9 columns</span></div>
            <p className="endpoint-desc">
              Added 0013. Short-lived, single-use codes for the <code>authorization_code</code> +
              PKCE grant — mirrors <code>refresh_tokens</code>' hash-only storage pattern.
            </p>
            <div className="table-scroll">
              <table className="params-table">
                <thead><tr><th>Column</th><th>Type</th><th>Null</th><th>Default</th><th>Notes</th></tr></thead>
                <tbody>
                  <tr><td>id<span className="col-badge pk">PK</span></td><td>uuid</td><td>no</td><td>—</td><td></td></tr>
                  <tr><td>application_id<span className="col-badge fk">FK</span></td><td>uuid</td><td>no</td><td>—</td><td>→ applications.id, ON DELETE CASCADE, indexed</td></tr>
                  <tr><td>code_hash<span className="col-badge uk">UK</span></td><td>string</td><td>no</td><td>—</td><td>SHA-256 hash of the opaque code</td></tr>
                  <tr><td>redirect_uri</td><td>string</td><td>no</td><td>—</td><td>the exact URI used at /oauth/authorize; re-checked at token exchange (loopback-port-agnostic)</td></tr>
                  <tr><td>code_challenge</td><td>string</td><td>no</td><td>—</td><td>PKCE, RFC 7636</td></tr>
                  <tr><td>code_challenge_method</td><td>string</td><td>no</td><td>—</td><td>only S256 is accepted</td></tr>
                  <tr><td>scope</td><td>string</td><td>no</td><td>—</td><td>carried through to the minted access token</td></tr>
                  <tr><td>created_at</td><td>timestamptz</td><td>no</td><td>now()</td><td></td></tr>
                  <tr><td>expires_at</td><td>timestamptz</td><td>no</td><td>—</td><td>~10 minutes (AUTHORIZATION_CODE_TTL_SECONDS)</td></tr>
                  <tr><td>used_at</td><td>timestamptz</td><td>yes</td><td>—</td><td>presence = already exchanged; set before the redirect_uri/PKCE checks run, so a failed exchange can't be retried</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <h2 id="indexes">Indexes</h2>
          <div className="table-scroll">
            <table className="params-table">
              <thead><tr><th>Name</th><th>Table</th><th>Columns</th><th>Kind</th></tr></thead>
              <tbody>
                <tr><td className="mono">ix_documents_library_id</td><td>documents</td><td>library_id</td><td>btree</td></tr>
                <tr><td className="mono">ix_documents_split_group_id</td><td>documents</td><td>split_group_id</td><td>btree, partial (WHERE split_group_id IS NOT NULL)</td></tr>
                <tr><td className="mono">ix_chunks_document_id</td><td>chunks</td><td>document_id</td><td>btree</td></tr>
                <tr><td className="mono">ix_chunks_library_id</td><td>chunks</td><td>library_id</td><td>btree</td></tr>
                <tr><td className="mono">ix_chunks_content_tsv_gin</td><td>chunks</td><td>content_tsv</td><td>GIN (sparse/keyword search)</td></tr>
                <tr><td className="mono">ix_chunks_embedding_hnsw</td><td>chunks</td><td>embedding</td><td>HNSW, vector_cosine_ops (dense search)</td></tr>
                <tr><td className="mono">ix_refresh_tokens_application_id</td><td>refresh_tokens</td><td>application_id</td><td>btree</td></tr>
                <tr><td className="mono">ix_authorization_codes_application_id</td><td>authorization_codes</td><td>application_id</td><td>btree</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
