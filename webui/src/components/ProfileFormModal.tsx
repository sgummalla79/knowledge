import { useState } from 'react'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import type { Profile } from '../api/types'
import { Modal } from './Modal'

// Mirrors api/constants.py's OBJECT_PERMISSIONS — a fixed protocol vocabulary (a new object type
// needs a new backend route anyway), same rationale ApplicationCreateModal's SCOPE_GROUPS already
// hardcodes APPLICATION_SCOPES' values. A separate list from SCOPE_GROUPS since profiles also
// cover org/org_members/applications/profiles themselves, which an application's own scopes don't.
const PERMISSION_GROUPS: { label: string; permissions: { value: string; label: string }[] }[] = [
  { label: 'Organization', permissions: [{ value: 'org:write', label: 'Rename / describe org' }] },
  {
    label: 'Documents',
    permissions: [
      { value: 'documents:read', label: 'Read' },
      { value: 'documents:write', label: 'Write' },
    ],
  },
  {
    label: 'Categories',
    permissions: [
      { value: 'categories:read', label: 'Read' },
      { value: 'categories:write', label: 'Write' },
    ],
  },
  {
    label: 'Shelves',
    permissions: [
      { value: 'shelves:read', label: 'Read' },
      { value: 'shelves:write', label: 'Write' },
    ],
  },
  {
    label: 'Tags',
    permissions: [
      { value: 'tags:read', label: 'Read' },
      { value: 'tags:write', label: 'Write' },
    ],
  },
  {
    label: 'Embedding models',
    permissions: [
      { value: 'embedding_models:read', label: 'Read' },
      { value: 'embedding_models:write', label: 'Write' },
    ],
  },
  {
    label: 'Org members',
    permissions: [
      { value: 'org_members:read', label: 'Read' },
      { value: 'org_members:write', label: 'Write' },
    ],
  },
  {
    label: 'Connected applications',
    permissions: [
      { value: 'applications:read', label: 'Read' },
      { value: 'applications:write', label: 'Write' },
    ],
  },
  {
    label: 'Profiles',
    permissions: [
      { value: 'profiles:read', label: 'Read' },
      { value: 'profiles:write', label: 'Write' },
    ],
  },
  { label: 'Search', permissions: [{ value: 'queries:execute', label: 'Execute queries' }] },
]

interface Props {
  profile: Profile | null
  onClose: () => void
  onSaved: () => void
}

export function ProfileFormModal({ profile, onClose, onSaved }: Props) {
  const [name, setName] = useState(profile?.name ?? '')
  const [description, setDescription] = useState(profile?.description ?? '')
  const [permissions, setPermissions] = useState<string[]>(profile?.permissions ?? [])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isAdmin = profile?.is_admin ?? false

  function togglePermission(permission: string) {
    setPermissions((current) =>
      current.includes(permission) ? current.filter((entry) => entry !== permission) : [...current, permission]
    )
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      const body = { name, description: description || null, permissions }
      if (profile) {
        await api.patch(`/profiles/${profile.id}`, body)
      } else {
        await api.post('/profiles', body)
      }
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
      setSaving(false)
    }
  }

  return (
    <Modal title={profile ? 'Edit profile' : 'New profile'} onClose={onClose} maxWidthClassName="max-w-lg">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && (
          <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        <div>
          <label htmlFor="profile-name" className="mb-1.5 block text-sm text-foreground">
            Name
          </label>
          <input
            id="profile-name"
            autoFocus
            placeholder="e.g. Read-only Analyst"
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground placeholder:text-muted-foreground"
          />
        </div>
        <div>
          <label htmlFor="profile-description" className="mb-1.5 block text-sm text-foreground">
            Description
          </label>
          <textarea
            id="profile-description"
            rows={2}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground"
          />
        </div>
        <div>
          <span className="mb-2 block text-sm text-foreground">Permissions</span>
          {isAdmin ? (
            <p className="rounded-sm border border-border bg-secondary px-4 py-2.5 text-[13.5px] text-muted-foreground">
              Admin always has full read/write access to every object — not editable.
            </p>
          ) : (
            <div className="flex flex-col gap-3 rounded-sm border border-border p-4">
              {PERMISSION_GROUPS.map((group) => (
                <div key={group.label}>
                  <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {group.label}
                  </div>
                  <div className="flex flex-wrap gap-x-5 gap-y-1.5">
                    {group.permissions.map((permission) => (
                      <label key={permission.value} className="flex items-center gap-1.5 text-[13.5px] text-foreground">
                        <input
                          type="checkbox"
                          checked={permissions.includes(permission.value)}
                          onChange={() => togglePermission(permission.value)}
                          className="h-3.5 w-3.5"
                        />
                        {permission.label}
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="mt-2 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground">
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving || !name.trim() || (!isAdmin && permissions.length === 0)}
            className="rounded-sm bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
