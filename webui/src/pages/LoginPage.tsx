import { useState } from 'react'
import { AuthLayout } from '../components/AuthLayout'
import { PasswordField } from '../components/PasswordField'
import { login } from '../api/auth'

export function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setPending(true)
    try {
      const result = await login(username, password)
      // Full navigation, not client-side routing — the target may be a server-rendered dashboard
      // page outside this SPA, or /change-password/​/workspace inside it; either way Flask needs
      // to serve a fresh shell with its own fresh CSRF token for wherever we land.
      window.location.href = result.redirect
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed.')
      setPending(false)
    }
  }

  return (
    <AuthLayout title="Knowledge">
      <form onSubmit={handleSubmit}>
        {error && <div className="error-banner">{error}</div>}
        <input
          className="field-pill"
          type="text"
          placeholder="Username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          autoFocus
        />
        <PasswordField id="password" placeholder="Password" value={password} onChange={setPassword} />
        <button type="submit" className="btn-block" disabled={pending || !username || !password}>
          Sign in
        </button>
      </form>
    </AuthLayout>
  )
}
