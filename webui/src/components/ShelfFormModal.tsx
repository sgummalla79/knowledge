import { useState } from 'react'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import type { Shelf } from '../api/types'
import { Modal } from './Modal'

interface Props {
  shelf: Shelf | null
  onClose: () => void
  onSaved: () => void
}

export function ShelfFormModal({ shelf, onClose, onSaved }: Props) {
  const [name, setName] = useState(shelf?.name ?? '')
  const [description, setDescription] = useState(shelf?.description ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      if (shelf) {
        await api.patch(`/shelves/${shelf.id}`, { name, description: description || null })
      } else {
        await api.post('/shelves', { name, description: description || null })
      }
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
      setSaving(false)
    }
  }

  return (
    <Modal title={shelf ? 'Edit shelf' : 'New shelf'} onClose={onClose}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && (
          <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        <div>
          <label htmlFor="shelf-name" className="mb-1.5 block text-sm text-foreground">
            Name
          </label>
          <input
            id="shelf-name"
            autoFocus
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground"
          />
        </div>
        <div>
          <label htmlFor="shelf-description" className="mb-1.5 block text-sm text-foreground">
            Description
          </label>
          <textarea
            id="shelf-description"
            rows={2}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground"
          />
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
