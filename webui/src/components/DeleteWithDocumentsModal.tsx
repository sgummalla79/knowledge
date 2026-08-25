import { useState } from 'react'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import { Modal } from './Modal'
import { PasswordField } from './PasswordField'

interface Props {
  kind: 'category' | 'shelf'
  name: string
  documentCount: number
  deletePath: string
  onClose: () => void
  onDeleted: (documentsDeleted: number) => void
}

// Two-step confirmation for a destructive action: this modal itself is the first confirmation
// (shown for every delete, cascade or not); opting into "also delete the documents" reveals a
// second, stronger step — the current password, re-verified server-side
// (CategoryService.delete_category / ShelfService.delete_shelf) the same way this app already
// gates other destructive/security-sensitive actions (username/org-name changes). Leaving the
// cascade checkbox off needs only this one dialog, since a plain unlink deletes nothing.
export function DeleteWithDocumentsModal({ kind, name, documentCount, deletePath, onClose, onDeleted }: Props) {
  const [cascade, setCascade] = useState(false)
  const [password, setPassword] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const affectedNoun = `document${documentCount === 1 ? '' : 's'}`
  const unlinkExplanation =
    kind === 'category'
      ? `will become uncategorized`
      : `will be removed from this shelf`

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      const { documents_deleted: documentsDeleted } = await api.delete<{ documents_deleted: number }>(
        deletePath,
        cascade ? { cascade: true, current_password: password } : undefined,
      )
      onDeleted(documentsDeleted)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
      setSaving(false)
    }
  }

  return (
    <Modal title={`Delete ${kind}`} onClose={onClose}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <p className="text-sm text-foreground">
          Delete <span className="font-semibold">{name}</span>? This cannot be undone.
          {documentCount > 0 && (
            <>
              {' '}
              {documentCount} {affectedNoun} currently in this {kind} {unlinkExplanation}.
            </>
          )}
        </p>

        {documentCount > 0 && (
          <label className="flex items-start gap-2.5 rounded-sm border border-border bg-secondary px-3 py-2.5 text-sm text-foreground">
            <input
              type="checkbox"
              checked={cascade}
              onChange={(event) => setCascade(event.target.checked)}
              className="mt-0.5 accent-destructive"
            />
            <span>
              Also <span className="font-semibold text-destructive">permanently delete</span> these {documentCount}{' '}
              {affectedNoun} and all their chunks. This cannot be undone.
            </span>
          </label>
        )}

        {cascade && (
          <div>
            <label htmlFor="delete-confirm-password" className="mb-1.5 block text-sm text-foreground">
              Current password
            </label>
            <PasswordField
              id="delete-confirm-password"
              placeholder="Confirm it's really you before permanently deleting content"
              value={password}
              onChange={setPassword}
              autoFocus
            />
          </div>
        )}

        {error && (
          <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="mt-2 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground">
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving || (cascade && !password)}
            className="rounded-sm bg-destructive px-5 py-2 text-sm font-semibold text-destructive-foreground hover:opacity-90 disabled:opacity-60"
          >
            {saving ? 'Deleting…' : cascade ? `Permanently delete ${kind} and ${documentCount} ${affectedNoun}` : `Delete ${kind}`}
          </button>
        </div>
      </form>
    </Modal>
  )
}
