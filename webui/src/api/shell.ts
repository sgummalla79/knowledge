declare global {
  interface Window {
    __CSRF_TOKEN__?: string
    __USERNAME__?: string
    __ORG_ID__?: string | null
    __ORG_NAME__?: string | null
    __ROLE__?: string | null
  }
}

// Globals injected into the served SPA shell by api/presentation/web/spa.py (serve_spa_shell) —
// every logged-in page gets a fresh CSRF token, the logged-in identity's email, and the active
// org's id/name/role on first load, so the nav bar can render without an extra round trip (see
// api/presentation/routes/app_shell.py).
export function csrfToken(): string {
  return window.__CSRF_TOKEN__ ?? ''
}

export function currentUsername(): string {
  return window.__USERNAME__ ?? ''
}

export function currentOrgId(): string | null {
  return window.__ORG_ID__ ?? null
}

export function currentOrgName(): string | null {
  return window.__ORG_NAME__ ?? null
}

export function currentRole(): string | null {
  return window.__ROLE__ ?? null
}
