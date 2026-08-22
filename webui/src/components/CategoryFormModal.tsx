import { useState } from 'react'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import type { Category } from '../api/types'
import { Modal } from './Modal'

interface Props {
  category: Category | null
  onClose: () => void
  onSaved: () => void
}

export function CategoryFormModal({ category, onClose, onSaved }: Props) {
  const [name, setName] = useState(category?.name ?? '')
  const [description, setDescription] = useState(category?.description ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      if (category) {
        await api.patch(`/categories/${category.id}`, { name, description: description || null })
      } else {
        await api.post('/categories', { name, description: description || null })
      }
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
      setSaving(false)
    }
  }

  return (
    <Modal title={category ? 'Edit category' : 'New category'} onClose={onClose}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && (
          <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        <div>
          <label htmlFor="category-name" className="mb-1.5 block text-sm text-foreground">
            Name
          </label>
          <input
            id="category-name"
            autoFocus
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground"
          />
        </div>
        <div>
          <label htmlFor="category-description" className="mb-1.5 block text-sm text-foreground">
            Description
          </label>
          <textarea
            id="category-description"
            rows={2}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Also used to route category-less queries here automatically, if it's a close enough match.
          </p>
        </div>
        <div className="mt-2 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground">
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving || !name.trim()}
            className="rounded-sm bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
