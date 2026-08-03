import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { EmbeddingOptions, JobStatus, Library, LibraryDocument, ScoredChunk } from './types'

export function useEmbeddingOptions() {
  return useQuery({
    queryKey: ['embedding-options'],
    queryFn: () => api.get<EmbeddingOptions>('/embedding-options'),
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

export function useDocuments(libraryId: string) {
  return useQuery({
    queryKey: ['libraries', libraryId, 'documents'],
    queryFn: () => api.get<LibraryDocument[]>(`/libraries/${libraryId}/documents`),
  })
}

export function useUploadDocument(libraryId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return api.upload<{ job_id: string }>(`/libraries/${libraryId}/documents`, formData)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['libraries', libraryId, 'documents'] }),
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

export function useRetryDocument(libraryId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (documentId: string) => api.post<{ job_id: string }>(`/libraries/${libraryId}/documents/${documentId}/retry`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['libraries', libraryId, 'documents'] }),
  })
}

const TERMINAL_JOB_STATUSES = new Set(['completed', 'failed', 'cancelled'])

export function useJobStatus(libraryId: string, jobId: string | null) {
  return useQuery({
    queryKey: ['libraries', libraryId, 'jobs', jobId],
    queryFn: () => api.get<JobStatus>(`/libraries/${libraryId}/jobs/${jobId}`),
    enabled: jobId !== null,
    refetchInterval: (query) => (query.state.data && TERMINAL_JOB_STATUSES.has(query.state.data.status) ? false : 1500),
  })
}

export function useQueryLibrary(libraryId: string) {
  return useMutation({
    mutationFn: (input: { query: string; topK: number }) =>
      api.post<{ chunks: ScoredChunk[] }>(`/libraries/${libraryId}/query`, { query: input.query, top_k: input.topK }),
  })
}
