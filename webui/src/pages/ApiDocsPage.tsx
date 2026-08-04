import { Link } from 'react-router-dom'

export function ApiDocsPage() {
  return (
    <div className="settings-wide">
      <h1>API Documentation</h1>
      <p className="subtitle">knowledge-api — REST reference. Every route below returns JSON and is served from this same host.</p>

      <div className="docs-layout">
        <nav className="docs-nav">
          <a href="#overview">Overview</a>
          <a href="#auth">Authentication</a>
          <a href="#errors">Errors</a>
          <div className="docs-nav-group">Resources</div>
          <a href="#libraries">Libraries</a>
          <a href="#documents">Documents</a>
          <a href="#query">Query</a>
          <div className="docs-nav-group">Configuration</div>
          <a href="#embedding-settings">Embedding Settings</a>
          <a href="#search-settings">Search Settings</a>
          <a href="#web-crawl-settings">Web Crawler Settings</a>
          <a href="#options">Reference Options</a>
        </nav>

        <div className="docs-main">
          <h2 id="overview">Overview</h2>
          <p className="lede">
            All endpoints accept and return <code>application/json</code> (document upload is{' '}
            <code>multipart/form-data</code>; the token endpoint is form-encoded, standard OAuth2
            convention). List endpoints are paginated with <code>limit</code> (default 100, max 500),{' '}
            <code>offset</code> (default 0), and <code>sort</code> (default <code>-created_at</code>)
            query params, and return the total row count in an <code>X-Total-Count</code> header.
            Requests are rate-limited to 200 per minute by default.
          </p>
          <p className="lede">
            This app also bundles an MCP server (<code>list_libraries</code> / <code>query_library</code>
            {' '}tools) over streamable-HTTP at <code>/mcp</code> on its own port, secured by the same
            OAuth2 stack via an <code>authorization_code</code> + PKCE flow — a separate interface
            from the REST API documented here. See{' '}
            <Link to="/settings/data-model">Data Model</Link> for the underlying schema.
          </p>

          <h2 id="auth">Authentication</h2>
          <p className="lede">
            OAuth2. Register an application from{' '}
            <Link to="/settings/applications">Settings &rsaquo; Applications</Link> to get a{' '}
            <code>client_id</code> / <code>client_secret</code> and a set of allowed scopes, then
            exchange them for a short-lived access token. Send it as{' '}
            <code>Authorization: Bearer &lt;token&gt;</code> on every resource request.
          </p>

          <div className="endpoint" id="post-oauth-token">
            <div className="endpoint-head">
              <span className="method method-post">POST</span>
              <span className="endpoint-path">/oauth/token</span>
              <span className="scope-tag none">no auth required</span>
            </div>
            <p className="endpoint-desc">
              Form-encoded (<code>application/x-www-form-urlencoded</code>), dispatched on{' '}
              <code>grant_type</code>.
            </p>

            <h4>client_credentials request</h4>
            <pre className="code">
              <code>{`grant_type=client_credentials
client_id=<uuid>
client_secret=<secret>
scope=libraries:read query:execute offline_access`}</code>
            </pre>

            <h4>refresh_token request</h4>
            <pre className="code">
              <code>{`grant_type=refresh_token
refresh_token=<opaque token>`}</code>
            </pre>

            <h4>Response — 200</h4>
            <pre className="code">
              <code>{`{
  "access_token": "eyJhbGciOi...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "libraries:read query:execute",
  "refresh_token": "..."  // only present if offline_access was requested/granted
}`}</code>
            </pre>
            <p className="endpoint-desc">
              Access tokens are JWTs (HS256, 1 hour TTL, stateless — never re-checked against the
              DB). Refresh tokens are opaque, DB-backed, and <strong>reusable</strong> — not
              rotated on use. <code>offline_access</code> is a control flag (whether a refresh
              token is issued), not a resource scope itself, so it's never present in the access
              token's own <code>scope</code>.
            </p>
            <h4>Errors</h4>
            <div className="table-scroll">
              <table className="params-table">
                <tbody>
                  <tr><td><code>invalid_client</code></td><td>401 — bad client_id/client_secret</td></tr>
                  <tr><td><code>invalid_grant</code></td><td>400 — refresh token missing, expired, or revoked</td></tr>
                  <tr><td><code>invalid_scope</code></td><td>400 — requested scope exceeds the application's allowed_scopes</td></tr>
                  <tr><td><code>unsupported_grant_type</code></td><td>400 — grant_type isn't client_credentials or refresh_token</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <p className="lede" style={{ marginTop: 24 }}>
            <strong>Scopes</strong>
          </p>
          <div className="table-scroll" style={{ maxWidth: 480 }}>
            <table className="params-table">
              <tbody>
                <tr><td><code>libraries:read</code> / <code>libraries:write</code></td><td>Library CRUD</td></tr>
                <tr><td><code>documents:read</code> / <code>documents:write</code></td><td>Document upload/crawl/list/rename/delete/retry, job status/cancel</td></tr>
                <tr><td><code>query:execute</code></td><td>Run a retrieval query against a library</td></tr>
                <tr><td><code>embedding_settings:read</code> / <code>:write</code></td><td>Embedding config + provider enable/disable</td></tr>
                <tr><td><code>search_settings:read</code> / <code>:write</code></td><td>Hybrid search tuning</td></tr>
                <tr><td><code>web_crawl_settings:read</code> / <code>:write</code></td><td>Web crawler User-Agent configuration</td></tr>
                <tr><td><code>offline_access</code></td><td>Controls whether <code>/oauth/token</code> also issues a refresh token</td></tr>
              </tbody>
            </table>
          </div>

          <h2 id="errors">Errors</h2>
          <p className="lede">Every error, from every endpoint, uses the same structured envelope:</p>
          <pre className="code">
            <code>{`{
  "error": {
    "code": "library_not_found",
    "message": "Library not found.",
    "field": "library_id"   // omitted when not applicable
  }
}`}</code>
          </pre>
          <p className="lede">
            <code>401</code> = missing/invalid/expired token. <code>403</code> = valid token,
            wrong scope (<code>insufficient_scope</code>). <code>400</code> = validation error.{' '}
            <code>404</code> = not found. <code>429</code> = rate limited.
          </p>

          <h2 id="libraries">Libraries</h2>
          <p className="lede">A named collection of documents. Chunking/embedding config is global, not per-library — see Embedding Settings.</p>

          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-post">POST</span><span className="endpoint-path">/libraries</span><span className="scope-tag">libraries:write</span></div>
            <h4>Request body</h4>
            <pre className="code"><code>{`{ "name": "product-docs", "description": "optional" }`}</code></pre>
            <h4>Response — 201</h4>
            <pre className="code">
              <code>{`{
  "id": "uuid", "name": "product-docs", "description": "optional",
  "document_count": 0, "chunk_count": 0, "last_ingested_at": null,
  "created_at": "...", "updated_at": "..."
}`}</code>
            </pre>
          </div>

          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-get">GET</span><span className="endpoint-path">/libraries</span><span className="scope-tag">libraries:read</span></div>
            <p className="endpoint-desc">Paginated (<code>limit</code>, <code>offset</code>, <code>sort</code>). Returns an array of the same shape as above; total count in <code>X-Total-Count</code>.</p>
          </div>

          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-get">GET</span><span className="endpoint-path">/libraries/{'{library_id}'}</span><span className="scope-tag">libraries:read</span></div>
          </div>

          <div className="endpoint" id="patch-library">
            <div className="endpoint-head"><span className="method method-patch">PATCH</span><span className="endpoint-path">/libraries/{'{library_id}'}</span><span className="scope-tag">libraries:write</span></div>
            <p className="endpoint-desc">Renames a library and/or updates its description — a pure display-label edit, with no effect on its documents or embeddings.</p>
            <h4>Request body</h4>
            <pre className="code"><code>{`{ "name": "New name", "description": "optional" }`}</code></pre>
            <h4>Response — 200</h4>
            <p className="endpoint-desc">The updated library, same shape as the create endpoint above.</p>
            <h4>Errors</h4>
            <div className="table-scroll">
              <table className="params-table">
                <tbody>
                  <tr><td><code>library_name_taken</code></td><td>409 — another library already has this name</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-delete">DELETE</span><span className="endpoint-path">/libraries/{'{library_id}'}</span><span className="scope-tag">libraries:write</span></div>
            <p className="endpoint-desc">Cascades to its documents and chunks. Returns <code>204</code>.</p>
          </div>

          <h2 id="documents">Documents</h2>

          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-post">POST</span><span className="endpoint-path">/libraries/{'{library_id}'}/documents</span><span className="scope-tag">documents:write</span></div>
            <p className="endpoint-desc"><code>multipart/form-data</code> with a <code>file</code> field (max 50MB). Parses, chunks, and embeds the file asynchronously.</p>
            <h4>Response — 202</h4>
            <pre className="code"><code>{`{ "job_id": "..." }`}</code></pre>
          </div>

          <div className="endpoint" id="post-documents-crawl">
            <div className="endpoint-head"><span className="method method-post">POST</span><span className="endpoint-path">/libraries/{'{library_id}'}/documents/crawl</span><span className="scope-tag">documents:write</span></div>
            <p className="endpoint-desc">
              Ingests one or more web pages starting from a URL, instead of a file upload. Pages
              that look like an unrendered JS shell on a plain fetch are transparently re-fetched
              with a headless browser first — no flag needed. The outbound User-Agent is
              admin-configurable from <Link to="/settings/web-crawler">Settings &rsaquo; Web Crawler</Link> (some sites block the default).
            </p>
            <h4>Request body</h4>
            <pre className="code">
              <code>{`{
  "url": "https://developer.example.com/docs/intro.htm",
  "max_pages": 1,
  "scope_prefix": null
}`}</code>
            </pre>
            <p className="endpoint-desc">
              <code>max_pages</code> (default <code>1</code>, max <code>100</code>) —{' '}
              <code>1</code> just ingests that one page; higher values crawl outward to same-host,
              in-scope linked pages found on each page, breadth-first. <code>scope_prefix</code>{' '}
              (optional) overrides the default scope, which is the seed URL's own directory — a
              crawl never leaves the seed's host regardless. robots.txt is respected; a page it
              disallows is silently skipped.
            </p>
            <h4>Response — 202</h4>
            <pre className="code"><code>{`{ "job_id": "..." }`}</code></pre>
            <h4>Errors</h4>
            <div className="table-scroll">
              <table className="params-table">
                <tbody>
                  <tr><td><code>invalid_crawl_url</code></td><td>400 — malformed URL, unresolvable host, or resolves to a non-public address</td></tr>
                  <tr><td><code>rate_limited</code></td><td>429 — capped at 5 requests/minute (this endpoint makes outbound fetches on the caller's behalf)</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="endpoint" id="get-crawl-jobs">
            <div className="endpoint-head"><span className="method method-get">GET</span><span className="endpoint-path">/libraries/{'{library_id}'}/crawl-jobs/{'{job_id}'}</span><span className="scope-tag">documents:read</span></div>
            <p className="endpoint-desc">Status for a crawl started via <code>POST .../documents/crawl</code> — separate from the single-document job endpoint below, since a crawl can produce many documents.</p>
            <h4>Response — 200</h4>
            <pre className="code">
              <code>{`{
  "status": "pending | running | completed | failed",
  "seed_url": "https://developer.example.com/docs/intro.htm",
  "error": null,
  "pages": {
    "https://developer.example.com/docs/intro.htm": {
      "status": "completed | failed",
      "document_id": "uuid or null",
      "error": "string or null"
    }
  }
}`}</code>
            </pre>
            <p className="endpoint-desc">
              <code>pages</code> grows as the crawl discovers and processes pages — poll until the
              top-level <code>status</code> settles. One page failing doesn't fail the whole job;
              each failed page can be retried individually via the document retry endpoint below
              once its <code>document_id</code> is known (a page that fails before a document is
              ever created has <code>document_id: null</code> and nothing to retry — re-run the
              crawl instead).
            </p>
          </div>

          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-get">GET</span><span className="endpoint-path">/libraries/{'{library_id}'}/jobs/{'{job_id}'}</span><span className="scope-tag">documents:read</span></div>
            <h4>Response — 200</h4>
            <pre className="code">
              <code>{`{
  "status": "pending | running | completed | failed | cancelled",
  "error": null,
  "document_id": "uuid or null",
  "cancel_requested": false
}`}</code>
            </pre>
            <p className="endpoint-desc">
              <code>cancel_requested</code> is <code>true</code> from the moment{' '}
              <code>POST .../jobs/{'{job_id}'}/cancel</code> is called until the job actually
              settles on <code>cancelled</code> — cancellation is best-effort (checked between
              embedding-provider batches, not instant), so a client can show "cancelling…" during
              that window.
            </p>
          </div>

          <div className="endpoint" id="post-jobs-cancel">
            <div className="endpoint-head"><span className="method method-post">POST</span><span className="endpoint-path">/libraries/{'{library_id}'}/jobs/{'{job_id}'}/cancel</span><span className="scope-tag">documents:write</span></div>
            <p className="endpoint-desc">
              Requests cancellation of an in-progress upload or retry. Returns immediately — poll{' '}
              <code>GET .../jobs/{'{job_id}'}</code> for the job to actually reach{' '}
              <code>cancelled</code>. The resulting document is kept (not deleted) with{' '}
              <code>status: "cancelled"</code> and can be retried later exactly like a failed one.
            </p>
            <h4>Response — 202</h4>
            <p className="endpoint-desc">Empty body.</p>
          </div>

          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-get">GET</span><span className="endpoint-path">/libraries/{'{library_id}'}/documents</span><span className="scope-tag">documents:read</span></div>
            <p className="endpoint-desc">Paginated. Each item: <code>id, library_id, source_filename, file_type, status, error_message, size_bytes, chunk_count, ingested_at, created_at</code>. <code>size_bytes</code>/<code>chunk_count</code> are <code>null</code> (not <code>0</code>) until known — <code>size_bytes</code> is set immediately, <code>chunk_count</code> only once ingestion completes.</p>
          </div>

          <div className="endpoint" id="patch-document">
            <div className="endpoint-head"><span className="method method-patch">PATCH</span><span className="endpoint-path">/libraries/{'{library_id}'}/documents/{'{document_id}'}</span><span className="scope-tag">documents:write</span></div>
            <p className="endpoint-desc">Renames a document — a pure display-label edit, safe at any status (including mid-ingestion) and has no effect on its chunks/embeddings or on future retries.</p>
            <h4>Request body</h4>
            <pre className="code"><code>{`{ "source_filename": "New Name.pdf" }`}</code></pre>
            <h4>Response — 200</h4>
            <p className="endpoint-desc">The updated document, same shape as the list endpoint above.</p>
          </div>

          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-delete">DELETE</span><span className="endpoint-path">/libraries/{'{library_id}'}/documents/{'{document_id}'}</span><span className="scope-tag">documents:write</span></div>
            <p className="endpoint-desc">Removes the document and its chunks, decrements the library's counts. Returns <code>204</code>.</p>
          </div>

          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-post">POST</span><span className="endpoint-path">/libraries/{'{library_id}'}/documents/{'{document_id}'}/retry</span><span className="scope-tag">documents:write</span></div>
            <p className="endpoint-desc">Re-runs ingestion for a <code>failed</code> or <code>cancelled</code> document using its originally-stored bytes. Returns <code>202</code> with a new <code>job_id</code>.</p>
          </div>

          <h2 id="query">Query</h2>
          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-post">POST</span><span className="endpoint-path">/libraries/{'{library_id}'}/query</span><span className="scope-tag">query:execute</span></div>
            <h4>Request body</h4>
            <pre className="code"><code>{`{ "query": "how do I reset a password?", "top_k": 5 }`}</code></pre>
            <p className="endpoint-desc">Hybrid retrieval: dense (pgvector) + sparse (keyword) candidates fused via reciprocal rank fusion — tuned via Search Settings.</p>
            <h4>Response — 200</h4>
            <pre className="code">
              <code>{`{
  "chunks": [
    { "id": "uuid", "document_id": "uuid", "chunk_index": 0, "content": "...", "score": 0.82 }
  ]
}`}</code>
            </pre>
          </div>

          <h2 id="embedding-settings">Embedding Settings</h2>
          <p className="lede">
            One configuration per provider (<code>voyage</code>, <code>ollama</code>,{' '}
            <code>openai_compatible</code>) — every provider starts disabled and unconfigured.
            Exactly one may be <code>enabled</code> at a time, since every library shares the same
            embedding model; enabling a provider disables whichever other one was active. Changing
            a provider's model/base_url/dimensions, or disabling/switching away from it, is
            rejected while it's the active provider and any document exists anywhere (embeddings
            from different models aren't comparable) — rotating just its api_key is always
            allowed, and configuring a provider that isn't the active one is never blocked. Also
            manageable from <Link to="/settings">Settings &rsaquo; Providers</Link>.
          </p>

          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-get">GET</span><span className="endpoint-path">/embedding-settings</span><span className="scope-tag">embedding_settings:read</span></div>
            <p className="endpoint-desc">Lists all three providers' status.</p>
            <h4>Response — 200</h4>
            <pre className="code">
              <code>{`[
  {
    "provider": "ollama", "enabled": true, "configured": true, "locked": true, "chunk_count": 42,
    "model": "nomic-embed-text", "base_url": "http://ollama:11434", "dimensions": 768,
    "chunk_size": 800, "chunk_overlap": 100, "updated_at": "..."
  },
  {
    "provider": "voyage", "enabled": false, "configured": false, "locked": false, "chunk_count": 0,
    "model": null, "base_url": null, "dimensions": null,
    "chunk_size": 800, "chunk_overlap": 100, "updated_at": null
  }
]`}</code>
            </pre>
          </div>

          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-get">GET</span><span className="endpoint-path">/embedding-settings/{'{provider}'}</span><span className="scope-tag">embedding_settings:read</span></div>
            <p className="endpoint-desc">A single provider's status — same shape as one item above.</p>
          </div>

          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-put">PUT</span><span className="endpoint-path">/embedding-settings/{'{provider}'}</span><span className="scope-tag">embedding_settings:write</span></div>
            <h4>Request body</h4>
            <pre className="code">
              <code>{`{
  "model": "text-embedding-3-small",
  "api_key": "sk-...",
  "base_url": "https://api.openai.com/v1",
  "dimensions": 1536,
  "chunk_size": 800,
  "chunk_overlap": 100
}`}</code>
            </pre>
            <p className="endpoint-desc">
              Saves this provider's config without changing whether it's enabled. On a first-time
              save or any model/base_url/dimensions change, the endpoint is live-verified (an
              actual embed call) before the new config is persisted.
            </p>
            <h4>Errors</h4>
            <div className="table-scroll">
              <table className="params-table">
                <tbody>
                  <tr><td><code>unsupported_embedding_provider</code></td><td>400 — not a registered provider adapter</td></tr>
                  <tr><td><code>embedding_model_locked</code></td><td>400 — model/base_url/dimensions changed while this provider is active and documents already exist</td></tr>
                  <tr><td><code>embedding_dimension_mismatch</code></td><td>400 — declared dimensions don't match what the provider actually returned</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-post">POST</span><span className="endpoint-path">/embedding-settings/{'{provider}'}/enable</span><span className="scope-tag">embedding_settings:write</span></div>
            <p className="endpoint-desc">
              Makes this the active provider, disabling whichever other one was active. Requires a
              saved, valid config first.
            </p>
            <h4>Errors</h4>
            <div className="table-scroll">
              <table className="params-table">
                <tbody>
                  <tr><td><code>embeddings_not_configured</code></td><td>400 — this provider has no saved model/dimensions yet</td></tr>
                  <tr><td><code>embedding_model_locked</code></td><td>400 — a different provider is active and has chunks; delete all documents first</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-post">POST</span><span className="endpoint-path">/embedding-settings/{'{provider}'}/disable</span><span className="scope-tag">embedding_settings:write</span></div>
            <p className="endpoint-desc">Deactivates this provider. A no-op if it wasn't the active one.</p>
            <h4>Errors</h4>
            <div className="table-scroll">
              <table className="params-table">
                <tbody>
                  <tr><td><code>embedding_model_locked</code></td><td>400 — this provider is active and has chunks; delete all documents first</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <h2 id="search-settings">Search Settings</h2>
          <p className="lede">Single global configuration for hybrid retrieval tuning. Absent is not an error — defaults apply.</p>

          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-get">GET</span><span className="endpoint-path">/search-settings</span><span className="scope-tag">search_settings:read</span></div>
          </div>
          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-put">PUT</span><span className="endpoint-path">/search-settings</span><span className="scope-tag">search_settings:write</span></div>
            <h4>Request body</h4>
            <pre className="code">
              <code>{`{
  "dense_k": 20,
  "sparse_k": 20,
  "rrf_k": 60
}`}</code>
            </pre>
          </div>

          <h2 id="web-crawl-settings">Web Crawler Settings</h2>
          <p className="lede">
            Single global User-Agent sent when fetching pages for "Add from URL" (
            <code>POST .../documents/crawl</code>). Absent is not an error — a default applies.
            Also manageable from <Link to="/settings/web-crawler">Settings &rsaquo; Web Crawler</Link>.
          </p>

          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-get">GET</span><span className="endpoint-path">/web-crawl-settings</span><span className="scope-tag">web_crawl_settings:read</span></div>
          </div>
          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-put">PUT</span><span className="endpoint-path">/web-crawl-settings</span><span className="scope-tag">web_crawl_settings:write</span></div>
            <h4>Request body</h4>
            <pre className="code"><code>{`{
  "user_agent": "python-requests/2.32.3"
}`}</code></pre>
          </div>

          <h2 id="options">Reference Options</h2>
          <p className="lede">Read-only capability listings for building a config UI — any authenticated token works, no specific scope required.</p>

          <div className="endpoint">
            <div className="endpoint-head"><span className="method method-get">GET</span><span className="endpoint-path">/embedding-options</span><span className="scope-tag none">any authenticated token</span></div>
            <h4>Response — 200</h4>
            <pre className="code">
              <code>{`{
  "providers": [
    { "name": "ollama", "enabled": true, "configured": true, "api_key_required": false, "base_url_required": false, "base_url_supported": true, "default_base_url": "http://ollama:11434" },
    { "name": "openai_compatible", "enabled": false, "configured": false, "api_key_required": false, "base_url_required": true, "base_url_supported": true },
    { "name": "voyage", "enabled": false, "configured": false, "api_key_required": true, "base_url_required": false, "base_url_supported": false }
  ],
  "default_provider": "ollama",
  "default_model": "nomic-embed-text",
  "suggested_models": [ { "provider": "ollama", "model": "nomic-embed-text", "dimensions": 768 } ]
}`}</code>
            </pre>
            <p className="endpoint-desc">Every known provider is listed regardless of state — see Embedding Settings for per-provider configuration. <code>default_provider</code>/<code>default_model</code> reflect whichever provider is currently active (<code>null</code> if none). <code>suggested_models</code> are convenience hints only — never enforced.</p>
          </div>
        </div>
      </div>
    </div>
  )
}
