import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Served by Flask (api/presentation/routes/workspace.py) from the same origin as the rest of the
// dashboard — base must match the static path it's mounted under so built asset URLs resolve
// correctly. outDir lands the build directly where deploy/Dockerfile's Node build stage expects
// to find it before COPYing into the final Python image.
export default defineConfig({
  base: '/static/workspace/',
  build: {
    outDir: '../api/static/workspace',
    emptyOutDir: true,
  },
  plugins: [react()],
})
