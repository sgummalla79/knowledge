import { useState } from 'react'
import { Modal } from './Modal'
import type { Library } from '../api/types'

interface Props {
  title: string
  submitLabel: string
  initial?: Library
  pending: boolean
  error?: string
  onClose: () => void
  onSubmit: (values: { name: string; description: string | null }) => void
}

export function LibraryFormModal({ title, submitLabel, initial, pending, error, onClose, onSubmit }: Props) {
  const [name, setName] = useState(initial?.name ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')

  return (
    <Modal title={title} onClose={onClose}>
      {error && <div className="error-banner">{error}</div>}
      <form
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit({ name: name.trim(), description: description.trim() || null })
        }}
      >
        <label htmlFor="library-name">Name</label>
        <input id="library-name" type="text" value={name} onChange={(event) => setName(event.target.value)} autoFocus />

        <label htmlFor="library-description">Description</label>
        <textarea
          id="library-description"
          rows={3}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />

        <div className="modal-actions">
          <button type="button" className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" disabled={pending || name.trim().length === 0}>
            {submitLabel}
          </button>
        </div>
      </form>
    </Modal>
  )
}
