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
  email: string
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

// Only "api_key" and "oauth_client_credentials" are creatable today — see
// api/presentation/schemas.py's ApplicationAuthMethod comment for why the other 2 methods already
// exist in the wire format but aren't selectable yet.
export type ApplicationAuthMethod = 'api_key' | 'oauth_client_credentials' | 'oauth_authorization_code' | 'certificate'
export type ApplicationStatus = 'active' | 'revoked'

export interface Application {
  id: string
  org_id: string
  name: string
  description: string | null
  auth_method: ApplicationAuthMethod
  status: ApplicationStatus
  // Only meaningful for api_key.
  scopes: string[]
  // Only set for oauth_client_credentials — the org member whose profile this application's
  // tokens inherit permissions from.
  execute_as_identity_id: string | null
  // Whether this application may reach the MCP server at all — uniform across all three auth
  // methods, independent of scopes/execute_as_identity_id above. See MCPSettings for the
  // org-level tier toggles that gate what it can actually do once connected.
  mcp_access: boolean
  created_at: string
  last_modified_at: string
  revoked_at: string | null
}

// Returned only from create/rotate — the raw API key is never persisted, so this is the only
// response shape that ever carries it.
export interface ApplicationWithSecret extends Application {
  api_key: string
}

// oauth_client_credentials' counterpart to ApplicationWithSecret.
export interface ApplicationWithClientSecret extends Application {
  client_id: string
  client_secret: string
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
