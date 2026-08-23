import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import { currentOrgId } from '../api/shell'
import { useMCPSettings, useOrgs } from '../api/queries'
import type { MCPSettings } from '../api/types'
import { useToast } from '../components/toastContext'

const TIERS: { key: keyof Pick<MCPSettings, 'search_read_enabled' | 'object_read_enabled' | 'object_write_enabled'>; label: string; description: string }[] = [
  {
    key: 'search_read_enabled',
    label: 'Search',
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

function CopyableValue({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    await navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="flex items-start gap-2 rounded-sm border border-border bg-secondary px-3.5 py-3">
      <code className="flex-1 overflow-x-auto whitespace-pre-wrap break-all text-[12.5px] text-foreground">{value}</code>
      <button
        type="button"
        onClick={() => void handleCopy()}
        className="shrink-0 rounded-sm bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:opacity-90"
      >
        {copied ? 'Copied' : 'Copy'}
      </button>
    </div>
  )
}

// Keyed by settings.org_id in the parent so a freshly loaded row seeds initial state directly, no
// reset-effect or render-time setState needed (same pattern as EmbeddingModelsPage's form).
//
// Every org's tools live at /<org-slug>/mcp/<tier>, not a bare /mcp/<tier> — the server rejects
// that bare path outright, and rejects an org-prefixed one whose bearer token belongs to a
// different org (see api/presentation/web/mcp_org_scoping.py). orgSlug is *this* org's, from
// useOrgs()'s Org.slug — not derived from the browser's current URL, which this page shouldn't
// depend on matching (even though App.tsx already self-corrects a mismatched one). <tier> itself
// comes from settings.tier_url_segments (GET /mcp-settings), not a hardcoded frontend mapping —
// see api.constants.MCP_TIERS, the single source both that response and
// api/mcp_server/permissions.py derive from.
function MCPSettingsForm({ settings, canWrite, orgSlug }: { settings: MCPSettings; canWrite: boolean; orgSlug: string }) {
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [values, setValues] = useState({
    search_read_enabled: settings.search_read_enabled,
    object_read_enabled: settings.object_read_enabled,
    object_write_enabled: settings.object_write_enabled,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const dirty =
    values.search_read_enabled !== settings.search_read_enabled ||
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

  const origin = window.location.origin

  return (
    <div className="max-w-2xl">
      <div className="mb-1.5 flex items-center justify-between">
        <h2 className="text-[22px] font-semibold text-foreground">MCP</h2>
        {canWrite && (
          <button
            type="submit"
            form="mcp-settings-form"
            disabled={saving || !dirty}
            className="rounded-sm bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        )}
      </div>
      <p className="mb-6 text-sm text-muted-foreground">
        This org's data is exposed over MCP as three separate tool tiers, each off by default. A connected
        application also needs its own MCP access (set when creating it) to reach any of them, and every tool call
        still checks the connecting identity's profile permissions.
      </p>

      <div className="mb-6 rounded-sm border border-border p-4">
        <h3 className="mb-1.5 text-[15px] font-semibold text-foreground">Connect an AI agent</h3>
        <p className="text-[13px] text-muted-foreground">
          Create a{' '}
          <Link to="/user/api-keys" className="text-foreground underline">
            personal access token
          </Link>{' '}
          with MCP access checked, then point your agent at a tier's URL below, sending the token
          as a Bearer header. A tier only responds once it's enabled and saved.
        </p>
        <p className="mt-2 text-[12.5px] text-muted-foreground">
          Streamable HTTP transport, with an{' '}
          <code className="text-foreground">Authorization: Bearer &lt;token&gt;</code> header. For
          Claude Code specifically:{' '}
          <code className="text-foreground">
            claude mcp add --transport http knowledge-search &lt;url&gt; --header "Authorization:
            Bearer &lt;token&gt;"
          </code>
        </p>
      </div>

      <form id="mcp-settings-form" onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && (
          <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        <div className="flex flex-col gap-5 rounded-sm border border-border p-4">
          {TIERS.map((tier) => (
            <div key={tier.key}>
              <label className="flex items-start gap-2.5">
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
              <div className="mt-2 pl-6">
                <CopyableValue value={`${origin}/${orgSlug}/mcp/${settings.tier_url_segments[tier.key]}`} />
              </div>
            </div>
          ))}
        </div>
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

  return (
    <MCPSettingsForm
      key={settings.data.org_id}
      settings={settings.data}
      canWrite={org.permissions.includes('mcp_settings:write')}
      orgSlug={org.slug}
    />
  )
}
