import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { checkOrgNameAvailable, signUp } from '../api/auth'
import { ApiError } from '../api/errors'
import { AuthCard } from '../components/AuthCard'
import { PasswordField } from '../components/PasswordField'

// Mirrors the backend's validate_org_slug (api/application/org_name_validation.py) — client-side
// check is a UX nicety only, the server re-validates on both the availability probe and submit.
const ORG_NAME_PATTERN = /^[a-z0-9]+(-[a-z0-9]+)*$/

function normalizeOrgName(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export function SignUpPage() {
  const [name, setName] = useState('')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [orgName, setOrgName] = useState('')
  const [orgNameStatus, setOrgNameStatus] = useState<{ available: boolean; message: string | null } | null>(null)
  const [checkingOrgName, setCheckingOrgName] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (orgName.length < 3 || !ORG_NAME_PATTERN.test(orgName)) {
      setOrgNameStatus(null)
      return
    }
    setCheckingOrgName(true)
    const timeout = setTimeout(() => {
      checkOrgNameAvailable(orgName)
        .then(setOrgNameStatus)
        .catch(() => setOrgNameStatus(null))
        .finally(() => setCheckingOrgName(false))
    }, 400)
    return () => clearTimeout(timeout)
  }, [orgName])

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const { redirect } = await signUp(username, password, name, orgName, email)
      window.location.href = redirect
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
      setSubmitting(false)
    }
  }

  return (
    <AuthCard
      wide
      eyebrow="Get started"
      title="Create your account"
      subtitle="You'll join an existing org, or create one right after."
      footer={
        <>
          Already have an account?{' '}
          <Link to="/sign-in" className="text-primary hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && (
          <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        <div className="grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-2">
          <div className="flex flex-col gap-4">
            <div>
              <label htmlFor="name" className="mb-1.5 block text-sm text-foreground">
                Full name
              </label>
              <input
                id="name"
                autoFocus
                placeholder="Ada Lovelace"
                value={name}
                onChange={(event) => setName(event.target.value)}
                className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
            <div>
              <label htmlFor="org-name" className="mb-1.5 block text-sm text-foreground">
                Org name
              </label>
              <input
                id="org-name"
                placeholder="acme-labs"
                value={orgName}
                onChange={(event) => setOrgName(normalizeOrgName(event.target.value))}
                className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              {orgName.length > 0 && orgName.length < 3 && (
                <p className="mt-1 text-[13px] text-muted-foreground">At least 3 characters.</p>
              )}
              {checkingOrgName && <p className="mt-1 text-[13px] text-muted-foreground">Checking availability…</p>}
              {!checkingOrgName && orgNameStatus && (
                <p className={`mt-1 text-[13px] ${orgNameStatus.available ? 'text-green-600' : 'text-destructive'}`}>
                  {orgNameStatus.available ? 'Available' : orgNameStatus.message}
                </p>
              )}
            </div>
            <div>
              <label htmlFor="email" className="mb-1.5 block text-sm text-foreground">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                placeholder="you@company.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
          </div>
          <div className="flex flex-col gap-4">
            <div>
              <label htmlFor="username" className="mb-1.5 block text-sm text-foreground">
                Username
              </label>
              <input
                id="username"
                placeholder="ada@acme.com"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm text-foreground">
                Password
              </label>
              <PasswordField
                id="password"
                placeholder="At least 8 characters"
                value={password}
                onChange={setPassword}
              />
            </div>
          </div>
        </div>
        <button
          type="submit"
          disabled={submitting || checkingOrgName || orgNameStatus?.available === false}
          className="mt-1 rounded-sm bg-primary px-5 py-2.5 text-[15px] font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
        >
          {submitting ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </AuthCard>
  )
}
