import { API_BASE_URL } from './config'
import { ApiError, parseErrorBody } from './errors'
import { csrfToken } from './shell'
import type { OAuthAuthorizeRequest, OAuthErrorInfo } from './shell'

export type AuthorizeContext =
  | { kind: 'error'; error: OAuthErrorInfo }
  | { kind: 'redirect'; redirect: string }
  | { kind: 'authorize'; request: OAuthAuthorizeRequest }

// JSON replacement for the deleted GET /oauth/authorize HTML-rendering route (see
// api/presentation/routes/oauth.py's authorize_context()) — fetched by AuthorizePage on mount
// instead of reading window.__OAUTH_AUTHORIZE__/__OAUTH_ERROR__, which nothing injects anymore.
export async function fetchAuthorizeContext(searchParams: string): Promise<AuthorizeContext> {
  const response = await fetch(`${API_BASE_URL}/oauth/authorize-context?${searchParams}`, { credentials: 'include' })
  const body = (await response.json()) as { error?: OAuthErrorInfo; redirect?: string; authorize?: OAuthAuthorizeRequest }
  if (body.error) return { kind: 'error', error: body.error }
  if (body.redirect) return { kind: 'redirect', redirect: body.redirect }
  return { kind: 'authorize', request: body.authorize as OAuthAuthorizeRequest }
}

// Same session+CSRF pattern as auth.ts's sign-in/sign-up (not the resource client's cookie+CSRF
// fetch in client.ts) — the response is always a redirect URL the caller navigates to with
// window.location.href, since the final hop may be cross-origin (the app's own redirect_uri).
export async function submitAuthorizeDecision(
  request: OAuthAuthorizeRequest,
  allow: boolean
): Promise<{ redirect: string }> {
  const response = await fetch(`${API_BASE_URL}/oauth/authorize`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() },
    body: JSON.stringify({ ...request, allow }),
  })
  if (!response.ok) {
    const { message, code, field } = await parseErrorBody(response)
    throw new ApiError(message, response.status, code, field)
  }
  return (await response.json()) as { redirect: string }
}
