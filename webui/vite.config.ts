import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// webui/ is a standalone deployable, served from its own origin (see this repo's CLAUDE.md
// session history item 34/35) — it owns the whole domain it's served from, never mounted under a
// sub-path, so base is always '/'. VITE_API_BASE_URL (webui/src/api/config.ts) is what points the
// built app at the API's real origin; it's a build-time env var (Vite bakes import.meta.env values
// in at build time), not something this config file needs to know about.
export default defineConfig({
  base: '/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    // Explicit 127.0.0.1, not the 'localhost' default — this machine resolves 'localhost' to
    // ::1 (IPv6) while this repo's dev-preview conventions (CLAUDE.md) all use 127.0.0.1, so
    // leaving it implicit silently breaks the two matching up.
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    cors: true,
  },
  plugins: [react(), tailwindcss()],
})
