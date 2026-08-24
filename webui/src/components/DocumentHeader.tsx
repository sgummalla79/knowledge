import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import type { Document } from '../api/types'
import { formatRelativeTime } from '../lib/formatRelativeTime'
import { useToast } from './toastContext'
import { PencilIcon, TrashIcon } from './icons'

interface Props {
  document: Document
}

// Type/category/shelves/tags used to render here as read-only pills — now editable, so they live
// in DocumentOrganizePanel instead (a static pill can't also be a control without either
// duplicating the UI or this component reaching into shelf/tag mutation state it has no other
// reason to know about). Title and delete stay here since they're properties of the document
// itself, not organization metadata.
export function DocumentHeader({ document }: Props) {
  const { showToast } = useToast()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const [editing, setEditing] = useState(false)
  const [titleDraft, setTitleDraft] = useState(document.title)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)

  function startEditing() {
    setTitleDraft(document.title)
    setEditing(true)
  }

  async function saveTitle() {
    const trimmed = titleDraft.trim()
    if (!trimmed || trimmed === document.title) {
      setEditing(false)
      return
    }
    setSaving(true)
    try {
      await api.patch(`/documents/${document.id}`, { title: trimmed })
      void queryClient.invalidateQueries({ queryKey: ['document', document.id] })
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
      setEditing(false)
      showToast('Title updated.')
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : 'Something went wrong — please try again.', 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete "${document.title}"? This permanently removes it and its chunks — this can't be undone.`)) {
      return
    }
    setDeleting(true)
    try {
      await api.delete(`/documents/${document.id}`)
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
      showToast('Document deleted.')
      navigate('/browse')
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : 'Something went wrong — please try again.', 'error')
      setDeleting(false)
    }
  }

  return (
    <header>
      <div className="flex items-start justify-between gap-4">
        {editing ? (
          <div className="flex flex-1 items-center gap-2">
            <input
              autoFocus
              value={titleDraft}
              onChange={(event) => setTitleDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void saveTitle()
                if (event.key === 'Escape') setEditing(false)
              }}
              disabled={saving}
              className="w-full rounded-sm border border-border bg-secondary px-3 py-1.5 text-[26px] font-semibold leading-snug text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <button
              type="button"
              onClick={() => void saveTitle()}
              disabled={saving}
              className="shrink-0 rounded-sm bg-primary px-3 py-1.5 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              onClick={() => setEditing(false)}
              disabled={saving}
              className="shrink-0 px-2 py-1.5 text-sm text-muted-foreground hover:text-foreground"
            >
              Cancel
            </button>
          </div>
        ) : (
          <div className="group flex min-w-0 items-center gap-2">
            <h1 className="text-[30px] font-semibold leading-snug text-foreground">{document.title}</h1>
            <button
              type="button"
              onClick={startEditing}
              aria-label="Edit title"
              className="shrink-0 text-muted-foreground opacity-0 transition-opacity hover:text-foreground group-hover:opacity-100"
            >
              <PencilIcon className="h-4 w-4" />
            </button>
          </div>
        )}

        <button
          type="button"
          onClick={() => void handleDelete()}
          disabled={deleting}
          aria-label="Delete document"
          className="mt-1 flex shrink-0 items-center gap-1.5 rounded-sm px-2.5 py-1.5 text-sm text-destructive hover:bg-destructive/10 disabled:opacity-60"
        >
          <TrashIcon className="h-4 w-4" />
          {deleting ? 'Deleting…' : 'Delete'}
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-muted-foreground">
        <span>Updated {formatRelativeTime(document.indexed_at ?? document.created_at)}</span>
        {document.file_type && <span>Format: {document.file_type}</span>}
      </div>
    </header>
  )
}
