import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  useCrawlDocuments,
  useCrawlJobStatus,
  useDeleteDocument,
  useDocuments,
  useJobStatus,
  useLibrary,
  useRenameDocument,
  useUploadDocument,
} from '../api/queries'
import type { JobStatus } from '../api/types'
import { GlobeIcon, LibraryIcon, UploadIcon } from '../components/icons'
import { useToast } from '../components/toastContext'

type Tab = 'documents' | 'web-pages'

// UI-only page size for the documents grid — not sourced from the backend because the API's own
// pagination default (100, see PaginationQuery) is sized for programmatic/MCP callers, not a
// browsable table.
const DOCUMENTS_PAGE_SIZE = 20

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

const TERMINAL_JOB_STATUSES = new Set(['completed', 'failed', 'cancelled'])

export function LibraryDetailPage() {
  const { libraryId } = useParams<{ libraryId: string }>()
  const [tab, setTab] = useState<Tab>('documents')
  const { data: library } = useLibrary(libraryId!)
  const { showToast } = useToast()
  const queryClient = useQueryClient()

  // Owned here (rather than inside UploadAction) so it survives a tab switch mid-upload — both
  // CrawlAction's button (a sibling, not a child) and the elapsed-time display need to keep
  // reflecting an in-flight upload even if the Documents tab isn't the active one.
  const uploadDocument = useUploadDocument(libraryId!)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [uploadStartedAt, setUploadStartedAt] = useState<number | null>(null)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)

  const { data: jobStatus } = useJobStatus(libraryId!, activeJobId)

  // A job can fail before it ever creates a Document row (e.g. no embedding provider configured
  // yet) — the documents grid alone would never show that, so re-fetch it once the job settles
  // and surface the job's own error via toast in the meantime.
  useEffect(() => {
    if (jobStatus && TERMINAL_JOB_STATUSES.has(jobStatus.status)) {
      queryClient.invalidateQueries({ queryKey: ['libraries', libraryId, 'documents'] })
    }
    if (jobStatus?.status === 'failed') {
      showToast(`Upload failed: ${jobStatus.error ?? 'Unknown error.'}`)
    }
  }, [jobStatus?.status, jobStatus?.error, libraryId, queryClient, showToast])

  // Ticks once a second purely to re-render the "Uploading… Ns" display — the duration reported
  // in the completion toast is measured separately from Date.now(), not this counter.
  useEffect(() => {
    if (uploadStartedAt === null) return
    const interval = setInterval(() => setElapsedSeconds(Math.floor((Date.now() - uploadStartedAt) / 1000)), 1000)
    return () => clearInterval(interval)
  }, [uploadStartedAt])

  function handleUpload(file: File) {
    const startedAt = Date.now()
    setUploadStartedAt(startedAt)
    setElapsedSeconds(0)
    uploadDocument.mutate(file, {
      onSuccess: (result) => {
        setActiveJobId(result.job_id)
        const seconds = ((Date.now() - startedAt) / 1000).toFixed(1)
        showToast(`${file.name} of size ${formatFileSize(file.size)} uploaded in ${seconds}s`)
      },
      onError: (error) => showToast(error.message),
      onSettled: () => setUploadStartedAt(null),
    })
  }

  return (
    <div className="settings-narrow">
      <div className="detail-header">
        <div className="page-header-icon">
          <LibraryIcon />
        </div>
        <div className="detail-header-title">
          <h1>{library?.name ?? '…'}</h1>
          {library?.description && <p className="subtitle">{library.description}</p>}
        </div>
      </div>

      <div className="tabs">
        <button type="button" className={`tab ${tab === 'documents' ? 'active' : ''}`} onClick={() => setTab('documents')}>
          Documents
        </button>
        <button type="button" className={`tab ${tab === 'web-pages' ? 'active' : ''}`} onClick={() => setTab('web-pages')}>
          Web Pages
        </button>
      </div>

      {tab === 'documents' ? (
        <UploadAction
          onUpload={handleUpload}
          isUploading={uploadDocument.isPending}
          elapsedSeconds={elapsedSeconds}
          jobStatus={jobStatus}
        />
      ) : (
        <CrawlAction libraryId={libraryId!} uploadInProgress={uploadDocument.isPending} />
      )}
      <DocumentsGrid libraryId={libraryId!} />
    </div>
  )
}

function UploadAction({
  onUpload,
  isUploading,
  elapsedSeconds,
  jobStatus,
}: {
  onUpload: (file: File) => void
  isUploading: boolean
  elapsedSeconds: number
  jobStatus: JobStatus | undefined
}) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    onUpload(file)
  }

  return (
    <>
      <input ref={fileInputRef} type="file" hidden onChange={handleFileChange} />
      <div style={{ marginBottom: 16 }}>
        <button type="button" onClick={() => fileInputRef.current?.click()} disabled={isUploading}>
          <UploadIcon />
          Upload document
        </button>
        {isUploading && (
          <span className="subtitle" style={{ marginLeft: 12 }}>
            Uploading… {elapsedSeconds}s
          </span>
        )}
      </div>
      {jobStatus && !TERMINAL_JOB_STATUSES.has(jobStatus.status) && (
        <p className="subtitle">Processing upload ({jobStatus.status})…</p>
      )}
    </>
  )
}

const TERMINAL_CRAWL_JOB_STATUSES = new Set(['completed', 'failed'])

