export type DocumentType = 'article' | 'document'
export type DocumentStatus = 'processing' | 'indexed' | 'failed' | 'archived'

export interface Document {
  id: string
  org_id: string
  category_id: string | null
  owner_id: string
  source_id: string | null
  title: string
  type: DocumentType
  description: string | null
  file_type: string
  status: DocumentStatus
  error_message: string | null
  size_bytes: number | null
  chunk_count: number | null
  split_group_id: string | null
  split_part: number | null
  split_total: number | null
  indexed_at: string | null
  created_at: string
  // Only present on the single-document GET (Item page) — see api/presentation/schemas.py's
  // DocumentResponse comment for why the list endpoint omits these.
  retrieval_count: number | null
  avg_similarity: number | null
}

export interface RoutedChunk {
  category_id: string
  category_name: string
  id: string
  document_id: string
  ordinal: number
  content: string
  score: number
  document_title: string
  document_type: DocumentType
}

export interface Chunk {
  id: string
  document_id: string
  ordinal: number
  content: string
  token_count: number
  created_at: string
}

export interface MostRetrievedDocument {
  document_id: string
  title: string
  retrieval_count: number
  avg_similarity: number
}

export interface DashboardStats {
  document_count: number
  chunk_count: number
  queries_last_30d: number
  avg_query_latency_ms: number | null
  most_retrieved_documents: MostRetrievedDocument[]
}

export interface EmbeddingProviderConfig {
  provider: string
  enabled: boolean
  configured: boolean
  locked: boolean
  locked_by_other: boolean
  chunk_count: number
  model: string | null
  base_url: string | null
  dimensions: number | null
  chunk_size: number
  chunk_overlap: number
  updated_at: string | null
  active_provider: string | null
}

export interface EmbeddingOptionProvider {
  name: string
  display_name: string
  enabled: boolean
  configured: boolean
  locked: boolean
  api_key_required: boolean
  base_url_required: boolean
  base_url_supported: boolean
  default_base_url: string | null
  supports_model_listing: boolean
}

export interface EmbeddingModelPreset {
  provider: string
  model: string
  dimensions: number
}

export interface EmbeddingOptions {
  providers: EmbeddingOptionProvider[]
  default_provider: string | null
  default_model: string | null
  suggested_models: EmbeddingModelPreset[]
}

export interface CrawlOptions {
  max_pages_limit: number
}

export interface Category {
  id: string
  org_id: string
  parent_id: string | null
  name: string
  slug: string
  description: string | null
  created_at: string
  last_modified_at: string
}

export interface Shelf {
  id: string
  org_id: string
  name: string
  slug: string
  description: string | null
  is_default: boolean
  document_count: number
  member_count: number
  created_at: string
  last_modified_at: string
}

export interface Org {
  id: string
  name: string
  slug: string
  description: string | null
  // The resolved permission set for the *current* identity in this org (e.g. "documents:write",
  // "applications:write") — check with permissions.includes(...) instead of a role comparison.
  permissions: string[]
}

export interface OrgMember {
  identity_id: string
  username: string
  email: string | null
  name: string
  profile_id: string
  profile_name: string
  profile_is_admin: boolean
}

export interface Profile {
  id: string
  org_id: string
  name: string
  description: string | null
  is_admin: boolean
  // True for all three profiles seeded per org (Admin, Contributor, Viewer) — fully locked, no
  // name/description/permission edits, no deletion. A strict superset of is_admin.
  is_system: boolean
  permissions: string[]
  created_at: string
  last_modified_at: string
}

export interface Tag {
  id: string
  org_id: string
  name: string
  created_at: string
}

export type IngestionJobType = 'upload' | 'crawl' | 'resync' | 'reindex'
export type IngestionJobStatus = 'queued' | 'processing' | 'indexed' | 'failed'

export interface IngestionJob {
  id: string
  org_id: string
  source_id: string | null
  document_id: string | null
  type: IngestionJobType
  status: IngestionJobStatus
  error_message: string | null
  items_processed: number
  triggered_by: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

// api_key was removed as a Connected Applications auth method — see PersonalAccessToken below for
// its self-service replacement. Only "oauth_client_credentials" is creatable today; the wire
// format still includes "certificate" (never built) — see api/presentation/schemas.py's
// ApplicationAuthMethod comment.
export type ApplicationAuthMethod = 'oauth_client_credentials' | 'oauth_authorization_code' | 'certificate'
export type ApplicationStatus = 'active' | 'revoked'

export interface Application {
  id: string
  org_id: string
  name: string
  description: string | null
  auth_method: ApplicationAuthMethod
  status: ApplicationStatus
  // Only set for oauth_client_credentials — the org member whose profile this application's
  // tokens inherit permissions from.
  execute_as_identity_id: string | null
  // Whether this application may reach the MCP server at all — uniform across both auth methods,
  // independent of execute_as_identity_id above. See MCPSettings for the org-level tier toggles
  // that gate what it can actually do once connected.
  mcp_access: boolean
  // Symmetric channel flag for the REST API side: without it, this application can't call any
  // REST endpoint at all regardless of what its profile would otherwise grant.
  api_access: boolean
  created_at: string
  last_modified_at: string
  revoked_at: string | null
}

// oauth_client_credentials' one-time-reveal response shape — client_secret is never persisted, so
// this is the only response that ever carries it.
export interface ApplicationWithClientSecret extends Application {
  client_id: string
  client_secret: string
}

// A self-service, per-user API key — created by an identity for themselves, in whichever org is
// active at creation time (org_id is then fixed). See api/domain/entities.py's PersonalAccessToken.
export interface PersonalAccessToken {
  id: string
  org_id: string
  name: string
  // Masked — only the first ~12 characters of the raw token, for the caller to recognize which
  // key is which. The full value is shown exactly once, at creation (PersonalAccessTokenWithSecret).
  token_prefix: string
  mcp_access: boolean
  created_at: string
  last_used_at: string | null
}

// Returned only from create — the raw token is never persisted, so this is the only response
// shape that ever carries it.
export interface PersonalAccessTokenWithSecret extends PersonalAccessToken {
  token: string
}

// One row per org: independent on/off switches for each of the three MCP tool tiers
// (/mcp/rag, /mcp/read, /mcp/write) — an application still needs its own mcp_access to reach any
// of them, and the connecting identity's profile still gates individual tool calls.
export interface MCPSettings {
  org_id: string
  rag_read_enabled: boolean
  object_read_enabled: boolean
  object_write_enabled: boolean
  last_modified_at: string
}
