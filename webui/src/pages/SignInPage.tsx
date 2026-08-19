import { useState } from 'react'
import { Link } from 'react-router-dom'
import { signIn } from '../api/auth'
import { ApiError } from '../api/errors'
import { AuthCard } from '../components/AuthCard'
import { PasswordField } from '../components/PasswordField'

export function SignInPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const { redirect } = await signIn(email, password)
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
      footer={
        <>
          Don&apos;t have an account?{' '}
          <Link to="/sign-up" className="text-primary hover:underline">
            Create one
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
        <div>
          <label htmlFor="email" className="mb-1.5 block text-sm text-foreground">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoFocus
            placeholder="you@company.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
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
