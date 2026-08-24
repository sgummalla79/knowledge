import { test, expect } from '@playwright/test'

// Runs against the dev-preview stack (see playwright.config.ts) -- a real Postgres + Flask + Vite,
// exactly like a developer clicking around manually. Exists because this app's frontend has had
// zero automated coverage (flagged in this repo's own CLAUDE.md after item 35's CSRF-bootstrap
// breakage went undetected by the Python test suite), and because the 2026-08-24 login-lockout
// incident was, again, only caught by a manual Playwright walkthrough -- these three scenarios are
// exactly the ones driven by hand that day, made permanent.

function freshCredentials() {
  const suffix = Math.floor(Math.random() * 1_000_000)
  return {
    orgName: `e2e-check-${suffix}`,
    username: `e2e-check-${suffix}@example.com`,
    password: 'TestPassword123!',
  }
}

test('sign up, land on the dashboard, sign out, and sign back in cleanly', async ({ page }) => {
  const { orgName, username, password } = freshCredentials()

  await page.goto('/sign-up')
  await page.getByPlaceholder('Ada Lovelace').fill('E2E Check')
  await page.getByPlaceholder('acme-labs').fill(orgName)
  await page.getByPlaceholder('you@company.com').fill(username)
  await page.getByPlaceholder('ada@acme.com').fill(username)
  await page.getByPlaceholder('At least 8 characters').fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()

  await expect(page).toHaveURL(new RegExp(`/${orgName}`))

  // Sign out, then sign back in -- direct regression coverage for the 2026-08-24 login-lockout
  // incident, at the one layer none of the Python tests can reach: a real browser, real cookies,
  // the real /sign-in -> /session sequence a returning user actually experiences.
  await page.getByLabel('Account menu').click()
  await page.getByText('Sign out').click()
  await expect(page).toHaveURL(/\/sign-in/)

  await page.getByPlaceholder('you@company.com').fill(username)
  await page.getByPlaceholder('Your password').fill(password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()

  // The exact failure mode from the incident: a bounce back to /sign-in instead of landing home.
  await expect(page).toHaveURL(new RegExp(`/${orgName}`))
  await expect(page.getByLabel('Account menu')).toBeVisible()
})

test('upload a document and watch its job settle to a terminal state', async ({ page }) => {
  const { orgName, username, password } = freshCredentials()

  await page.goto('/sign-up')
  await page.getByPlaceholder('Ada Lovelace').fill('E2E Check')
  await page.getByPlaceholder('acme-labs').fill(orgName)
  await page.getByPlaceholder('you@company.com').fill(username)
  await page.getByPlaceholder('ada@acme.com').fill(username)
  await page.getByPlaceholder('At least 8 characters').fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page).toHaveURL(new RegExp(`/${orgName}`))

  // A bare /upload (no org prefix) trips the app's own URL self-correction (App.tsx compares the
  // address bar's org slug against the session's real one and redirects to the org home,
  // deliberately dropping the sub-path -- see this repo's CLAUDE.md item 21) -- must navigate to
  // the org-prefixed path directly, the same way the third test below already does.
  await page.goto(`/${orgName}/upload`)
  await page.locator('input[type="file"]').setInputFiles({
    name: 'e2e-check.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('hello from the e2e critical-path check'),
  })
  await page.getByPlaceholder('e.g. Q3 refund policy update').fill('E2E check document')
  await page.getByRole('button', { name: /Add to library|Adding…|Indexing…/ }).click()

  // No embedding provider is configured for a fresh dev-preview org, so this job is expected to
  // fail -- what's under test is the frontend's own polling wiring (does it reach a terminal
  // state and re-enable the form), not a successful ingestion. api/ingestion_worker/tests/
  // already covers real success/failure processing end-to-end on the backend.
  await expect(page.getByRole('button', { name: 'Add to library' })).toBeVisible({ timeout: 30_000 })
})

test('several authenticated navigations at once do not fail or lock up', async ({ page, context }) => {
  const { orgName, username, password } = freshCredentials()

  await page.goto('/sign-up')
  await page.getByPlaceholder('Ada Lovelace').fill('E2E Check')
  await page.getByPlaceholder('acme-labs').fill(orgName)
  await page.getByPlaceholder('you@company.com').fill(username)
  await page.getByPlaceholder('ada@acme.com').fill(username)
  await page.getByPlaceholder('At least 8 characters').fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page).toHaveURL(new RegExp(`/${orgName}`))

  // A browser-level version of api/tests/concurrency/'s check: several tabs (the same cookie jar,
  // same identity) hitting authenticated routes at once should never 500 or hang -- the exact
  // pattern (concurrent requests from one signed-in identity) behind two of the 2026-08-24
  // incidents.
  const paths = ['/browse', '/search', '/dashboard', '/upload']
  const pages = await Promise.all(paths.map(() => context.newPage()))
  const responses = await Promise.all(
    pages.map((p, i) => p.goto(`/${orgName}${paths[i]}`, { waitUntil: 'domcontentloaded' })),
  )

  for (const response of responses) {
    expect(response?.ok()).toBeTruthy()
  }
  await Promise.all(pages.map((p) => p.close()))
})
