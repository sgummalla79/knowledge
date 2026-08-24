import { defineConfig, devices } from '@playwright/test'

// Assumes the dev-preview stack (Postgres + Flask + Vite) is already running -- see this repo's
// CLAUDE.md "Local dev preview" section, deploy/dev-preview-up.sh. Deliberately no `webServer`
// auto-start block here: orchestrating Postgres + migrations + Flask + Vite together from
// Playwright itself is a separate, bigger effort (this suite is meant to run against the same
// persistent dev-preview stack a developer is already using interactively, not spin up its own).
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false, // each spec signs up its own fresh org; no shared state to race on, but
  // keeping this sequential for now avoids hammering a single-worker dev-preview Flask process.
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
