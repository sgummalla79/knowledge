import { ApiError, parseErrorBody } from './errors'
import { csrfToken } from './shell'

// Session+CSRF authenticated, not bearer-token — these run before any access token can exist
// (minting one itself requires being logged in), so they bypass client.ts's `api` helper
// entirely and talk to Flask's session-cookie surface directly, same as a browser form post would.
async function post(path: string, json: unknown): Promise<{ redirect: string }> {
  const response = await fetch(path, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() },
    body: JSON.stringify(json),
  })
  if (!response.ok) {
    const { message, code } = await parseErrorBody(response)
    throw new ApiError(message, response.status, code)
  }
  return (await response.json()) as { redirect: string }
}

export function login(username: string, password: string) {
  return post('/login', { username, password })
}

export function changePassword(newPassword: string, confirmPassword: string) {
  return post('/change-password', { new_password: newPassword, confirm_password: confirmPassword })
}

export async function signOut(): Promise<void> {
  await fetch('/logout', { method: 'POST', credentials: 'include' })
}
