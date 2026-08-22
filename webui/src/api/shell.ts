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

declare global {
  interface Window {
    __CSRF_TOKEN__?: string
    __USERNAME__?: string
    __ORG_ID__?: string | null
    // Injected only on GET /oauth/authorize — see api/presentation/routes/oauth.py.
    __OAUTH_AUTHORIZE__?: OAuthAuthorizeRequest
    __OAUTH_ERROR__?: OAuthErrorInfo
  }
}

// Globals injected into the served SPA shell by api/presentation/web/spa.py (serve_spa_shell) —
// every logged-in page gets a fresh CSRF token, the logged-in identity's username, and the active
// org's id on first load, so the nav bar can render without an extra round trip (see
// api/presentation/routes/app_shell.py). Permissions aren't injected here — they're resolved
// fresh per request server-side, so the frontend reads them from GET /orgs (Org.permissions)
// instead of a page-load snapshot that could go stale.
export function csrfToken(): string {
  return window.__CSRF_TOKEN__ ?? ''
}

export function currentUsername(): string {
  return window.__USERNAME__ ?? ''
}

export function currentOrgId(): string | null {
  return window.__ORG_ID__ ?? null
}
