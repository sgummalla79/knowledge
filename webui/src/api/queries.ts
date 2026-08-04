import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  EmbeddingOptions,
  EmbeddingProviderStatus,
  EmbeddingProviderUpdateInput,
  Library,
  LibraryDocument,
  WebCrawlSettings,
} from './types'

export function useWebCrawlSettings() {
  return useQuery({
    queryKey: ['web-crawl-settings'],
    queryFn: () => api.get<WebCrawlSettings>('/web-crawl-settings'),
  })
}

export function useUpdateWebCrawlSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (userAgent: string) => api.put<WebCrawlSettings>('/web-crawl-settings', { user_agent: userAgent }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['web-crawl-settings'] }),
  })
}

export function useEmbeddingOptions() {
  return useQuery({
    queryKey: ['embedding-options'],
    queryFn: () => api.get<EmbeddingOptions>('/embedding-options'),
  })
}

export function useEmbeddingProviderStatus(provider: string | null) {
  return useQuery({
    queryKey: ['embedding-settings', provider],
    queryFn: () => api.get<EmbeddingProviderStatus>(`/embedding-settings/${provider}`),
    enabled: provider !== null,
  })
}

function useInvalidateEmbeddingQueries() {
  const queryClient = useQueryClient()
  return (provider: string) => {
    queryClient.invalidateQueries({ queryKey: ['embedding-settings', provider] })
    queryClient.invalidateQueries({ queryKey: ['embedding-options'] })
  }
}

export function useUpdateEmbeddingProvider(provider: string) {
  const invalidate = useInvalidateEmbeddingQueries()
  return useMutation({
    mutationFn: (input: EmbeddingProviderUpdateInput) =>
      api.put<EmbeddingProviderStatus>(`/embedding-settings/${provider}`, input),
    onSuccess: () => invalidate(provider),
  })
}

export function useEnableEmbeddingProvider(provider: string) {
  const invalidate = useInvalidateEmbeddingQueries()
  return useMutation({
    mutationFn: () => api.post<EmbeddingProviderStatus>(`/embedding-settings/${provider}/enable`),
    onSuccess: () => invalidate(provider),
  })
}

export function useDisableEmbeddingProvider(provider: string) {
  const invalidate = useInvalidateEmbeddingQueries()
  return useMutation({
    mutationFn: () => api.post<EmbeddingProviderStatus>(`/embedding-settings/${provider}/disable`),
    onSuccess: () => invalidate(provider),
  })
}

export function useLibraries() {
  return useQuery({
    queryKey: ['libraries'],
    queryFn: () => api.get<Library[]>('/libraries'),
  })
}

export function useLibrary(libraryId: string) {
  return useQuery({
    queryKey: ['libraries', libraryId],
    queryFn: () => api.get<Library>(`/libraries/${libraryId}`),
  })
}

export function useCreateLibrary() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: { name: string; description: string | null }) => api.post<Library>('/libraries', input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['libraries'] }),
  })
}

export function useUpdateLibrary(libraryId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: { name: string; description: string | null }) =>
      api.patch<Library>(`/libraries/${libraryId}`, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['libraries'] }),
  })
}

export function useDeleteLibrary() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (libraryId: string) => api.delete(`/libraries/${libraryId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['libraries'] }),
  })
}

export function useDocuments(libraryId: string, limit: number, offset: number) {
  return useQuery({
    queryKey: ['libraries', libraryId, 'documents', limit, offset],
    queryFn: () =>
      api.getPaginated<LibraryDocument>(`/libraries/${libraryId}/documents?limit=${limit}&offset=${offset}`),
    placeholderData: (previous) => previous,
  })
}

export function useDeleteDocument(libraryId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (documentId: string) => api.delete(`/libraries/${libraryId}/documents/${documentId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['libraries', libraryId, 'documents'] })
      queryClient.invalidateQueries({ queryKey: ['libraries'] })
    },
  })
}

export function useRenameDocument(libraryId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: { documentId: string; sourceFilename: string }) =>
      api.patch<LibraryDocument>(`/libraries/${libraryId}/documents/${input.documentId}`, {
        source_filename: input.sourceFilename,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['libraries', libraryId, 'documents'] }),
  })
}

