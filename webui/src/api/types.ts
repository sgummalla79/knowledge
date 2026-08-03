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
