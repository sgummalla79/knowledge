import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import { useProfiles } from '../api/queries'
import { Modal } from './Modal'
import { Select } from './Select'

interface Props {
  orgId: string
  onClose: () => void
  onInvited: () => void
}

export function InviteMemberModal({ orgId, onClose, onInvited }: Props) {
  const profiles = useProfiles()
  const [email, setEmail] = useState('')
  const [profileId, setProfileId] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Profiles are custom per org — there's no fixed default like the old "viewer" role, so seed
  // the picker with whichever profile loads first once the list is in.
  useEffect(() => {
    if (!profileId && profiles.data && profiles.data.length > 0) {
      setProfileId(profiles.data[0].id)
    }
  }, [profileId, profiles.data])

  const profileOptions = (profiles.data ?? []).map((profile) => ({ value: profile.id, label: profile.name }))

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await api.post(`/orgs/${orgId}/invites`, { email, profile_id: profileId })
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
          <label htmlFor="invite-profile" className="mb-1.5 block text-sm text-foreground">
            Profile
          </label>
          <Select
            id="invite-profile"
            value={profileId}
            options={profileOptions}
            onChange={(value) => setProfileId(value)}
            className="w-full px-4 py-2.5 text-[15px]"
          />
        </div>
        <div className="mt-2 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground">
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving || !email.trim() || !profileId}
            className="rounded-sm bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {saving ? 'Inviting…' : 'Invite member'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
