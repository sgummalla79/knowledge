import { useQuery } from '@tanstack/react-query'
import { api } from './client'
import type {
  Application,
  Category,
  Chunk,
  CrawlOptions,
  DashboardStats,
  Document,
  EmbeddingOptions,
  EmbeddingProviderConfig,
  IngestionJob,
  MCPSettings,
  Org,
  OrgMember,
  PermissionGroup,
  PersonalAccessToken,
  Profile,
  Shelf,
  Tag,
} from './types'

export function useOrgs() {
  return useQuery({ queryKey: ['orgs'], queryFn: () => api.get<Org[]>('/orgs') })
}

export function useOrgMembers(orgId: string | undefined) {
  return useQuery({
    queryKey: ['orgs', orgId, 'members'],
    queryFn: () => api.get<OrgMember[]>(`/orgs/${orgId}/members`),
    enabled: orgId !== undefined,
  })
}

// The caller's own account/profile in the active org — unlike useOrgMembers, needs no
// org_members:read permission, so it works for every member, not just admins (see GET /orgs/me).
export function useMe() {
  return useQuery({ queryKey: ['orgs', 'me'], queryFn: () => api.get<OrgMember>('/orgs/me') })
}

export function useApplications() {
  return useQuery({ queryKey: ['applications'], queryFn: () => api.get<Application[]>('/applications') })
}

export function useProfiles(enabled = true) {
  return useQuery({ queryKey: ['profiles'], queryFn: () => api.get<Profile[]>('/profiles'), enabled })
}

export function usePermissionCatalog() {
  return useQuery({
    queryKey: ['profiles', 'permissions'],
    queryFn: () => api.get<{ groups: PermissionGroup[] }>('/profiles/permissions'),
  })
}

export function usePersonalAccessTokens() {
  return useQuery({
    queryKey: ['personal-access-tokens'],
    queryFn: () => api.get<PersonalAccessToken[]>('/personal-access-tokens'),
  })
}

export function useMCPSettings() {
  return useQuery({ queryKey: ['mcp-settings'], queryFn: () => api.get<MCPSettings>('/mcp-settings') })
}

export function useCategories() {
  return useQuery({ queryKey: ['categories'], queryFn: () => api.get<Category[]>('/categories') })
}

export function useShelves() {
  return useQuery({ queryKey: ['shelves'], queryFn: () => api.get<Shelf[]>('/shelves') })
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

export function useEmbeddingOptions() {
  return useQuery({ queryKey: ['embedding-options'], queryFn: () => api.get<EmbeddingOptions>('/embedding-options') })
}

export function useCrawlOptions() {
  return useQuery({ queryKey: ['crawl-options'], queryFn: () => api.get<CrawlOptions>('/crawl-options') })
}

export interface DocumentFilters {
  categoryId?: string
  shelfId?: string
  type?: string
  sort?: string
  limit?: number
  offset?: number
  q?: string
}

function buildDocumentsPath(filters: DocumentFilters): string {
  const params = new URLSearchParams()
  if (filters.categoryId) params.set('category_id', filters.categoryId)
  if (filters.shelfId) params.set('shelf_id', filters.shelfId)
  if (filters.type) params.set('type', filters.type)
  if (filters.sort) params.set('sort', filters.sort)
  if (filters.limit !== undefined) params.set('limit', String(filters.limit))
  if (filters.offset !== undefined) params.set('offset', String(filters.offset))
  if (filters.q) params.set('q', filters.q)
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
