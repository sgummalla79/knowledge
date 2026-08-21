import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import { useOrgMembers } from '../api/queries'
import { currentOrgId } from '../api/shell'
import type { Application, ApplicationAuthMethod, ApplicationWithClientSecret, ApplicationWithSecret } from '../api/types'
import { Select } from '../components/Select'

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

type CreatedApplication = ApplicationWithSecret | ApplicationWithClientSecret | Application

// Routed at org/applications/new (see App.tsx) — a full page rather than a modal, same rationale
// ProfileFormPage already documents (the scope list needs room). On success, navigates back to
// the list with the created application in router state so it can open the one-time secret-reveal
// modal — that step stays a modal, since it's a single acknowledgement, not a form.
export function ApplicationCreatePage() {
  const orgId = currentOrgId()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const members = useOrgMembers(orgId ?? undefined)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [authMethod, setAuthMethod] = useState<ApplicationAuthMethod>('api_key')
  const [scopes, setScopes] = useState<string[]>([])
  const [executeAsIdentityId, setExecuteAsIdentityId] = useState('')
  const [redirectUrisText, setRedirectUrisText] = useState('')
  const [mcpAccess, setMcpAccess] = useState(false)
  const [apiAccess, setApiAccess] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function toggleScope(scope: string) {
    setScopes((current) => (current.includes(scope) ? current.filter((entry) => entry !== scope) : [...current, scope]))
  }

  function isDirty() {
    return (
      name !== '' ||
      description !== '' ||
      authMethod !== 'api_key' ||
      scopes.length > 0 ||
      executeAsIdentityId !== '' ||
      redirectUrisText !== '' ||
      mcpAccess ||
      !apiAccess
    )
  }

  function goBack() {
    if (isDirty() && !window.confirm('You have unsaved changes. Leave this page and lose them?')) return
    navigate('/org/applications')
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
      const base = {
        name,
        description: description || null,
        auth_method: authMethod,
        mcp_access: mcpAccess,
        api_access: apiAccess,
      }
      const body =
        authMethod === 'api_key'
          ? { ...base, scopes }
          : authMethod === 'oauth_client_credentials'
            ? { ...base, execute_as_identity_id: executeAsIdentityId }
            : { ...base, redirect_uris: redirectUris }
      const application = await api.post<CreatedApplication>('/applications', body)
      void queryClient.invalidateQueries({ queryKey: ['applications'] })
      navigate('/org/applications', { state: { justCreated: application } })
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
    <div>
      <button
        type="button"
        onClick={goBack}
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <span aria-hidden="true">←</span> Back to connected applications
      </button>
      <div className="mb-6 flex max-w-4xl items-center justify-between">
        <h2 className="text-[22px] font-semibold text-foreground">New connected application</h2>
        <button
          type="submit"
          form="application-form"
          disabled={saving || !canSubmit}
          className="rounded-sm bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
        >
          {saving ? 'Creating…' : 'Create application'}
        </button>
      </div>

      <form id="application-form" onSubmit={handleSubmit} className="flex max-w-4xl flex-col gap-4">
        {error && (
          <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        <div className="grid grid-cols-2 gap-8">
          <div className="flex flex-col gap-4">
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
                rows={3}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className="w-full resize-y rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground"
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
            {authMethod === 'oauth_client_credentials' ? (
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
                  No scopes to pick — this application inherits exactly what this member's profile grants, and
                  stays in sync if that profile changes later.
                </p>
              </div>
            ) : authMethod === 'oauth_authorization_code' ? (
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
                  className="w-full resize-y rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground placeholder:text-muted-foreground"
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  Where this application is allowed to receive the consent redirect. For a local CLI/MCP client on
                  127.0.0.1 or localhost, the port doesn't need to match exactly — only the host and path do.
                </p>
              </div>
            ) : null}
          </div>
          <div>
            <span className="mb-2 block text-sm text-foreground">Scopes</span>
            <div className="grid grid-cols-2 gap-x-6 gap-y-4 rounded-sm border border-border p-4">
              {/* documents/categories/etc. scopes only mean anything for api_key — the two OAuth
                  methods inherit permissions from whichever identity is connected, so only the API/
                  MCP access toggles (channel flags, not real scopes — see api/constants.py's
                  APPLICATION_SCOPES vs. applications.api_access/mcp_access) are shown for them. */}
              {authMethod === 'api_key' &&
                SCOPE_GROUPS.map((group) => (
                  <div key={group.label}>
                    <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      {group.label}
                    </div>
                    <div className="flex flex-col gap-1">
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
              <div>
                <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">API</div>
                <div className="flex flex-col gap-1">
                  <label className="flex items-center gap-1.5 text-[13.5px] text-foreground">
                    <input
                      type="checkbox"
                      checked={apiAccess}
                      onChange={(event) => setApiAccess(event.target.checked)}
                      className="h-3.5 w-3.5"
                    />
                    API access
                  </label>
                </div>
              </div>
              <div>
                <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">MCP</div>
                <div className="flex flex-col gap-1">
                  <label className="flex items-center gap-1.5 text-[13.5px] text-foreground">
                    <input
                      type="checkbox"
                      checked={mcpAccess}
                      onChange={(event) => setMcpAccess(event.target.checked)}
                      className="h-3.5 w-3.5"
                    />
                    MCP access
                  </label>
                </div>
              </div>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              API access gates the plain REST API (documents, categories, etc. above) — without it, this
              application can't call any REST endpoint regardless of what's checked above. MCP access lets it
              reach this org's MCP tool tiers instead, if any are enabled under Settings &gt; MCP. Both are
              available for all three authentication methods, and the connecting identity's profile still gates
              each individual call either way.
            </p>
          </div>
        </div>
      </form>
    </div>
  )
}