function CrawlAction({ libraryId, uploadInProgress }: { libraryId: string; uploadInProgress: boolean }) {
  const { showToast } = useToast()
  const [url, setUrl] = useState('')
  const [maxPages, setMaxPages] = useState(1)
  const [scopePrefix, setScopePrefix] = useState('')
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const crawlDocuments = useCrawlDocuments(libraryId)
  const queryClient = useQueryClient()

  const { data: jobStatus } = useCrawlJobStatus(libraryId, activeJobId)

  // Same rationale as UploadAction's identical effect: a crawled page only becomes a Document row
  // once its own fetch+ingest step completes, so the documents grid needs a re-fetch once the job
  // settles rather than relying on the mutation's own onSuccess (which only means the job started).
  useEffect(() => {
    if (jobStatus && TERMINAL_CRAWL_JOB_STATUSES.has(jobStatus.status)) {
      queryClient.invalidateQueries({ queryKey: ['libraries', libraryId, 'documents'] })
    }
    if (jobStatus?.status === 'failed') {
      showToast(`Crawl failed: ${jobStatus.error ?? 'Unknown error.'}`)
    }
  }, [jobStatus?.status, jobStatus?.error, libraryId, queryClient, showToast])

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!url.trim()) return
    crawlDocuments.mutate(
      { url: url.trim(), maxPages, scopePrefix: scopePrefix.trim() || null },
      { onSuccess: (result) => setActiveJobId(result.job_id), onError: (error) => showToast(error.message) },
    )
  }

  // Per-page detail for the crawl that's currently running (or just finished) — a page that fails
  // never becomes a Document row, so this is the only place its status/error is visible; the
  // shared grid below only ever reflects pages that succeeded.
  const pages = jobStatus ? Object.entries(jobStatus.pages) : []

  return (
    <>
      <form className="query-form" onSubmit={handleSubmit}>
        <div className="query-input">
          <label htmlFor="crawl-url">URL</label>
          <input
            id="crawl-url"
            type="url"
            placeholder="https://example.com/docs"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            style={{ marginBottom: 0 }}
          />
        </div>
        <div className="topk-input">
          <label htmlFor="crawl-max-pages">Max pages</label>
          <input
            id="crawl-max-pages"
            type="number"
            min={1}
            max={100}
            value={maxPages}
            onChange={(event) => setMaxPages(Number(event.target.value))}
            style={{ marginBottom: 0 }}
          />
        </div>
        {maxPages > 1 && (
          <div className="scope-prefix-input">
            <label htmlFor="crawl-scope-prefix">Scope prefix (optional)</label>
            <input
              id="crawl-scope-prefix"
              type="text"
              placeholder="Defaults to the URL's own path"
              value={scopePrefix}
              onChange={(event) => setScopePrefix(event.target.value)}
              style={{ marginBottom: 0 }}
            />
          </div>
        )}
        <button type="submit" disabled={crawlDocuments.isPending || uploadInProgress}>
          <GlobeIcon />
          Crawl
        </button>
      </form>

      {jobStatus && !TERMINAL_CRAWL_JOB_STATUSES.has(jobStatus.status) && (
        <p className="subtitle">Crawling ({jobStatus.status})…</p>
      )}
      {pages.length > 0 && (
        <table style={{ marginBottom: 20 }}>
          <thead>
            <tr>
              <th>URL</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {pages.map(([pageUrl, page]) => (
              <tr key={pageUrl}>
                <td>{pageUrl}</td>
                <td>
                  <span className={`badge status-${page.status}`}>{page.status}</span>
                  {page.error && <div className="subtitle">{page.error}</div>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  )
}

function DocumentsGrid({ libraryId }: { libraryId: string }) {
  const { showToast } = useToast()
  const [offset, setOffset] = useState(0)
  const { data } = useDocuments(libraryId, DOCUMENTS_PAGE_SIZE, offset)
  const deleteDocument = useDeleteDocument(libraryId)
  const renameDocument = useRenameDocument(libraryId)

  const documents = data?.items ?? []
  const total = data?.total ?? 0
  const page = offset / DOCUMENTS_PAGE_SIZE + 1
  const pageCount = Math.max(1, Math.ceil(total / DOCUMENTS_PAGE_SIZE))

  if (documents.length === 0) {
    return <div className="empty-state">No documents yet — upload a file or crawl a web page to add one.</div>
  }

  return (
    <>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>File Type</th>
            <th>Chunks</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => (
            <tr key={document.id}>
              <td>{document.source_filename}</td>
              <td>{document.file_type}</td>
              <td>{document.chunk_count ?? '—'}</td>
              <td>
                <div className="row-actions">
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => {
                      const next = window.prompt('Rename document', document.source_filename)
                      if (next && next.trim()) {
                        renameDocument.mutate(
                          { documentId: document.id, sourceFilename: next.trim() },
                          { onError: (error) => showToast(error.message) },
                        )
                      }
                    }}
                  >
                    Rename
                  </button>
                  <button
                    type="button"
                    className="danger"
                    onClick={() => {
                      if (window.confirm(`Delete "${document.source_filename}"?`)) {
                        deleteDocument.mutate(document.id, { onError: (error) => showToast(error.message) })
                      }
                    }}
                  >
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {pageCount > 1 && (
        <div className="pagination">
          <button type="button" className="secondary" disabled={offset === 0} onClick={() => setOffset(offset - DOCUMENTS_PAGE_SIZE)}>
            Previous
          </button>
          <span className="subtitle">
            Page {page} of {pageCount}
          </span>
          <button
            type="button"
            className="secondary"
            disabled={offset + DOCUMENTS_PAGE_SIZE >= total}
            onClick={() => setOffset(offset + DOCUMENTS_PAGE_SIZE)}
          >
            Next
          </button>
        </div>
      )}
    </>
  )
}
