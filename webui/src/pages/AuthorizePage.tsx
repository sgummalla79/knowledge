import { useState } from 'react'
import { AuthLayout } from '../components/AuthLayout'
import { useToast } from '../components/toastContext'
import { submitOauthAuthorize } from '../api/auth'
import { oauthAuthorizeData, oauthError } from '../api/shell'

export function AuthorizePage() {
  const { showToast } = useToast()
  const data = oauthAuthorizeData()
  const errorMessage = oauthError()
  const [pending, setPending] = useState<'approve' | 'deny' | null>(null)

  async function handleAction(action: 'approve' | 'deny') {
    if (!data) return
    setPending(action)
    try {
      const result = await submitOauthAuthorize(data.params, action)
      window.location.href = result.redirect
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Authorization failed.')
      setPending(null)
    }
  }

  if (errorMessage) {
    return (
      <AuthLayout title="Knowledge">
        <h1>Can't complete authorization</h1>
        <div className="error-banner">{errorMessage}</div>
      </AuthLayout>
    )
  }

  if (!data) {
    return (
      <AuthLayout title="Knowledge">
        <h1>Can't complete authorization</h1>
        <div className="error-banner">Missing authorization request.</div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout title="Knowledge">
      <h1>Authorize {data.application_name}</h1>
      <p className="subtitle">This application is requesting the following access to your Knowledge libraries:</p>
      <div className="scope-tag-list">
        {data.params.scope.map((scope) => (
          <span key={scope} className="scope-tag">
            {scope}
          </span>
        ))}
      </div>
      <div className="modal-actions" style={{ justifyContent: 'flex-start' }}>
        <button type="button" disabled={pending !== null} onClick={() => handleAction('approve')}>
          Approve
        </button>
        <button type="button" className="secondary" disabled={pending !== null} onClick={() => handleAction('deny')}>
          Deny
        </button>
      </div>
    </AuthLayout>
  )
}
