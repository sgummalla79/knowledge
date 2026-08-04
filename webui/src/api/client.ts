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

async function rawRequest(path: string, options: RequestOptions = {}, retried = false): Promise<Response> {
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
    return rawRequest(path, options, true)
  }
  if (!response.ok) {
    const { message, code } = await parseErrorBody(response)
    throw new ApiError(message, response.status, code)
  }
  return response
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await rawRequest(path, options)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

// For list endpoints that report their total row count via X-Total-Count (see PaginationQuery in
// app/presentation/schemas.py) rather than in the JSON body itself.
async function requestPaginated<T>(path: string): Promise<{ items: T[]; total: number }> {
  const response = await rawRequest(path)
  const items = (await response.json()) as T[]
  const total = Number(response.headers.get('X-Total-Count') ?? items.length)
  return { items, total }
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  getPaginated: <T>(path: string) => requestPaginated<T>(path),
  post: <T>(path: string, json?: unknown) => request<T>(path, { method: 'POST', json }),
  patch: <T>(path: string, json?: unknown) => request<T>(path, { method: 'PATCH', json }),
  put: <T>(path: string, json?: unknown) => request<T>(path, { method: 'PUT', json }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, formData: FormData) => request<T>(path, { method: 'POST', formData }),
}
