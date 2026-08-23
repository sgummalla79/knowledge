import { API_BASE_URL } from './config'
import { ApiError, parseErrorBody } from './errors'
import { csrfToken } from './shell'

// Session+CSRF authenticated, not the resource client's cookie+CSRF fetch (client.ts) — these run
// before any session may even exist yet (sign-up/sign-in themselves), and always trigger a full
// page navigation on success (see each caller below) rather than client-side routing, since the
// destination may be /change-password or the post-login redirect target and Flask must re-serve a
// fresh SPA shell (fresh CSRF token, fresh org/role globals) for whichever page is next.
async function post(path: string, json: unknown): Promise<{ redirect: string }> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
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

export function signIn(username: string, password: string) {
  return post('/sign-in', { username, password })
}

export function signUp(username: string, password: string, name: string, orgName: string, email: string) {
  return post('/sign-up', { username, password, name, org_name: orgName, email })
}

export async function checkOrgNameAvailable(orgName: string): Promise<{ available: boolean; message: string | null }> {
  const response = await fetch(`${API_BASE_URL}/check-org-name?name=${encodeURIComponent(orgName)}`, {
    credentials: 'include',
  })
  return (await response.json()) as { available: boolean; message: string | null }
}

export function changePassword(newPassword: string, confirmPassword: string) {
  return post('/change-password', { new_password: newPassword, confirm_password: confirmPassword })
}

export async function signOut(): Promise<void> {
  await fetch(`${API_BASE_URL}/logout`, { method: 'POST', credentials: 'include' })
}
