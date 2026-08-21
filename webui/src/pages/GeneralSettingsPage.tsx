import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { currentOrgId } from '../api/shell'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import { useOrgs } from '../api/queries'
import type { Org } from '../api/types'
import { useToast } from '../components/toastContext'

// Keyed by `org.id` in the parent so a freshly loaded org seeds initial state directly, no
// reset-effect or render-time setState needed (same pattern as EmbeddingModelsPage's form).
function OrgGeneralForm({ org }: { org: Org }) {
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [name, setName] = useState(org.name)
  const [description, setDescription] = useState(org.description ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const canEdit = org.permissions.includes('org:write')

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await api.patch(`/orgs/${org.id}`, { name, description: description || null })
      await queryClient.invalidateQueries({ queryKey: ['orgs'] })
      showToast('Org settings saved.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-lg">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-[22px] font-semibold text-foreground">Org settings</h2>
        {canEdit && (
          <button
            type="submit"
            form="org-settings-form"
            disabled={saving || !name.trim()}
            className="rounded-sm bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        )}
      </div>
      <form id="org-settings-form" onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && (
          <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        <div>
          <label htmlFor="org-name" className="mb-1.5 block text-sm text-foreground">
            Organization name
          </label>
          <input
            id="org-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={!canEdit}
            className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground disabled:opacity-60"
          />
        </div>
        <div>
          <span className="mb-1.5 block text-sm text-foreground">Workspace URL</span>
          <div className="flex items-center rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-muted-foreground">
            knowledge.app/{org.slug}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Not editable.</p>
        </div>
        <div>
          <label htmlFor="org-description" className="mb-1.5 block text-sm text-foreground">
            Description
          </label>
          <textarea
            id="org-description"
            rows={3}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            disabled={!canEdit}
            className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground disabled:opacity-60"
          />
        </div>
      </form>

      <div className="mt-12 rounded-sm border border-destructive/30 p-5">
        <h3 className="mb-1.5 text-sm font-semibold text-destructive">Delete organization</h3>
        <p className="mb-4 text-[13px] text-muted-foreground">
          Permanently deletes all documents, chunks, members and settings. This can&apos;t be undone.
        </p>
        <button
          type="button"
          disabled
          title="Not yet supported"
          className="cursor-not-allowed rounded-sm border border-destructive/40 px-4 py-2 text-sm text-destructive opacity-50"
        >
          Delete this organization
        </button>
      </div>
    </div>
  )
}

export function GeneralSettingsPage() {
  const orgs = useOrgs()
  const org = orgs.data?.find((entry) => entry.id === currentOrgId())

  if (orgs.isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>
  if (!org) return <p className="text-sm text-muted-foreground">Organization not found.</p>

  return <OrgGeneralForm key={org.id} org={org} />
}
