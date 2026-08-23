import { API_BASE_URL } from './config'

export interface OAuthAuthorizeRequest {
  application_name: string
  org_name: string
  client_id: string
  redirect_uri: string
  response_type: string
  code_challenge: string
  code_challenge_method: string
  scope: string
  state: string
}

export interface OAuthErrorInfo {
  message: string
}

// Bootstrap state, fetched once at app start (see bootstrap() below) rather than injected into a
// server-rendered HTML shell — this API renders no HTML at all now (see this repo's CLAUDE.md
// session history on the standalone-API change; api/presentation/routes/auth_ui.py's GET
// /csrf-token and GET /session are the replacements for what app_shell.py used to embed). Reads
// stay synchronous (csrfToken()/currentUsername()/etc.) so every existing call site — NavBar,
// client.ts's CSRF header, the Settings pages reading currentOrgId() — keeps working unchanged;
// only the population moved from "already present before React renders" to "awaited once by
// App.tsx before the router mounts".
let csrfTokenValue = ''
let sessionInfo: { username: string; orgId: string | null; orgSlug: string | null } | null = null

export async function bootstrap(): Promise<void> {
  const csrfResponse = await fetch(`${API_BASE_URL}/csrf-token`, { credentials: 'include' })
  if (csrfResponse.ok) {
    const data = (await csrfResponse.json()) as { csrf_token: string }
    csrfTokenValue = data.csrf_token
  }

  const sessionResponse = await fetch(`${API_BASE_URL}/session`, { credentials: 'include' })
  if (sessionResponse.ok) {
    const data = (await sessionResponse.json()) as { username: string; org_id: string; org_slug: string | null }
    sessionInfo = { username: data.username, orgId: data.org_id, orgSlug: data.org_slug }
  } else {
    sessionInfo = null
  }
}

export function csrfToken(): string {
  return csrfTokenValue
}

export function currentUsername(): string {
  return sessionInfo?.username ?? ''
}

export function currentOrgId(): string | null {
  return sessionInfo?.orgId ?? null
}

export function currentOrgSlug(): string | null {
  return sessionInfo?.orgSlug ?? null
}

declare global {
  interface Window {
    // Injected only on GET /oauth/authorize — see api/presentation/routes/oauth.py.
    __OAUTH_AUTHORIZE__?: OAuthAuthorizeRequest
    __OAUTH_ERROR__?: OAuthErrorInfo
  }
}
