import { ApiError, parseErrorBody } from './errors'
import { csrfToken } from './shell'

// Session+CSRF authenticated, not the resource client's cookie+CSRF fetch (client.ts) — these run
// before any session may even exist yet (sign-up/sign-in themselves), and always trigger a full
// page navigation on success (see each caller below) rather than client-side routing, since the
// destination may be /change-password or the post-login redirect target and Flask must re-serve a
// fresh SPA shell (fresh CSRF token, fresh org/role globals) for whichever page is next.
async function post(path: string, json: unknown): Promise<{ redirect: string }> {
  const response = await fetch(path, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() },
    body: JSON.stringify(json),
  })
  if (!response.ok) {
    const { message, code, field } = await parseErrorBody(response)
    throw new ApiError(message, response.status, code, field)
  }
  return (await response.json()) as { redirect: string }
}

export function signIn(email: string, password: string) {
  return post('/sign-in', { email, password })
}

export function signUp(email: string, password: string, name: string) {
  return post('/sign-up', { email, password, name })
}

export function changePassword(newPassword: string, confirmPassword: string) {
  return post('/change-password', { new_password: newPassword, confirm_password: confirmPassword })
}

export async function signOut(): Promise<void> {
  await fetch('/logout', { method: 'POST', credentials: 'include' })
}
