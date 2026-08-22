import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Built output is served by Flask (api/presentation/routes/app_shell.py) from the same origin as
// the rest of the API — base must match the static path it's mounted under so built asset URLs
// resolve correctly. outDir lands the build directly where deploy/Dockerfile's Node build stage
// expects to find it before COPYing into the final Python image.
//
// `npm run dev` (local iteration only) is a separate standalone server on its own port instead —
// Flask's serve_spa_shell() points the SPA shell straight at it (WEBUI_DEV_SERVER, see
// api/presentation/web/spa.py) rather than proxying, so base must be '/' here, not the built
// bundle's mount path. Port is fixed (not Vite's default-with-auto-increment-if-taken) since
// spa.py's dev shell needs a stable URL to point at.
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/static/workspace/' : '/',
  build: {
    outDir: '../api/static/workspace',
    emptyOutDir: true,
  },
  server: {
    // Explicit 127.0.0.1, not the 'localhost' default — this machine resolves 'localhost' to
    // ::1 (IPv6) while spa.py's WEBUI_DEV_SERVER and the rest of this doc's dev-preview
    // conventions all use 127.0.0.1, so leaving it implicit silently breaks the two matching up.
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    cors: true,
  },
  plugins: [react(), tailwindcss()],
}))
