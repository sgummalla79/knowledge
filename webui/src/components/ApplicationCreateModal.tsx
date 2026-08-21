import { useState } from 'react'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import { useOrgMembers } from '../api/queries'
import type { Application, ApplicationAuthMethod, ApplicationWithClientSecret, ApplicationWithSecret } from '../api/types'
import { Modal } from './Modal'
import { Select } from './Select'

// Mirrors api/constants.py's APPLICATION_SCOPES — a fixed protocol vocabulary (a new scope needs
// a new backend route anyway), same rationale InviteMemberModal's ROLE_OPTIONS already hardcodes
// the org_member_role enum's values rather than fetching them.
const SCOPE_GROUPS: { label: string; scopes: { value: string; label: string }[] }[] = [
  {
    label: 'Documents',
    scopes: [
      { value: 'documents:read', label: 'Read' },
      { value: 'documents:write', label: 'Write' },
    ],
  },
  {
    label: 'Categories',
    scopes: [
      { value: 'categories:read', label: 'Read' },
      { value: 'categories:write', label: 'Write' },
    ],
  },
  {
    label: 'Shelves',
    scopes: [
      { value: 'shelves:read', label: 'Read' },
      { value: 'shelves:write', label: 'Write' },
    ],
  },
  {
    label: 'Tags',
    scopes: [
      { value: 'tags:read', label: 'Read' },
      { value: 'tags:write', label: 'Write' },
    ],
  },
  {
    label: 'Embedding models',
    scopes: [
      { value: 'embedding_models:read', label: 'Read' },
      { value: 'embedding_models:write', label: 'Write' },
    ],
  },
  {
    label: 'Org members',
    scopes: [
      { value: 'org_members:read', label: 'Read' },
      { value: 'org_members:write', label: 'Write' },
    ],
  },
  {
    label: 'Search',
    scopes: [{ value: 'queries:execute', label: 'Execute queries' }],
  },
]

const AUTH_METHOD_OPTIONS: { value: ApplicationAuthMethod; label: string }[] = [
  { value: 'api_key', label: 'API key (headless)' },
  { value: 'oauth_client_credentials', label: 'OAuth 2.0 (client credentials)' },
  { value: 'oauth_authorization_code', label: 'OAuth 2.0 (authorization code)' },
]

interface Props {
  orgId: string
  onClose: () => void
  onCreated: (application: ApplicationWithSecret | ApplicationWithClientSecret | Application) => void
}

