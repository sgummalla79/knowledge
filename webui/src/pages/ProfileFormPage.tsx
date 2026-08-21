import { useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import { useProfiles } from '../api/queries'

// Mirrors api/constants.py's OBJECT_PERMISSIONS — a fixed protocol vocabulary (a new object type
// needs a new backend route anyway), same rationale ApplicationCreatePage's SCOPE_GROUPS already
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

// Routed at org/profiles/new and org/profiles/:id/edit (see App.tsx) — a full page rather than a
// modal so a permission list this long has room to breathe. The back link (not a browser-history
// back, an explicit link to the list) doubles as the page's "cancel" action; it warns before
// discarding unsaved changes rather than needing a separate Cancel button.
export function ProfileFormPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const profiles = useProfiles()
  const profile = id ? profiles.data?.find((entry) => entry.id === id) : null

  const [name, setName] = useState(profile?.name ?? '')
  const [description, setDescription] = useState(profile?.description ?? '')
  const [permissions, setPermissions] = useState<string[]>(profile?.permissions ?? [])
  const [initialized, setInitialized] = useState(profile !== null && profile !== undefined)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isAdmin = profile?.is_admin ?? false

  // Snapshot of the fields' just-loaded values, taken once (see the sync effect below) — compared
  // against current state to decide whether Back needs to warn about unsaved changes.
  const initialSnapshot = useRef<{ name: string; description: string; permissions: string[] } | null>(
    initialized ? { name: profile?.name ?? '', description: profile?.description ?? '', permissions: profile?.permissions ?? [] } : null
  )

  // Profiles load async (useProfiles), so on a hard refresh of an edit URL the form fields above
  // may have initialized empty before the fetch resolved — sync once, the first time real data
  // shows up, without clobbering whatever the user's already typed on later re-renders.
  if (!initialized && profile) {
    setName(profile.name)
    setDescription(profile.description ?? '')
    setPermissions(profile.permissions)
    setInitialized(true)
    initialSnapshot.current = { name: profile.name, description: profile.description ?? '', permissions: profile.permissions }
  }

  function togglePermission(permission: string) {
    setPermissions((current) =>
      current.includes(permission) ? current.filter((entry) => entry !== permission) : [...current, permission]
    )
  }

  function isDirty() {
    const initial = initialSnapshot.current
    if (!initial) return name !== '' || description !== '' || permissions.length > 0
    return (
      name !== initial.name ||
      description !== initial.description ||
      permissions.length !== initial.permissions.length ||
      permissions.some((permission) => !initial.permissions.includes(permission))
    )
  }

  function goBack() {
    if (isDirty() && !window.confirm('You have unsaved changes. Leave this page and lose them?')) return
    navigate('/org/profiles')
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      const body = { name, description: description || null, permissions }
      if (id) {
        await api.patch(`/profiles/${id}`, body)
      } else {
        await api.post('/profiles', body)
      }
      void queryClient.invalidateQueries({ queryKey: ['profiles'] })
      goBack()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
      setSaving(false)
    }
  }

  if (id && profiles.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>
  }

  return (
    <div>
      <button
        type="button"
        onClick={goBack}
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <span aria-hidden="true">←</span> Back to profiles
      </button>
      <div className="mb-6 flex max-w-4xl items-center justify-between">
        <h2 className="text-[22px] font-semibold text-foreground">{id ? 'Edit profile' : 'New profile'}</h2>
        <button
          type="submit"
          form="profile-form"
          disabled={saving || !name.trim() || (!isAdmin && permissions.length === 0)}
          className="rounded-sm bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>

      <form id="profile-form" onSubmit={handleSubmit} className="flex max-w-4xl flex-col gap-4">
        {error && (
          <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        <div className="grid grid-cols-2 gap-8">
          <div className="flex flex-col gap-4">
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
                rows={3}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className="w-full resize-y rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground"
              />
            </div>
          </div>
          <div>
            <span className="mb-2 block text-sm text-foreground">Permissions</span>
            {isAdmin ? (
              <p className="rounded-sm border border-border bg-secondary px-4 py-2.5 text-[13.5px] text-muted-foreground">
                Admin always has full read/write access to every object — not editable.
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-x-6 gap-y-4 rounded-sm border border-border p-4">
                {PERMISSION_GROUPS.map((group) => (
                  <div key={group.label}>
                    <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      {group.label}
                    </div>
                    <div className="flex flex-col gap-1">
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
        </div>
      </form>
    </div>
  )
}
