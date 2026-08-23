// webui/ is a separate deployable from the API now (see this repo's CLAUDE.md session history on
// the standalone-API change) — every relative fetch() path in this app (client.ts, auth.ts,
// oauth.ts, shell.ts) is prefixed with this at call time. Empty string keeps same-origin relative
// requests working for a setup that reverse-proxies both under one origin; anything else (local
// dev against a separately-run API container, or a real deployment on its own subdomain) sets
// VITE_API_BASE_URL at build/dev time — see .env.development for the local-dev-preview default and
// api/presentation/web/cors.py for the matching server-side allowlist this requires.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''
