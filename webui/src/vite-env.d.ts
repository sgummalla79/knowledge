/// <reference types="vite/client" />

interface ImportMetaEnv {
  // See webui/src/api/config.ts — the API's origin, empty for a same-origin (reverse-proxied)
  // deployment.
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
