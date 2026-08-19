const STORAGE_KEY = 'knowledge-theme'

export type Theme = 'light' | 'dark'

// Applies a stored explicit choice immediately on load (called from main.tsx before React
// renders, to avoid a flash of the wrong theme) — no stored choice means "follow system", so no
// data-theme attribute is set at all and index.css's prefers-color-scheme block takes over.
export function applyStoredTheme(): void {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'light' || stored === 'dark') {
    document.documentElement.dataset.theme = stored
  }
}

export function currentTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'light' || stored === 'dark') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function setTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme
  localStorage.setItem(STORAGE_KEY, theme)
}
