import { useState } from 'react'
import { Link } from 'react-router-dom'
import { signUp } from '../api/auth'
import { ApiError } from '../api/errors'
import { AuthCard } from '../components/AuthCard'
import { PasswordField } from '../components/PasswordField'

export function SignUpPage() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const { redirect } = await signUp(email, password, name)
      window.location.href = redirect
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
      setSubmitting(false)
    }
  }

  return (
    <AuthCard
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
          <label htmlFor="email" className="mb-1.5 block text-sm text-foreground">
            Work email
          </label>
          <input
            id="email"
            type="email"
            placeholder="you@company.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
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
        <div className="rounded-sm bg-accent px-3.5 py-3 text-[13px] text-accent-foreground">
          We&apos;ll set up a workspace for you automatically — you can invite teammates or rename
          it anytime from org settings.
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="mt-1 rounded-sm bg-primary px-5 py-2.5 text-[15px] font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
        >
          {submitting ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </AuthCard>
  )
}
