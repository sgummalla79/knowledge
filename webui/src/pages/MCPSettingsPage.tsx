import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import { currentOrgId } from '../api/shell'
import { useMCPSettings, useOrgs } from '../api/queries'
import type { MCPSettings } from '../api/types'
import { useToast } from '../components/toastContext'

const TIERS: { key: keyof Pick<MCPSettings, 'rag_read_enabled' | 'object_read_enabled' | 'object_write_enabled'>; label: string; description: string }[] = [
  {
    key: 'rag_read_enabled',
    label: 'RAG (search)',
    description: 'search, list_categories, get_document, get_document_chunks — hybrid search and reading what it found.',
  },
  {
    key: 'object_read_enabled',
    label: 'Object read',
    description: 'list_shelves, list_documents, list_tags, list_embedding_models — listing beyond search results.',
  },
  {
    key: 'object_write_enabled',
    label: 'Object write',
    description:
      'Create, rename, and delete documents, categories, shelves, and tags. Content only — org members, profiles, and applications are never reachable over MCP regardless of this toggle.',
  },
]

// Keyed by settings.org_id in the parent so a freshly loaded row seeds initial state directly, no
// reset-effect or render-time setState needed (same pattern as EmbeddingModelsPage's form).
function MCPSettingsForm({ settings, canWrite }: { settings: MCPSettings; canWrite: boolean }) {
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [values, setValues] = useState({
    rag_read_enabled: settings.rag_read_enabled,
    object_read_enabled: settings.object_read_enabled,
    object_write_enabled: settings.object_write_enabled,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const dirty =
    values.rag_read_enabled !== settings.rag_read_enabled ||
    values.object_read_enabled !== settings.object_read_enabled ||
    values.object_write_enabled !== settings.object_write_enabled

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await api.put('/mcp-settings', values)
      await queryClient.invalidateQueries({ queryKey: ['mcp-settings'] })
      showToast('MCP settings saved.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-lg">
      <h2 className="mb-1.5 text-[22px] font-semibold text-foreground">MCP</h2>
      <p className="mb-5 text-sm text-muted-foreground">
        This org's data is exposed over MCP as three separate tool tiers, each off by default. A connected
        application also needs its own MCP access (set when creating it) to reach any of them, and every tool call
        still checks the connecting identity's profile permissions.
      </p>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && (
          <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        <div className="flex flex-col gap-3 rounded-sm border border-border p-4">
          {TIERS.map((tier) => (
            <label key={tier.key} className="flex items-start gap-2.5">
              <input
                type="checkbox"
                checked={values[tier.key]}
                onChange={(event) => setValues((current) => ({ ...current, [tier.key]: event.target.checked }))}
                disabled={!canWrite}
                className="mt-0.5 h-3.5 w-3.5 disabled:opacity-60"
              />
              <span>
                <span className="block text-[15px] text-foreground">{tier.label}</span>
                <span className="block text-[13px] text-muted-foreground">{tier.description}</span>
              </span>
            </label>
          ))}
        </div>
        {canWrite && (
          <button
            type="submit"
            disabled={saving || !dirty}
            className="w-fit rounded-sm bg-primary px-5 py-2.5 text-[15px] font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        )}
      </form>
    </div>
  )
}

export function MCPSettingsPage() {
  const orgs = useOrgs()
  const settings = useMCPSettings()
  const org = orgs.data?.find((entry) => entry.id === currentOrgId())

  if (orgs.isLoading || settings.isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>
  if (!org || !settings.data) return <p className="text-sm text-muted-foreground">Organization not found.</p>

  return <MCPSettingsForm key={settings.data.org_id} settings={settings.data} canWrite={org.permissions.includes('mcp_settings:write')} />
}
