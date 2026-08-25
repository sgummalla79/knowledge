import { useState } from 'react'
import { signIn } from '../api/auth'
import { ApiError } from '../api/errors'
import { AuthCard } from '../components/AuthCard'
import { PasswordField } from '../components/PasswordField'

export function SignInPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const { redirect } = await signIn(username, password)
      window.location.href = redirect
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
      setSubmitting(false)
    }
  }

  return (
    <AuthCard
      eyebrow="Welcome back"
      title="Sign in"
      subtitle="Access your org's knowledge library."
      // Self-serve sign-up is hidden for now -- no link out to it from here. The /sign-up route
      // itself and its backend are untouched; this only removes the discoverable entry point.
      footer={null}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && (
          <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        <div>
          <label htmlFor="username" className="mb-1.5 block text-sm text-foreground">
            Username
          </label>
          <input
            id="username"
            autoFocus
            placeholder="you@company.com"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>
        <div>
          <div className="mb-1.5 flex items-baseline justify-between">
            <label htmlFor="password" className="block text-sm text-foreground">
              Password
            </label>
            <a href="#" className="text-xs text-primary hover:underline">
              Forgot password?
            </a>
          </div>
          <PasswordField id="password" placeholder="Your password" value={password} onChange={setPassword} />
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="mt-2 rounded-sm bg-primary px-5 py-2.5 text-[15px] font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
        >
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </AuthCard>
  )
}
