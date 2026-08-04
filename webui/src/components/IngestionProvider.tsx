import { useEffect, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { CrawlJobStatus, JobStatus } from '../api/types'
import { IngestionContext, type IngestionKind } from './ingestionContext'
import { useToast } from './toastContext'

const TERMINAL_JOB_STATUSES = new Set(['completed', 'failed', 'cancelled'])
const TERMINAL_CRAWL_JOB_STATUSES = new Set(['completed', 'failed'])

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB']
  let value = bytes / 1024
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`
}

// App-wide (not per-library-page): an upload or crawl started from one library must keep blocking
// BOTH kinds of ingestion — from that library or any other — until its background job actually
// finishes, even if the user navigates to a different library's page while it's still running.
export function IngestionProvider({ children }: { children: ReactNode }) {
  const { showToast } = useToast()
  const queryClient = useQueryClient()

  const [activeKind, setActiveKind] = useState<IngestionKind | null>(null)
  const [activeLibraryId, setActiveLibraryId] = useState<string | null>(null)

  // --- upload ---
  const [uploadPosting, setUploadPosting] = useState(false)
  const [uploadJobId, setUploadJobId] = useState<string | null>(null)
  const [uploadStartedAt, setUploadStartedAt] = useState<number | null>(null)
  const [uploadElapsedSeconds, setUploadElapsedSeconds] = useState(0)
  // Captured at upload time so the completion toast (fired once the job settles, well after the
  // request itself has resolved and the File object reference is gone) still has a name/size.
  const [pendingUpload, setPendingUpload] = useState<{ name: string; size: number } | null>(null)

  const { data: uploadJobStatus } = useQuery({
    queryKey: ['libraries', activeLibraryId, 'jobs', uploadJobId],
    queryFn: () => api.get<JobStatus>(`/libraries/${activeLibraryId}/jobs/${uploadJobId}`),
    enabled: activeKind === 'upload' && activeLibraryId !== null && uploadJobId !== null,
    refetchInterval: (query) => (query.state.data && TERMINAL_JOB_STATUSES.has(query.state.data.status) ? false : 1500),
  })

  // --- crawl ---
  const [crawlPosting, setCrawlPosting] = useState(false)
  const [crawlJobId, setCrawlJobId] = useState<string | null>(null)

  const { data: crawlJobStatus } = useQuery({
    queryKey: ['libraries', activeLibraryId, 'crawl-jobs', crawlJobId],
    queryFn: () => api.get<CrawlJobStatus>(`/libraries/${activeLibraryId}/crawl-jobs/${crawlJobId}`),
    enabled: activeKind === 'crawl' && activeLibraryId !== null && crawlJobId !== null,
    refetchInterval: (query) => (query.state.data && TERMINAL_CRAWL_JOB_STATUSES.has(query.state.data.status) ? false : 1500),
  })

  // POST .../documents (or .../documents/crawl) returns 202 the instant it's accepted — the real
  // work runs afterward on a background thread. So "busy" must stay true from the moment the
  // request is fired (uploadPosting/crawlPosting, the brief in-flight window) through to the
  // background job reaching a terminal status, not just until the initial response lands.
  const isUploadBusy =
    uploadPosting ||
    (activeKind === 'upload' && uploadJobId !== null && (!uploadJobStatus || !TERMINAL_JOB_STATUSES.has(uploadJobStatus.status)))
  const isCrawlBusy =
    crawlPosting ||
    (activeKind === 'crawl' && crawlJobId !== null && (!crawlJobStatus || !TERMINAL_CRAWL_JOB_STATUSES.has(crawlJobStatus.status)))
  const isBusy = isUploadBusy || isCrawlBusy

  useEffect(() => {
    if (activeKind !== 'upload' || !uploadJobStatus || !TERMINAL_JOB_STATUSES.has(uploadJobStatus.status)) return

    if (activeLibraryId) {
      queryClient.invalidateQueries({ queryKey: ['libraries', activeLibraryId, 'documents'] })
    }
    if (uploadJobStatus.status === 'completed' && pendingUpload && uploadStartedAt !== null) {
      const seconds = ((Date.now() - uploadStartedAt) / 1000).toFixed(1)
      showToast(`${pendingUpload.name} of size ${formatFileSize(pendingUpload.size)} uploaded in ${seconds}s`, 'success')
    } else if (uploadJobStatus.status === 'failed') {
      showToast(`Upload failed: ${uploadJobStatus.error ?? 'Unknown error.'}`)
    }

    setActiveKind(null)
    setActiveLibraryId(null)
    setUploadJobId(null)
    setUploadStartedAt(null)
    setPendingUpload(null)
  }, [activeKind, uploadJobStatus, activeLibraryId, pendingUpload, queryClient, showToast, uploadStartedAt])

  useEffect(() => {
    if (activeKind !== 'crawl' || !crawlJobStatus || !TERMINAL_CRAWL_JOB_STATUSES.has(crawlJobStatus.status)) return

    if (activeLibraryId) {
      queryClient.invalidateQueries({ queryKey: ['libraries', activeLibraryId, 'documents'] })
    }
    if (crawlJobStatus.status === 'failed') {
      showToast(`Crawl failed: ${crawlJobStatus.error ?? 'Unknown error.'}`)
    }

    setActiveKind(null)
    setActiveLibraryId(null)
    setCrawlJobId(null)
  }, [activeKind, crawlJobStatus, activeLibraryId, queryClient, showToast])

  // Ticks once a second purely to re-render the "Uploading… Ns" display — the duration reported in
  // the completion toast is measured separately from Date.now(), not this counter.
  useEffect(() => {
    if (uploadStartedAt === null) return
    const interval = setInterval(() => setUploadElapsedSeconds(Math.floor((Date.now() - uploadStartedAt) / 1000)), 1000)
    return () => clearInterval(interval)
  }, [uploadStartedAt])

  function startUpload(libraryId: string, file: File) {
    if (isBusy) return // safety net — the UI should already prevent this via disabled buttons
    setActiveKind('upload')
    setActiveLibraryId(libraryId)
    setUploadStartedAt(Date.now())
    setUploadElapsedSeconds(0)
    setPendingUpload({ name: file.name, size: file.size })
    setUploadPosting(true)

    const formData = new FormData()
    formData.append('file', file)
    api
      .upload<{ job_id: string }>(`/libraries/${libraryId}/documents`, formData)
      .then((result) => {
        setUploadPosting(false)
        setUploadJobId(result.job_id)
        queryClient.invalidateQueries({ queryKey: ['libraries', libraryId, 'documents'] })
      })
      .catch((error: Error) => {
        setUploadPosting(false)
        setActiveKind(null)
        setActiveLibraryId(null)
        setUploadStartedAt(null)
        setPendingUpload(null)
        showToast(error.message)
      })
  }

  function startCrawl(libraryId: string, input: { url: string; maxPages: number; scopePrefix: string | null }) {
    if (isBusy) return
    setActiveKind('crawl')
    setActiveLibraryId(libraryId)
    setCrawlPosting(true)

    api
      .post<{ job_id: string }>(`/libraries/${libraryId}/documents/crawl`, {
        url: input.url,
        max_pages: input.maxPages,
        scope_prefix: input.scopePrefix,
      })
      .then((result) => {
        setCrawlPosting(false)
        setCrawlJobId(result.job_id)
        queryClient.invalidateQueries({ queryKey: ['libraries', libraryId, 'documents'] })
      })
      .catch((error: Error) => {
        setCrawlPosting(false)
        setActiveKind(null)
        setActiveLibraryId(null)
        showToast(error.message)
      })
  }

  return (
    <IngestionContext.Provider
      value={{
        isBusy,
        activeKind,
        activeLibraryId,
        uploadElapsedSeconds,
        uploadJobStatusLabel: uploadJobStatus && !TERMINAL_JOB_STATUSES.has(uploadJobStatus.status) ? uploadJobStatus.status : null,
        startUpload,
        crawlJobStatus: crawlJobStatus ?? null,
        startCrawl,
      }}
    >
      {children}
    </IngestionContext.Provider>
  )
}
