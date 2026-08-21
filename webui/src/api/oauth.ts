import { ApiError, parseErrorBody } from './errors'
import { csrfToken } from './shell'
import type { OAuthAuthorizeRequest } from './shell'

// Same session+CSRF pattern as auth.ts's sign-in/sign-up (not the resource client's cookie+CSRF
// fetch in client.ts) — the response is always a redirect URL the caller navigates to with
// window.location.href, since the final hop may be cross-origin (the app's own redirect_uri).
export async function submitAuthorizeDecision(
  request: OAuthAuthorizeRequest,
  allow: boolean
): Promise<{ redirect: string }> {
  const response = await fetch('/oauth/authorize', {
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
