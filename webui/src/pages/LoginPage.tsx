import { useState } from 'react'
import { AuthLayout } from '../components/AuthLayout'
import { PasswordField } from '../components/PasswordField'
import { useToast } from '../components/toastContext'
import { login } from '../api/auth'

export function LoginPage() {
  const { showToast } = useToast()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setPending(true)
    try {
      const result = await login(username, password)
      // Full navigation, not client-side routing — the target may be a server-rendered dashboard
      // page outside this SPA, or /change-password/​/workspace inside it; either way Flask needs
      // to serve a fresh shell with its own fresh CSRF token for wherever we land.
      window.location.href = result.redirect
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Login failed.')
      setPending(false)
    }
  }

  return (
    <AuthLayout title="Knowledge">
      <form onSubmit={handleSubmit}>
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