export function ApplicationCreateModal({ orgId, onClose, onCreated }: Props) {
  const members = useOrgMembers(orgId)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [authMethod, setAuthMethod] = useState<ApplicationAuthMethod>('api_key')
  const [scopes, setScopes] = useState<string[]>([])
  const [executeAsIdentityId, setExecuteAsIdentityId] = useState('')
  const [redirectUrisText, setRedirectUrisText] = useState('')
  const [mcpAccess, setMcpAccess] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function toggleScope(scope: string) {
    setScopes((current) => (current.includes(scope) ? current.filter((entry) => entry !== scope) : [...current, scope]))
  }

  const memberOptions = (members.data ?? []).map((member) => ({ value: member.identity_id, label: `${member.name} (${member.email})` }))
  const redirectUris = redirectUrisText
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      const base = { name, description: description || null, auth_method: authMethod, mcp_access: mcpAccess }
      const body =
        authMethod === 'api_key'
          ? { ...base, scopes }
          : authMethod === 'oauth_client_credentials'
            ? { ...base, execute_as_identity_id: executeAsIdentityId }
            : { ...base, redirect_uris: redirectUris }
      const application = await api.post<ApplicationWithSecret | ApplicationWithClientSecret | Application>(
        '/applications',
        body
      )
      onCreated(application)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
      setSaving(false)
    }
  }

  const canSubmit =
    name.trim().length > 0 &&
    (authMethod === 'api_key'
      ? scopes.length > 0
      : authMethod === 'oauth_client_credentials'
        ? executeAsIdentityId.length > 0
        : redirectUris.length > 0)

  return (
    <Modal title="New connected application" onClose={onClose} maxWidthClassName="max-w-lg">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && (
          <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        <div>
          <label htmlFor="app-name" className="mb-1.5 block text-sm text-foreground">
            Name
          </label>
          <input
            id="app-name"
            autoFocus
            placeholder="e.g. MCP client"
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground placeholder:text-muted-foreground"
          />
        </div>
        <div>
          <label htmlFor="app-description" className="mb-1.5 block text-sm text-foreground">
            Description
          </label>
          <textarea
            id="app-description"
            rows={2}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground"
          />
        </div>
        <div>
          <label htmlFor="app-auth-method" className="mb-1.5 block text-sm text-foreground">
            Authentication method
          </label>
          <Select
            id="app-auth-method"
            value={authMethod}
            options={AUTH_METHOD_OPTIONS}
            onChange={(value) => setAuthMethod(value as ApplicationAuthMethod)}
            className="w-full px-4 py-2.5 text-[15px]"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            {authMethod === 'api_key' &&
              'A single bearer token, shown once at creation — the simplest way for a script or MCP client to authenticate.'}
            {authMethod === 'oauth_client_credentials' &&
              'A client_id/client_secret pair exchanged for a short-lived access token at POST /oauth/token — the token acts exactly as whichever member you pick below, with their current permissions.'}
            {authMethod === 'oauth_authorization_code' &&
              "A member connects this application themselves via a consent screen — the token acts as whoever consents, with their own current permissions. No secret to manage; it's a public, PKCE-only client."}
          </p>
        </div>
        {authMethod === 'api_key' ? (
          <div>
            <span className="mb-2 block text-sm text-foreground">Scopes</span>
            <div className="flex flex-col gap-3 rounded-sm border border-border p-4">
              {SCOPE_GROUPS.map((group) => (
                <div key={group.label}>
                  <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {group.label}
                  </div>
                  <div className="flex flex-wrap gap-x-5 gap-y-1.5">
                    {group.scopes.map((scope) => (
                      <label key={scope.value} className="flex items-center gap-1.5 text-[13.5px] text-foreground">
                        <input
                          type="checkbox"
                          checked={scopes.includes(scope.value)}
                          onChange={() => toggleScope(scope.value)}
                          className="h-3.5 w-3.5"
                        />
                        {scope.label}
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : authMethod === 'oauth_client_credentials' ? (
          <div>
            <label htmlFor="app-execute-as" className="mb-1.5 block text-sm text-foreground">
              Execute as
            </label>
            <Select
              id="app-execute-as"
              value={executeAsIdentityId}
              options={memberOptions}
              onChange={(value) => setExecuteAsIdentityId(value)}
              className="w-full px-4 py-2.5 text-[15px]"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              No scopes to pick — this application inherits exactly what this member's profile grants, and stays
              in sync if that profile changes later.
            </p>
          </div>
        ) : (
          <div>
            <label htmlFor="app-redirect-uris" className="mb-1.5 block text-sm text-foreground">
              Redirect URIs
            </label>
            <textarea
              id="app-redirect-uris"
              rows={3}
              placeholder={'One per line, e.g.\nhttp://127.0.0.1:51000/callback'}
              value={redirectUrisText}
              onChange={(event) => setRedirectUrisText(event.target.value)}
              className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground placeholder:text-muted-foreground"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Where this application is allowed to receive the consent redirect. For a local CLI/MCP client on
              127.0.0.1 or localhost, the port doesn't need to match exactly — only the host and path do.
            </p>
          </div>
        )}
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
                Lets this application reach this org's MCP tool tiers, if any are enabled under Settings &gt; MCP.
                Applies regardless of the authentication method above — the connecting identity's profile still
                gates each individual tool call.
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
            disabled={saving || !canSubmit}
            className="rounded-sm bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {saving ? 'Creating…' : 'Create application'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
