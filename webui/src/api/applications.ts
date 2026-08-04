import { ApiError, parseErrorBody } from './errors'
import { csrfToken } from './shell'
import type { Application, ScopeGroup } from './types'

// Session+CSRF authenticated, not bearer-token — application registration is deliberately never
// part of the bearer-token OAuth2 API surface (see app/presentation/routes/auth_ui.py's
// _require_csrf_header): a delegable credential able to mint or delete other credentials would be
// a privilege-escalation vector. Mirrors api/auth.ts's fetch pattern rather than client.ts's.
async function request<T>(path: string, method: string = 'GET'): Promise<T> {
  const response = await fetch(path, {
    method,
    credentials: 'include',
    headers: method === 'GET' ? {} : { 'X-CSRF-Token': csrfToken() },
  })
  if (!response.ok) {
    const { message, code } = await parseErrorBody(response)
    throw new ApiError(message, response.status, code)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function listApplications(): Promise<Application[]> {
  return request('/dashboard/applications')
}

export function listScopeGroups(): Promise<ScopeGroup[]> {
  return request('/dashboard/scopes')
}

export function revokeApplicationToken(applicationId: string): Promise<void> {
  return request(`/dashboard/applications/${applicationId}/revoke-token`, 'POST')
}

export function deleteApplication(applicationId: string): Promise<void> {
  return request(`/dashboard/applications/${applicationId}/delete`, 'POST')
}
