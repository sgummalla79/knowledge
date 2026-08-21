import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import { usePersonalAccessTokens } from '../api/queries'
import type { PersonalAccessToken, PersonalAccessTokenWithSecret } from '../api/types'
import { ApplicationSecretRevealModal } from '../components/ApplicationSecretRevealModal'
import { Modal } from '../components/Modal'
import { useToast } from '../components/toastContext'

function formatDate(value: string | null): string {
  if (!value) return 'Never'
  return new Date(value).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

interface CreateModalProps {
  onClose: () => void
  onCreated: (token: PersonalAccessTokenWithSecret) => void
}

function CreateApiKeyModal({ onClose, onCreated }: CreateModalProps) {
  const [name, setName] = useState('')
  const [mcpAccess, setMcpAccess] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      const token = await api.post<PersonalAccessTokenWithSecret>('/personal-access-tokens', {
        name,
        mcp_access: mcpAccess,
      })
      onCreated(token)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
      setSaving(false)
    }
  }

  return (
    <Modal title="New API key" onClose={onClose}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && (
          <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        <div>
          <label htmlFor="key-name" className="mb-1.5 block text-sm text-foreground">
            Name
          </label>
          <input
            id="key-name"
            autoFocus
            placeholder="e.g. My laptop"
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground placeholder:text-muted-foreground"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Acts with your own current permissions in this org — nothing to pick, nothing to keep in sync.
          </p>
        </div>
        <div>
          <label className="flex items-start gap-2.5">
            <input
              type="checkbox"
              checked={mcpAccess}
              onChange={(event) => setMcpAccess(event.target.checked)}
              className="mt-0.5 h-3.5 w-3.5"
            />
            <span>
              <span className="block text-[15px] text-foreground">MCP access</span>
              <span className="block text-[13px] text-muted-foreground">
                Lets this key reach this org's MCP tool tiers, if any are enabled under Settings &gt; MCP.
              </span>
            </span>
          </label>
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
            {saving ? 'Creating…' : 'Create key'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

// Routed at /account/api-keys (see App.tsx), outside SettingsLayout — this is personal, not
// org-admin. Self-service: any org member manages their own keys here, no applications:write-style
// permission required (see api/presentation/routes/personal_access_tokens.py's require_org_session
// gate). Scoped to whichever org is currently active, same as everything else in this app.
export function ApiKeysPage() {
  const tokens = usePersonalAccessTokens()
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [creating, setCreating] = useState(false)
  const [revealing, setRevealing] = useState<PersonalAccessTokenWithSecret | null>(null)

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ['personal-access-tokens'] })
  }

  async function handleDelete(token: PersonalAccessToken) {
    if (!window.confirm(`Delete "${token.name}"? Anything using it will immediately lose access.`)) return
    try {
      await api.delete(`/personal-access-tokens/${token.id}`)
      invalidate()
      showToast('API key deleted.')
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : 'Something went wrong — please try again.', 'error')
    }
  }

  return (
    <div className="py-12">
      <div className="mb-1.5 flex items-baseline justify-between">
        <h2 className="text-[22px] font-semibold text-foreground">API keys</h2>
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="rounded-sm bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
        >
          New API key
        </button>
      </div>
      <p className="mb-6 max-w-xl text-[13.5px] text-muted-foreground">
        A personal API key lets a script or tool access this org's data as you, with your own current
        permissions. It's yours alone — only you can see, create, or delete it.
      </p>

      {tokens.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {tokens.data && tokens.data.length === 0 && <p className="text-sm text-muted-foreground">No API keys yet.</p>}
      {tokens.data && tokens.data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
                <th className="pb-2.5 font-semibold">Name</th>
                <th className="pb-2.5 font-semibold">Key</th>
                <th className="pb-2.5 font-semibold">MCP access</th>
                <th className="pb-2.5 font-semibold">Created</th>
                <th className="pb-2.5 font-semibold">Last used</th>
                <th className="pb-2.5 font-semibold"></th>
              </tr>
            </thead>
            <tbody>
              {tokens.data.map((token) => (
                <tr key={token.id} className="border-t border-border align-top">
                  <td className="py-3.5 pr-4 font-semibold text-foreground">{token.name}</td>
                  <td className="py-3.5 pr-4">
                    <code className="text-[12.5px] text-muted-foreground">{token.token_prefix}…</code>
                  </td>
                  <td className="py-3.5 pr-4 text-[13px] text-foreground">{token.mcp_access ? 'Yes' : 'No'}</td>
                  <td className="py-3.5 pr-4 text-[13px] text-foreground">{formatDate(token.created_at)}</td>
                  <td className="py-3.5 pr-4 text-[13px] text-foreground">{formatDate(token.last_used_at)}</td>
                  <td className="py-3.5 text-right">
                    <button
                      type="button"
                      onClick={() => void handleDelete(token)}
                      className="text-[13px] text-destructive hover:underline"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {creating && (
        <CreateApiKeyModal
          onClose={() => setCreating(false)}
          onCreated={(token) => {
            invalidate()
            setCreating(false)
            setRevealing(token)
          }}
        />
      )}

      {revealing && (
        <ApplicationSecretRevealModal
          applicationName={revealing.name}
          fields={[{ label: 'API key', value: revealing.token }]}
          onClose={() => setRevealing(null)}
        />
      )}
    </div>
  )
}
