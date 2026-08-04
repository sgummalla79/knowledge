export interface Library {
  id: string
  name: string
  description: string | null
  document_count: number
  chunk_count: number
  last_ingested_at: string | null
  created_at: string
  updated_at: string
}

export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'

export interface LibraryDocument {
  id: string
  library_id: string
  source_filename: string
  file_type: string
  status: DocumentStatus
  error_message: string | null
  size_bytes: number | null
  chunk_count: number | null
  ingested_at: string | null
  created_at: string
}

export interface JobStatus {
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  error: string | null
  document_id: string | null
  cancel_requested: boolean
}

export interface ScoredChunk {
  id: string
  document_id: string
  chunk_index: number
  content: string
  score: number
}

export interface EmbeddingProviderOption {
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

export interface EmbeddingOptions {
  providers: EmbeddingProviderOption[]
  default_provider: string | null
  default_model: string | null
  suggested_models: { provider: string; model: string; dimensions: number }[]
}

export interface EmbeddingProviderStatus {
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

export interface EmbeddingProviderUpdateInput {
  model: string
  api_key?: string
  base_url?: string | null
  dimensions: number
  chunk_size: number
  chunk_overlap: number
}

export type ApplicationTokenStatus = 'active' | 'revoked' | 'none'

export interface Application {
  id: string
  name: string
  allowed_scopes: string[]
  token_status: ApplicationTokenStatus
  last_used_at: string | null
}

export interface ScopeGroup {
  label: string
  scopes: string[]
}

export interface WebCrawlSettings {
  user_agent: string
  updated_at: string | null
}

export type CrawlPageState = 'pending' | 'completed' | 'failed'

export interface CrawlPageStatus {
  status: CrawlPageState
  document_id: string | null
  error: string | null
}

export interface CrawlJobStatus {
  status: 'pending' | 'running' | 'completed' | 'failed'
  seed_url: string
  error: string | null
  pages: Record<string, CrawlPageStatus>
}
