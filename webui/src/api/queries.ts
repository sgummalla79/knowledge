import { useQuery } from '@tanstack/react-query'
import { api } from './client'
import type {
  Category,
  Chunk,
  DashboardStats,
  Document,
  EmbeddingProviderConfig,
  IngestionJob,
  Shelf,
  Tag,
} from './types'

export function useCategories() {
  return useQuery({ queryKey: ['categories'], queryFn: () => api.get<Category[]>('/categories') })
}

export function useShelves() {
  return useQuery({ queryKey: ['shelves'], queryFn: () => api.get<Shelf[]>('/shelves') })
}

export function useTags() {
  return useQuery({ queryKey: ['tags'], queryFn: () => api.get<Tag[]>('/tags') })
}

export function useIngestionJobs(limit = 10) {
  return useQuery({
    queryKey: ['ingestion-jobs', limit],
    queryFn: () => api.get<IngestionJob[]>(`/ingestion-jobs?limit=${limit}`),
  })
}

export function useDashboardStats() {
  return useQuery({ queryKey: ['stats', 'dashboard'], queryFn: () => api.get<DashboardStats>('/stats/dashboard') })
}

export function useDocument(documentId: string | undefined) {
  return useQuery({
    queryKey: ['document', documentId],
    queryFn: () => api.get<Document>(`/documents/${documentId}`),
    enabled: documentId !== undefined,
  })
}

export function useDocumentChunks(documentId: string | undefined) {
  return useQuery({
    queryKey: ['document', documentId, 'chunks'],
    queryFn: () => api.get<Chunk[]>(`/documents/${documentId}/chunks`),
    enabled: documentId !== undefined,
  })
}

export function useDocumentShelves(documentId: string | undefined) {
  return useQuery({
    queryKey: ['document', documentId, 'shelves'],
    queryFn: () => api.get<Shelf[]>(`/documents/${documentId}/shelves`),
    enabled: documentId !== undefined,
  })
}

export function useDocumentTags(documentId: string | undefined) {
  return useQuery({
    queryKey: ['document', documentId, 'tags'],
    queryFn: () => api.get<Tag[]>(`/documents/${documentId}/tags`),
    enabled: documentId !== undefined,
  })
}

export function useEmbeddingSettings() {
  return useQuery({
    queryKey: ['embedding-settings'],
    queryFn: () => api.get<EmbeddingProviderConfig[]>('/embedding-settings'),
  })
}

export interface DocumentFilters {
  categoryId?: string
  shelfId?: string
  type?: string
  sort?: string
  limit?: number
  offset?: number
}

function buildDocumentsPath(filters: DocumentFilters): string {
  const params = new URLSearchParams()
  if (filters.categoryId) params.set('category_id', filters.categoryId)
  if (filters.shelfId) params.set('shelf_id', filters.shelfId)
  if (filters.type) params.set('type', filters.type)
  if (filters.sort) params.set('sort', filters.sort)
  if (filters.limit !== undefined) params.set('limit', String(filters.limit))
  if (filters.offset !== undefined) params.set('offset', String(filters.offset))
  const query = params.toString()
  return query ? `/documents?${query}` : '/documents'
}

export function useDocuments(filters: DocumentFilters, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['documents', filters],
    queryFn: () => api.getPaginated<Document>(buildDocumentsPath(filters)),
    enabled: options.enabled ?? true,
  })
}
