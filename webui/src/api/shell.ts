export interface OAuthAuthorizeParams {
  response_type: string
  client_id: string
  redirect_uri: string
  scope: string[]
  state: string
  code_challenge: string
  code_challenge_method: string
}

export interface OAuthAuthorizeData {
  application_name: string
  params: OAuthAuthorizeParams
}

declare global {
  interface Window {
    __CSRF_TOKEN__?: string
    __USERNAME__?: string
    __OAUTH_AUTHORIZE__?: OAuthAuthorizeData
    __OAUTH_ERROR__?: string
  }
}

// Globals injected into the served SPA shell by app/presentation/web/spa.py (serve_spa_shell) —
// every page this app renders (login, change-password, workspace, oauth/authorize) gets a fresh
// CSRF token on load; /workspace also gets the logged-in username (for the sidebar's account
// menu), and /oauth/authorize gets exactly one of __OAUTH_AUTHORIZE__ (render the consent form)
// or __OAUTH_ERROR__ (render the error page) — see app/presentation/routes/oauth.py's authorize().
export function csrfToken(): string {
  return window.__CSRF_TOKEN__ ?? ''
}

export function currentUsername(): string {
  return window.__USERNAME__ ?? ''
}

export function oauthAuthorizeData(): OAuthAuthorizeData | null {
  return window.__OAUTH_AUTHORIZE__ ?? null
}

export function oauthError(): string | null {
  return window.__OAUTH_ERROR__ ?? null
}
