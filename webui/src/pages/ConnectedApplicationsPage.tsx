import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import { useApplications, useOrgMembers, useOrgs } from '../api/queries'
import { currentOrgId } from '../api/shell'
import type { Application, ApplicationWithClientSecret } from '../api/types'
import { ApplicationSecretRevealModal } from '../components/ApplicationSecretRevealModal'
import { ApplicationsTable } from '../components/ApplicationsTable'
import { useToast } from '../components/toastContext'

type CreatedApplication = ApplicationWithClientSecret | Application

function secretFields(application: CreatedApplication) {
  if ('client_secret' in application) {
    return [
      { label: 'Client ID', value: application.client_id },
      { label: 'Client secret', value: application.client_secret },
    ]
  }
  return []
}

export function ConnectedApplicationsPage() {
  const orgs = useOrgs()
  const orgId = currentOrgId()
  const applications = useApplications()
  const members = useOrgMembers(orgId ?? undefined)
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  // ApplicationCreatePage (setup/applications/new) hands the freshly created application back via
  // router state rather than a callback prop, since it's a separate routed page now, not a modal
  // rendered inline here. oauth_authorization_code has nothing secret to show (a public,
  // PKCE-only client), so only open the reveal step when there's actually a secret to reveal.
  const justCreated = location.state?.justCreated as CreatedApplication | undefined
  const [revealing, setRevealing] = useState<CreatedApplication | null>(
    justCreated && secretFields(justCreated).length > 0 ? justCreated : null
  )
  useEffect(() => {
    // Runs once per navigation into this page with fresh state — clears it immediately so a
    // later back-navigation or refresh doesn't reopen the reveal modal (setRevealing above
    // already captured what it needed from justCreated before this fires).
    if (justCreated) navigate(location.pathname, { replace: true, state: null })
  }, [justCreated])

  const org = orgs.data?.find((entry) => entry.id === orgId)
  const canManage = org?.permissions.includes('applications:write') ?? false

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ['applications'] })
  }

  async function handleRotateKey(application: Application) {
    try {
      const updated = await api.post<ApplicationWithClientSecret>(`/applications/${application.id}/rotate-key`)
      invalidate()
      setRevealing(updated)
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : 'Something went wrong — please try again.', 'error')
    }
  }

  async function handleRevoke(application: Application) {
    if (!window.confirm(`Revoke "${application.name}"? It will immediately lose API access.`)) return
    try {
      await api.post(`/applications/${application.id}/revoke`)
      invalidate()
      showToast('Application revoked.')
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : 'Something went wrong — please try again.', 'error')
    }
  }

  async function handleDelete(application: Application) {
    if (!window.confirm(`Permanently delete "${application.name}"?`)) return
    try {
      await api.delete(`/applications/${application.id}`)
      invalidate()
      showToast('Application deleted.')
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : 'Something went wrong — please try again.', 'error')
    }
  }

  if (!orgId) return <p className="text-sm text-muted-foreground">No active organization.</p>

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <h2 className="text-[22px] font-semibold text-foreground">Connected applications</h2>
        {canManage && (
          <button
            type="button"
            onClick={() => navigate('/setup/applications/new')}
            className="rounded-sm bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
          >
            New application
          </button>
        )}
      </div>
      <p className="mb-6 max-w-xl text-[13.5px] text-muted-foreground">
        Connected applications let an external tool or script — an MCP client, a CI job, an integration — access
        this org&apos;s data through the API, scoped to only what it needs.
      </p>

      {applications.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {applications.data && applications.data.length === 0 && (
        <p className="text-sm text-muted-foreground">No connected applications yet.</p>
      )}
      {applications.data && applications.data.length > 0 && (
        <ApplicationsTable
          applications={applications.data}
          members={members.data ?? []}
          canManage={canManage}
          onRotateKey={(application) => void handleRotateKey(application)}
          onRevoke={(application) => void handleRevoke(application)}
          onDelete={(application) => void handleDelete(application)}
        />
      )}

      {revealing && (
        <ApplicationSecretRevealModal
          applicationName={revealing.name}
          fields={secretFields(revealing)}
          onClose={() => setRevealing(null)}
        />
      )}
    </div>
  )
}
