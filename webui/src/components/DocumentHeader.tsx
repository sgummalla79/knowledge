import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import type { Document } from '../api/types'
import { formatRelativeTime } from '../lib/formatRelativeTime'
import { useToast } from './toastContext'
import { CheckIcon, PencilIcon, SpinnerIcon, TrashIcon, XIcon } from './icons'

const ICON_BUTTON = 'flex h-9 w-9 shrink-0 items-center justify-center rounded-sm disabled:opacity-60'

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
      <div className="flex items-center justify-between gap-4">
        {editing ? (
          <input
            autoFocus
            value={titleDraft}
            onChange={(event) => setTitleDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') void saveTitle()
              if (event.key === 'Escape') setEditing(false)
            }}
            disabled={saving}
            className="w-full flex-1 rounded-sm border border-border bg-secondary px-3 py-1.5 text-[26px] font-semibold leading-snug text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
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

        <div className="flex shrink-0 items-center gap-1.5">
          {editing && (
            <>
              <button
                type="button"
                onClick={() => void saveTitle()}
                disabled={saving}
                aria-label="Save title"
                className={`${ICON_BUTTON} bg-primary text-primary-foreground hover:opacity-90`}
              >
                {saving ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <CheckIcon className="h-4 w-4" />}
              </button>
              <button
                type="button"
                onClick={() => setEditing(false)}
                disabled={saving}
                aria-label="Cancel"
                className={`${ICON_BUTTON} text-muted-foreground hover:bg-secondary hover:text-foreground`}
              >
                <XIcon className="h-4 w-4" />
              </button>
            </>
          )}
          <button
            type="button"
            onClick={() => void handleDelete()}
            disabled={deleting}
            aria-label="Delete document"
            className="flex h-9 shrink-0 items-center gap-1.5 rounded-sm bg-destructive px-3 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-60"
          >
            {deleting ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <TrashIcon className="h-4 w-4" />}
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-muted-foreground">
        <span>Updated {formatRelativeTime(document.indexed_at ?? document.created_at)}</span>
        {document.file_type && <span>Format: {document.file_type}</span>}
      </div>
    </header>
  )
}
