import { useState } from 'react'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import type { OrgRole } from '../api/types'
import { Modal } from './Modal'

interface Props {
  orgId: string
  onClose: () => void
  onInvited: () => void
}

export function InviteMemberModal({ orgId, onClose, onInvited }: Props) {
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<OrgRole>('viewer')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await api.post(`/orgs/${orgId}/invites`, { email, role })
      onInvited()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
      setSaving(false)
    }
  }

  return (
    <Modal title="Invite member" onClose={onClose}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && (
          <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        <div>
          <label htmlFor="invite-email" className="mb-1.5 block text-sm text-foreground">
            Email
          </label>
          <input
            id="invite-email"
            type="email"
            autoFocus
            placeholder="teammate@company.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground placeholder:text-muted-foreground"
          />
        </div>
        <div>
          <label htmlFor="invite-role" className="mb-1.5 block text-sm text-foreground">
            Role
          </label>
          <select
            id="invite-role"
            value={role}
            onChange={(event) => setRole(event.target.value as OrgRole)}
            className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground"
          >
            <option value="viewer">Viewer</option>
            <option value="contributor">Contributor</option>
            <option value="admin">Admin</option>
          </select>
        </div>
        <div className="mt-2 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground">
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving || !email.trim()}
            className="rounded-sm bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {saving ? 'Inviting…' : 'Invite member'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
