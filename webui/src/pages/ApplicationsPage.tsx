import { useState } from 'react'
import { GridIcon } from '../components/icons'
import { ApplicationInfoModal } from '../components/ApplicationInfoModal'
import { useToast } from '../components/toastContext'
import { useApplications, useDeleteApplication, useRevokeApplicationToken } from '../api/applicationQueries'
import type { Application } from '../api/types'

function TokenBadge({ status }: { status: Application['token_status'] }) {
  if (status === 'active') return <span className="badge status-completed">active</span>
  if (status === 'revoked') return <span className="badge status-failed">revoked</span>
  return <span className="badge status-failed">none issued</span>
}

export function ApplicationsPage() {
  const { showToast } = useToast()
  const { data: applications, isLoading } = useApplications()
  const revoke = useRevokeApplicationToken()
  const deleteApp = useDeleteApplication()

  const [viewing, setViewing] = useState<Application | null>(null)

  function handleDelete(application: Application) {
    if (!window.confirm(`Delete "${application.name}"? This permanently removes its credentials and token — this cannot be undone.`)) return
    deleteApp.mutate(application.id, { onError: (error) => showToast(error.message) })
  }

  return (
    <>
      <div className="settings-narrow">
        <div className="page-header">
          <div className="page-header-left">
            <div className="page-header-icon">
              <GridIcon />
            </div>
            <div>
              <h1>Applications</h1>
              <p className="subtitle">
                Registered OAuth2 clients — each has its own client ID/secret and a scoped access token.
              </p>
            </div>
          </div>
        </div>

        {isLoading && <p className="subtitle">Loading…</p>}

        {!isLoading && (applications ?? []).length === 0 && (
          <div className="empty-state-panel">
            <GridIcon className="empty-state-icon" />
            <p>No applications registered.</p>
          </div>
        )}

        {(applications ?? []).length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Application Name</th>
                <th>Last used</th>
                <th>Token</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(applications ?? []).map((application) => (
                <tr key={application.id}>
                  <td>
                    {application.name}
                    <button
                      type="button"
                      className="info-icon-btn"
                      aria-label="Show application details"
                      title="Show application details"
                      onClick={() => setViewing(application)}
                    >
                      i
                    </button>
                  </td>
                  <td>{application.last_used_at ?? '—'}</td>
                  <td>
                    <TokenBadge status={application.token_status} />
                  </td>
                  <td>
                    <div className="row-actions">
                      <button
                        type="button"
                        className="danger"
                        disabled={application.token_status !== 'active' || revoke.isPending}
                        onClick={() => revoke.mutate(application.id, { onError: (error) => showToast(error.message) })}
                      >
                        Revoke
                      </button>
                      <button
                        type="button"
                        className="danger"
                        disabled={deleteApp.isPending}
                        onClick={() => handleDelete(application)}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {viewing && <ApplicationInfoModal application={viewing} onClose={() => setViewing(null)} />}
    </>
  )
}
