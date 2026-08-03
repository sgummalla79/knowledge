declare global {
  interface Window {
    __CSRF_TOKEN__?: string
    __USERNAME__?: string
  }
}

// Globals injected into the served SPA shell by app/presentation/web/spa.py (serve_spa_shell) —
// every page this app renders (login, change-password, workspace) gets a fresh CSRF token on
// load; only /workspace also gets the logged-in username (for the sidebar's account menu).
export function csrfToken(): string {
  return window.__CSRF_TOKEN__ ?? ''
}

export function currentUsername(): string {
  return window.__USERNAME__ ?? ''
}
