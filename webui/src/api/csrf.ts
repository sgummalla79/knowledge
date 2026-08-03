declare global {
  interface Window {
    __CSRF_TOKEN__?: string
  }
}

// Injected into the served SPA shell by app/presentation/web/spa.py (serve_spa_shell) — every
// page this app renders (login, change-password, workspace) gets a fresh one on load.
export function csrfToken(): string {
  return window.__CSRF_TOKEN__ ?? ''
}
