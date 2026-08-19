import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import { useCategories, useIngestionJobs, useShelves, useTags } from '../api/queries'
import type { Tag } from '../api/types'
import { Dropzone } from '../components/Dropzone'
import { RecentUploadsList } from '../components/RecentUploadsList'
import { Select } from '../components/Select'
import { SourceTypeRadio, type SourceType } from '../components/SourceTypeRadio'
import { TagPillInput } from '../components/TagPillInput'
import { useToast } from '../components/toastContext'
import { useJobPolling } from '../lib/useJobPolling'

interface JobStatus {
  status: string
  error: string | null
  document_id: string | null
}

interface CrawlStatus {
  status: string
  error: string | null
  pages: Record<string, { status: string; document_id: string | null; error: string | null }>
}

export function UploadPage() {
  const { showToast } = useToast()
  const queryClient = useQueryClient()
  const categories = useCategories()
  const shelves = useShelves()
  const tags = useTags()
  const recentJobs = useIngestionJobs(10)

  const [sourceType, setSourceType] = useState<SourceType>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [url, setUrl] = useState('')
  const [title, setTitle] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [pendingTags, setPendingTags] = useState<Tag[]>([])
  const [shelfIds, setShelfIds] = useState<string[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  function resetForm() {
    setFile(null)
    setUrl('')
    setTitle('')
    setPendingTags([])
    setShelfIds([])
  }

  async function applyPostUploadSettings(documentId: string) {
    try {
      if (title.trim()) {
        await api.patch(`/documents/${documentId}`, { title: title.trim() })
      }
      for (const tag of pendingTags) {
        await api.post(`/documents/${documentId}/tags`, { tag_id: tag.id })
      }
      for (const shelfId of shelfIds) {
        await api.post(`/shelves/${shelfId}/documents`, { document_id: documentId })
      }
    } catch {
      // The upload itself already succeeded — a follow-up rename/tag/shelf call failing shouldn't
      // read as an upload failure. The document is fully indexed and reachable; it just may be
      // missing a title override, tag, or shelf assignment the user can add from the item page.
      showToast('Uploaded, but some details couldn’t be saved — you can edit them from the item page.', 'error')
    }
  }

  useJobPolling<JobStatus>(sourceType === 'upload' ? activeJobId : null, 'upload', (status) => {
    setActiveJobId(null)
    void (async () => {
      if (status.status === 'completed' && status.document_id) {
        await applyPostUploadSettings(status.document_id)
        showToast('Upload complete.')
      } else if (status.status === 'failed') {
        showToast(status.error ?? 'Upload failed.', 'error')
      } else if (status.status === 'cancelled') {
        showToast('Upload cancelled.', 'error')
      }
      void queryClient.invalidateQueries({ queryKey: ['ingestion-jobs'] })
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
      resetForm()
    })()
  })

  useJobPolling<CrawlStatus>(sourceType === 'url' ? activeJobId : null, 'crawl', (status) => {
    setActiveJobId(null)
    const completedPages = Object.values(status.pages).filter((page) => page.status === 'completed').length
    if (status.status === 'completed' && completedPages > 0) {
      showToast(`Crawl complete — ${completedPages} page${completedPages === 1 ? '' : 's'} indexed.`)
    } else {
      showToast(status.error ?? 'Crawl failed.', 'error')
    }
    void queryClient.invalidateQueries({ queryKey: ['ingestion-jobs'] })
    void queryClient.invalidateQueries({ queryKey: ['documents'] })
    resetForm()
  })

  function toggleShelf(shelfId: string) {
    setShelfIds((current) =>
      current.includes(shelfId) ? current.filter((id) => id !== shelfId) : [...current, shelfId],
    )
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setFormError(null)

    if (sourceType === 'upload' && !file) {
      setFormError('Choose a file to upload.')
      return
    }
    if (sourceType === 'url' && !url.trim()) {
      setFormError('Enter a URL to crawl.')
      return
    }

    setSubmitting(true)
    try {
      if (sourceType === 'upload' && file) {
        const formData = new FormData()
        formData.append('file', file)
        if (categoryId) formData.append('category_id', categoryId)
        const { job_id } = await api.upload<{ job_id: string }>('/documents', formData)
        setActiveJobId(job_id)
      } else if (sourceType === 'url') {
        const { job_id } = await api.post<{ job_id: string }>('/documents/crawl', {
          url: url.trim(),
          category_id: categoryId || undefined,
        })
        setActiveJobId(job_id)
      }
      showToast('Upload started — indexing runs in the background.')
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="grid grid-cols-1 gap-12 py-12 lg:grid-cols-[1fr_320px]">
      <div>
        <h1 className="mb-1 text-[32px] font-semibold text-foreground">Add to the library</h1>
        <p className="mb-8 text-sm text-muted-foreground">
          New sources are chunked, embedded and made retrievable automatically after review.
        </p>

        <SourceTypeRadio value={sourceType} onChange={setSourceType} />

        <form onSubmit={handleSubmit}>
          {sourceType === 'upload' && <Dropzone file={file} onFileSelected={setFile} />}
          {sourceType === 'url' && (
            <input
              type="url"
              placeholder="https://docs.example.com/getting-started"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              className="mb-6 w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          )}
          {sourceType === 'connector' && (
            <p className="mb-6 rounded-sm bg-secondary px-4 py-3 text-sm text-muted-foreground">
              Connectors aren&apos;t available yet.
            </p>
          )}

          {formError && (
            <div className="mb-4 rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {formError}
            </div>
          )}

          <div className="mb-4">
            <label htmlFor="title" className="mb-1.5 block text-sm text-foreground">
              Title
            </label>
            <input
              id="title"
              placeholder="e.g. Q3 refund policy update"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>

          <div className="mb-4">
            <label htmlFor="category" className="mb-1.5 block text-sm text-foreground">
              Category
            </label>
            <Select
              id="category"
              value={categoryId}
              onChange={setCategoryId}
              options={[
                { value: '', label: 'No category' },
                ...(categories.data ?? []).map((category) => ({ value: category.id, label: category.name })),
              ]}
              className="w-full px-4 py-2.5 text-[15px]"
            />
          </div>

          <div className="mb-4">
            <span className="mb-1.5 block text-sm text-foreground">Tags</span>
            <TagPillInput
              tags={pendingTags}
              existingTags={tags.data ?? []}
              onAdd={(tag) => setPendingTags((current) => [...current, tag])}
              onRemove={(tagId) => setPendingTags((current) => current.filter((tag) => tag.id !== tagId))}
              placeholder="billing, refunds — press Tab or Enter"
            />
          </div>

          {(shelves.data ?? []).length > 0 && (
            <div className="mb-6">
              <span className="mb-1.5 block text-sm text-foreground">Shelf — who can retrieve this</span>
              <div className="flex flex-col gap-1.5">
                {(shelves.data ?? []).map((shelf) => (
                  <label key={shelf.id} className="flex items-center gap-2 text-sm text-foreground">
                    <input
                      type="checkbox"
                      checked={shelfIds.includes(shelf.id)}
                      onChange={() => toggleShelf(shelf.id)}
                      className="accent-primary"
                    />
                    {shelf.name}
                    {shelf.description && <span className="text-muted-foreground">— {shelf.description}</span>}
                  </label>
                ))}
              </div>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || sourceType === 'connector'}
            className="rounded-sm bg-primary px-5 py-2.5 text-[15px] font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {submitting ? 'Adding…' : 'Add to library'}
          </button>
        </form>
      </div>

      <div>
        <h2 className="mb-4 text-lg font-semibold text-foreground">Recent uploads</h2>
        <RecentUploadsList jobs={recentJobs.data ?? []} />
      </div>
    </div>
  )
}
