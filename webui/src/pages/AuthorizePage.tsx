import { useState } from 'react'
import { submitAuthorizeDecision } from '../api/oauth'
import { AuthCard } from '../components/AuthCard'

// Reads window.__OAUTH_AUTHORIZE__/__OAUTH_ERROR__, injected by GET /oauth/authorize (see
// api/presentation/routes/oauth.py) — whichever one the server decided to render. There's no
// scope picker here: this app has nothing of its own to authorize per request — the resulting
// token is simply capped at whatever the signed-in member's own profile already grants, so the
// only real decision is "let this application act as me, yes or no."
export function AuthorizePage() {
  const request = window.__OAUTH_AUTHORIZE__
  const error = window.__OAUTH_ERROR__
  const [submitting, setSubmitting] = useState(false)
  const [failure, setFailure] = useState<string | null>(null)

  async function handleDecision(allow: boolean) {
    if (!request) return
    setSubmitting(true)
    setFailure(null)
    try {
      const { redirect } = await submitAuthorizeDecision(request, allow)
      window.location.href = redirect
    } catch {
      setFailure('Something went wrong — please try again.')
      setSubmitting(false)
    }
  }

  if (error) {
    return (
      <AuthCard eyebrow="Connection request" title="Can't connect this application" subtitle={error.message} footer={null}>
        <p className="text-sm text-muted-foreground">You can close this window.</p>
      </AuthCard>
    )
  }

  if (!request) {
    return (
      <AuthCard eyebrow="Connection request" title="Invalid request" subtitle="This page was opened without a valid connection request." footer={null}>
        <p className="text-sm text-muted-foreground">You can close this window.</p>
      </AuthCard>
    )
  }

  return (
    <AuthCard
      eyebrow="Connection request"
      title={`Connect "${request.application_name}"`}
      subtitle={`This application wants to access "${request.org_name}" using your own permissions.`}
      footer={null}
    >
      <div className="flex flex-col gap-4">
        <p className="text-[13.5px] text-muted-foreground">
          It will be able to do exactly what you can do — nothing more. If your access changes later, so does
          what this application can do.
        </p>
        {failure && (
          <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {failure}
          </div>
        )}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            disabled={submitting}
            onClick={() => void handleDecision(false)}
            className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground disabled:opacity-60"
          >
            Deny
          </button>
          <button
            type="button"
            disabled={submitting}
            onClick={() => void handleDecision(true)}
            className="rounded-sm bg-primary px-5 py-2.5 text-[15px] font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {submitting ? 'Connecting…' : 'Allow'}
          </button>
        </div>
      </div>
    </AuthCard>
  )
}
