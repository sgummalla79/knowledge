import { API_BASE_URL } from './config'
import { ApiError, parseErrorBody } from './errors'
import { csrfToken } from './shell'

// Cookie-session + CSRF client for every resource route (categories, documents, shelves, orgs,
// ...) — there is no bearer-token/API-key concept in this app's auth model (plain Flask session
// cookie, see api/presentation/routes/auth_ui.py), so every call just rides the browser's session
// cookie and attaches X-CSRF-Token on mutations, the same way auth.ts's login/signup calls do.

const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  if (MUTATING_METHODS.has(method)) {
    headers.set('X-CSRF-Token', csrfToken())
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, method, headers, credentials: 'include' })
  if (!response.ok) {
    if (response.status === 401) {
      // Session expired mid-use (every page load is already server-gated, so this only fires
      // once a previously-valid session lapses) — same full navigation login.tsx would do, so a
      // fresh CSRF token and shell globals load with the sign-in page.
      window.location.href = '/sign-in'
    }
    const { message, code, field } = await parseErrorBody(response)
    throw new ApiError(message, response.status, code, field)
  }
  return response
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body !== undefined && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await request(path, { ...init, headers })
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  get: <T>(path: string) => requestJson<T>(path),

  getPaginated: async <T>(path: string): Promise<{ items: T[]; total: number }> => {
    const response = await request(path)
    const items = (await response.json()) as T[]
    const total = Number(response.headers.get('X-Total-Count') ?? items.length)
    return { items, total }
  },

  post: <T>(path: string, body?: unknown) =>
    requestJson<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),

  patch: <T>(path: string, body?: unknown) =>
    requestJson<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) }),

  put: <T>(path: string, body?: unknown) =>
    requestJson<T>(path, { method: 'PUT', body: body === undefined ? undefined : JSON.stringify(body) }),

  delete: <T>(path: string) => requestJson<T>(path, { method: 'DELETE' }),

  upload: <T>(path: string, formData: FormData) => requestJson<T>(path, { method: 'POST', body: formData }),
}
