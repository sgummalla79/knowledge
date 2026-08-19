export type DocumentType = 'article' | 'dataset' | 'guide' | 'report' | 'faq' | 'media'
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
