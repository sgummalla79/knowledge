import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  useDeleteDocument,
  useDocuments,
  useJobStatus,
  useLibrary,
  useQueryLibrary,
  useRenameDocument,
  useRetryDocument,
  useUploadDocument,
} from '../api/queries'
import { ArrowLeftIcon } from '../components/icons'
import type { ScoredChunk } from '../api/types'

type Tab = 'documents' | 'query'

export function LibraryDetailPage() {
  const { libraryId } = useParams<{ libraryId: string }>()
  const [tab, setTab] = useState<Tab>('documents')
  const { data: library } = useLibrary(libraryId!)

  return (
    <>
      <div className="detail-header">
        <Link to="/" className="back-link" aria-label="Back to libraries">
          <ArrowLeftIcon />
        </Link>
        <h1>{library?.name ?? '…'}</h1>
      </div>
      {library?.description && <p className="subtitle">{library.description}</p>}

      <div className="tabs">
        <button type="button" className={`tab ${tab === 'documents' ? 'active' : ''}`} onClick={() => setTab('documents')}>
          Documents
        </button>
        <button type="button" className={`tab ${tab === 'query' ? 'active' : ''}`} onClick={() => setTab('query')}>
          Query
        </button>
      </div>

      {tab === 'documents' ? <DocumentsTab libraryId={libraryId!} /> : <QueryTab libraryId={libraryId!} />}
    </>
  )
}

const TERMINAL_JOB_STATUSES = new Set(['completed', 'failed', 'cancelled'])

function DocumentsTab({ libraryId }: { libraryId: string }) {
  const { data: documents } = useDocuments(libraryId)
  const uploadDocument = useUploadDocument(libraryId)
  const deleteDocument = useDeleteDocument(libraryId)
  const renameDocument = useRenameDocument(libraryId)
  const retryDocument = useRetryDocument(libraryId)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

  const { data: jobStatus } = useJobStatus(libraryId, activeJobId)

  // A job can fail before it ever creates a Document row (e.g. no embedding provider configured
  // yet) — the documents list alone would never show that, so re-fetch it once the job settles
  // and surface the job's own error in the meantime.
  useEffect(() => {
    if (jobStatus && TERMINAL_JOB_STATUSES.has(jobStatus.status)) {
      queryClient.invalidateQueries({ queryKey: ['libraries', libraryId, 'documents'] })
    }
  }, [jobStatus?.status, libraryId, queryClient])

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    uploadDocument.mutate(file, {
      onSuccess: (result) => setActiveJobId(result.job_id),
    })
  }

  return (
    <>
      <input ref={fileInputRef} type="file" hidden onChange={handleFileChange} />
      <div style={{ marginBottom: 16 }}>
        <button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploadDocument.isPending}>
          Upload document
        </button>
      </div>
      {uploadDocument.error && <div className="error-banner">{uploadDocument.error.message}</div>}
      {jobStatus && jobStatus.status === 'failed' && (
        <div className="error-banner">Upload failed: {jobStatus.error ?? 'Unknown error.'}</div>
      )}
      {jobStatus && !TERMINAL_JOB_STATUSES.has(jobStatus.status) && (
        <p className="subtitle">Processing upload ({jobStatus.status})…</p>
      )}

      {(documents ?? []).length === 0 ? (
        <div className="empty-state">No documents yet — upload a markdown, text, or PDF file.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Filename</th>
              <th>Type</th>
              <th>Status</th>
              <th>Chunks</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {(documents ?? []).map((document) => (
              <tr key={document.id}>
                <td>{document.source_filename}</td>
                <td>{document.file_type}</td>
                <td>
                  <span className={`badge status-${document.status}`}>{document.status}</span>
                  {document.error_message && <div className="subtitle">{document.error_message}</div>}
                </td>
                <td>{document.chunk_count ?? '—'}</td>
                <td>
                  <div className="row-actions">
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => {
                        const next = window.prompt('Rename document', document.source_filename)
                        if (next && next.trim()) renameDocument.mutate({ documentId: document.id, sourceFilename: next.trim() })
                      }}
                    >
                      Rename
                    </button>
                    {document.status === 'failed' && (
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => retryDocument.mutate(document.id, { onSuccess: (result) => setActiveJobId(result.job_id) })}
                      >
                        Retry
                      </button>
                    )}
                    <button
                      type="button"
                      className="danger"
                      onClick={() => {
                        if (window.confirm(`Delete "${document.source_filename}"?`)) deleteDocument.mutate(document.id)
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
      )}
    </>
  )
}

function QueryTab({ libraryId }: { libraryId: string }) {
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState(5)
  const [results, setResults] = useState<ScoredChunk[] | null>(null)
  const queryLibrary = useQueryLibrary(libraryId)

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!query.trim()) return
    queryLibrary.mutate(
      { query: query.trim(), topK },
      { onSuccess: (result) => setResults(result.chunks) },
    )
  }

  return (
    <>
      <form className="query-form" onSubmit={handleSubmit}>
        <div className="query-input">
          <label htmlFor="query-text">Query</label>
          <input id="query-text" type="text" value={query} onChange={(event) => setQuery(event.target.value)} style={{ marginBottom: 0 }} />
        </div>
        <div className="topk-input">
          <label htmlFor="query-topk">Top K</label>
          <input
            id="query-topk"
            type="number"
            min={1}
            max={100}
            value={topK}
            onChange={(event) => setTopK(Number(event.target.value))}
            style={{ marginBottom: 0 }}
          />
        </div>
        <button type="submit" disabled={queryLibrary.isPending}>
          Search
        </button>
      </form>

      {queryLibrary.error && <div className="error-banner">{queryLibrary.error.message}</div>}

      {results !== null && results.length === 0 && <div className="empty-state">No matching chunks.</div>}

      {(results ?? []).map((chunk) => (
        <div key={chunk.id} className="chunk-result">
          <div className="chunk-result-meta">
            <span>chunk #{chunk.chunk_index}</span>
            <span>score {chunk.score.toFixed(4)}</span>
          </div>
          <div className="chunk-result-content">{chunk.content}</div>
        </div>
      ))}
    </>
  )
}
