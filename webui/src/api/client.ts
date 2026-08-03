import { ApiError, parseErrorBody } from './errors'
import { csrfToken } from './shell'

// Bridges the admin's session-cookie login (already established by the Flask dashboard) to a real
// OAuth2 bearer token for this app's own REST API — see app/presentation/routes/workspace.py's
// POST /dashboard/token. Held in memory only, never persisted, mirroring the retry-once-on-401
// shape mcp_server/client.py's RagApiClient uses for its own (separate) service-account credential.
let accessToken: string | null = null

async function mintToken(): Promise<string> {
  const response = await fetch('/dashboard/token', {
    method: 'POST',
    credentials: 'include',
    headers: { 'X-CSRF-Token': csrfToken() },
  })
  if (!response.ok) {
    throw new ApiError('Your session has expired — please reload the page and log in again.', response.status)
  }
  const body = (await response.json()) as { access_token: string }
  accessToken = body.access_token
  return accessToken
}

interface RequestOptions {
  method?: string
  json?: unknown
  formData?: FormData
}

async function request<T>(path: string, options: RequestOptions = {}, retried = false): Promise<T> {
  if (accessToken === null) await mintToken()

  const headers: Record<string, string> = { Authorization: `Bearer ${accessToken}` }
  let body: BodyInit | undefined
  if (options.json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.json)
  } else if (options.formData) {
    body = options.formData
  }

  const response = await fetch(path, { method: options.method ?? 'GET', headers, body })

  if (response.status === 401 && !retried) {
    accessToken = null
    return request<T>(path, options, true)
  }
  if (!response.ok) {
    const { message, code } = await parseErrorBody(response)
    throw new ApiError(message, response.status, code)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, json?: unknown) => request<T>(path, { method: 'POST', json }),
  patch: <T>(path: string, json?: unknown) => request<T>(path, { method: 'PATCH', json }),
  put: <T>(path: string, json?: unknown) => request<T>(path, { method: 'PUT', json }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, formData: FormData) => request<T>(path, { method: 'POST', formData }),
}
